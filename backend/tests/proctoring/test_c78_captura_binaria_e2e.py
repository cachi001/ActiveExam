"""La captura binaria de punta a punta, contra Postgres real (c-78, task 16.4).

La parte pura (round-trip exacto) esta en `tests/test_c78_captura_binaria.py`.
Aca se verifica lo que solo se ve con la base delante:

  - la captura se persiste en `screenshot_bin` (binaria y cifrada) y NO en la
    columna base64 vieja;
  - el revisor la sigue leyendo identica a lo que mando el cliente;
  - `verify-chain` sigue dando cadena INTEGRA, que es la prueba de que ningun
    hash se movio;
  - las filas legacy en base64 se siguen leyendo y verificando igual;
  - la purga de retencion borra la columna nueva (si no, dejaria de purgar de
    verdad justo cuando la captura pesa mas).
"""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.compliance.retencion_capturas import purgar_capturas_vencidas
from app.application.proctoring import event_service
from app.application.proctoring.captura_almacenada import leer_captura
from app.application.proctoring.reinferencia import ResultadoReinferencia
from app.application.verify_chain.service import VerifyChainService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.verify_chain.certificate import ChainVerificationStatus
from app.infrastructure.crypto.evidence_encryption import EvidenceCipher
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.verify_chain import (
    SqlChainVerificationAuditor,
    SqlEventMaterialRepository,
)

pytestmark = pytest.mark.asyncio

_IMAGEN = os.urandom(2048)
_DATA_URL = "data:image/jpeg;base64," + base64.b64encode(_IMAGEN).decode("ascii")
_HASH_CLIENTE = hashlib.sha256(_IMAGEN).hexdigest()

_PRINCIPAL = AuthenticatedPrincipal(
    username="estudiante1", email="estudiante1@activeexam.local"
)


class _ReinferenciaStub:
    def evaluar(
        self, screenshot_b64: str | None, face_count_cliente: int | None
    ) -> ResultadoReinferencia:
        return ResultadoReinferencia(face_count_servidor=1, veredicto="coincide")


def _cipher() -> EvidenceCipher:
    return EvidenceCipher(key=Fernet.generate_key().decode())


async def _crear_sesion(db_session: AsyncSession, *, creada_en=None) -> str:
    sesion = ProctoringSessionModel(modo="test")
    if creada_en is not None:
        sesion.creada_en = creada_en
    db_session.add(sesion)
    await db_session.commit()
    await db_session.refresh(sesion)
    return sesion.id


async def _ingestar(db_session, cipher, session_id=None) -> ProctoringEventModel:
    session_id = session_id or await _crear_sesion(db_session)
    return await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="MULTIPLE_FACES",
        severidad="alto",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL,
        screenshot_base64=_DATA_URL,
        face_count_cliente=2,
        cipher=cipher,
        screenshot_sha256_cliente=_HASH_CLIENTE,
    )


async def test_la_captura_va_a_la_columna_BINARIA_y_no_a_la_base64(
    db_session: AsyncSession,
) -> None:
    evento = await _ingestar(db_session, _cipher())

    assert evento.screenshot_bin is not None
    assert evento.screenshot_b64 is None  # la vieja queda solo para el historico
    assert evento.screenshot_prefijo == "data:image/jpeg;base64"


async def test_ocupa_MENOS_que_el_base64_cifrado_que_reemplaza(
    db_session: AsyncSession,
) -> None:
    """La razon de ser del change. El base64 cifrado del mismo contenido pesa ~78%
    mas que la imagen; el binario cifrado pesa ~100%."""
    cipher = _cipher()
    evento = await _ingestar(db_session, cipher)
    equivalente_viejo = cipher.encrypt(_DATA_URL)

    assert evento.screenshot_bin is not None
    assert len(evento.screenshot_bin) < len(equivalente_viejo)
    # Y de paso: sigue siendo mas grande que la imagen cruda (esta cifrada).
    assert len(evento.screenshot_bin) >= len(_IMAGEN)


async def test_el_revisor_la_lee_IDENTICA_a_lo_que_mando_el_cliente(
    db_session: AsyncSession,
) -> None:
    cipher = _cipher()
    evento = await _ingestar(db_session, cipher)

    leida = leer_captura(
        screenshot_bin=evento.screenshot_bin,
        screenshot_prefijo=evento.screenshot_prefijo,
        screenshot_b64_legacy=evento.screenshot_b64,
        cipher=cipher,
    )

    assert leida == _DATA_URL


async def test_verify_chain_sigue_dando_cadena_INTEGRA(
    db_session: AsyncSession,
) -> None:
    """La prueba de que ningun hash se movio: verify-chain re-hashea la captura
    reconstruida y la compara contra el `screenshot_sha256` del ingreso."""
    cipher = _cipher()
    evento = await _ingestar(db_session, cipher)

    servicio = VerifyChainService(
        event_repo=SqlEventMaterialRepository(db_session, cipher=cipher),
        auditor=SqlChainVerificationAuditor(db_session),
    )
    cert = await servicio.verify(evento.id, actor="test")

    assert cert.status == ChainVerificationStatus.INTACT


async def test_el_hash_de_custodia_del_cliente_sigue_coincidiendo(
    db_session: AsyncSession,
) -> None:
    evento = await _ingestar(db_session, _cipher())
    assert evento.custodia_cliente == "coincide"


async def test_una_fila_LEGACY_en_base64_se_sigue_leyendo_y_verificando(
    db_session: AsyncSession,
) -> None:
    """La base real va a tener las dos cosas por mucho tiempo. El historico no
    puede volverse ilegible por este change."""
    cipher = _cipher()
    session_id = await _crear_sesion(db_session)
    evento = await _ingestar(db_session, cipher, session_id)
    # Simula una fila vieja: la captura en la columna base64, la binaria vacia.
    evento.screenshot_b64 = cipher.encrypt(_DATA_URL)
    evento.screenshot_bin = None
    evento.screenshot_prefijo = None
    await db_session.commit()

    leida = leer_captura(
        screenshot_bin=None,
        screenshot_prefijo=None,
        screenshot_b64_legacy=evento.screenshot_b64,
        cipher=cipher,
    )
    assert leida == _DATA_URL

    servicio = VerifyChainService(
        event_repo=SqlEventMaterialRepository(db_session, cipher=cipher),
        auditor=SqlChainVerificationAuditor(db_session),
    )
    cert = await servicio.verify(evento.id, actor="test")
    assert cert.status == ChainVerificationStatus.INTACT


async def test_la_purga_de_retencion_borra_la_columna_NUEVA(
    db_session: AsyncSession,
) -> None:
    """Si la purga solo mirara la columna vieja, dejaria de borrar de verdad justo
    cuando la captura pesa mas — el problema de cumplimiento que existe para
    resolver (Ley 25.326)."""
    vieja = datetime.now(timezone.utc) - timedelta(days=400)
    session_id = await _crear_sesion(db_session, creada_en=vieja)
    evento = await _ingestar(db_session, _cipher(), session_id)
    assert evento.screenshot_bin is not None

    purgadas = await purgar_capturas_vencidas(db_session, dias=180)
    await db_session.commit()
    await db_session.refresh(evento)

    assert purgadas >= 1
    assert evento.screenshot_bin is None
    assert evento.screenshot_prefijo is None
    # El registro de que el evento existio SOBREVIVE: solo se va la imagen.
    assert evento.screenshot_sha256 is not None
    assert evento.id is not None


async def test_la_purga_es_idempotente(db_session: AsyncSession) -> None:
    vieja = datetime.now(timezone.utc) - timedelta(days=400)
    session_id = await _crear_sesion(db_session, creada_en=vieja)
    await _ingestar(db_session, _cipher(), session_id)

    await purgar_capturas_vencidas(db_session, dias=180)
    await db_session.commit()
    segunda = await purgar_capturas_vencidas(db_session, dias=180)
    await db_session.commit()

    assert segunda == 0
