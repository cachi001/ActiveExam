"""verify-chain sobre evidencia CIFRADA at-rest, que es como está en producción (c-78).

## El bug

`screenshot_sha256` se calcula sobre el screenshot EN CLARO, antes de cifrar
(`event_service`, paso 2). Pero `SqlEventMaterialRepository` lee la columna
`screenshot_b64` **tal cual está en la base**, o sea el token Fernet, y
`VerifyChainService` re-hashea eso y lo compara contra el hash del claro.

Nunca pueden coincidir. Con el cifrado activo —y lo está: `main_activeexam`
construye el `EvidenceCipher` con `EMBEDDING_ENCRYPTION_KEY`— **verify-chain
reportaba `broken` (cadena rota, o sea evidencia manipulada) para TODOS los
eventos**.

Y no es un endpoint de perito que se usa una vez al año: `informe_service` corre
este mismo servicio sobre CADA captura del informe de devolución que ve el
alumno. Le estábamos diciendo a cada alumno que su propia evidencia estaba
adulterada.

El test de integración que ya existía (`test_c18_verify_chain_integration.py`)
no lo agarraba porque escribe `screenshot_b64` a mano EN CLARO: probaba un
escenario que en producción no ocurre.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
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

_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_DATA_URL = f"data:image/png;base64,{_PNG_1X1_B64}"
_HASH_CLIENTE = hashlib.sha256(base64.b64decode(_PNG_1X1_B64)).hexdigest()

_PRINCIPAL = AuthenticatedPrincipal(
    username="estudiante1", email="estudiante1@activeexam.local"
)


class _ReinferenciaStub:
    def evaluar(
        self, screenshot_b64: str | None, face_count_cliente: int | None
    ) -> ResultadoReinferencia:
        return ResultadoReinferencia(face_count_servidor=1, veredicto="coincide")


def _cipher() -> EvidenceCipher:
    """Cipher real, con una clave Fernet generada para el test (nunca hardcodeada)."""
    return EvidenceCipher(key=Fernet.generate_key().decode())


async def _crear_sesion(db_session: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="test")
    db_session.add(sesion)
    await db_session.commit()
    await db_session.refresh(sesion)
    return sesion.id


async def _ingestar(db_session: AsyncSession, cipher: EvidenceCipher | None) -> str:
    session_id = await _crear_sesion(db_session)
    evento = await event_service.ingestar_evento(
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
    return evento.id


def _servicio(db_session: AsyncSession, cipher: EvidenceCipher | None) -> VerifyChainService:
    return VerifyChainService(
        event_repo=SqlEventMaterialRepository(db_session, cipher=cipher),
        auditor=SqlChainVerificationAuditor(db_session),
    )


async def test_evidencia_cifrada_verifica_como_INTACTA(db_session: AsyncSession) -> None:
    """El caso de PRODUCCIÓN: con el cipher activo la cadena tiene que dar íntegra."""
    cipher = _cipher()
    evento_id = await _ingestar(db_session, cipher)

    cert = await _servicio(db_session, cipher).verify(evento_id, actor="test")

    assert cert.status == ChainVerificationStatus.INTACT


async def test_sin_cifrado_sigue_verificando_como_intacta(
    db_session: AsyncSession,
) -> None:
    """Retrocompatibilidad: las filas legacy en claro se siguen verificando bien."""
    evento_id = await _ingestar(db_session, None)

    cert = await _servicio(db_session, None).verify(evento_id, actor="test")

    assert cert.status == ChainVerificationStatus.INTACT


async def test_una_fila_LEGACY_en_base64_se_verifica_aunque_haya_cipher(
    db_session: AsyncSession,
) -> None:
    """La base real tiene las dos cosas: filas viejas con la captura en la columna
    base64 y nuevas con la binaria (migración 0097). El mismo camino de lectura
    tiene que servir para ambas, o el histórico se vuelve inverificable."""
    cipher = _cipher()
    evento_id = await _ingestar(db_session, cipher)

    # Convertir la fila recién escrita en una LEGACY: la captura pasa a la columna
    # base64 (como se guardaba antes de 0097) y la binaria queda vacía.
    evento = await db_session.get(ProctoringEventModel, evento_id)
    assert evento is not None
    evento.screenshot_b64 = cipher.encrypt(_DATA_URL)
    evento.screenshot_bin = None
    evento.screenshot_prefijo = None
    await db_session.commit()

    cert = await _servicio(db_session, cipher).verify(evento_id, actor="test")

    assert cert.status == ChainVerificationStatus.INTACT


async def test_si_alguien_toca_la_captura_en_la_base_la_cadena_da_ROTA(
    db_session: AsyncSession,
) -> None:
    """Lo que verify-chain existe para detectar tiene que seguir detectándose: el
    arreglo no puede volverlo un sello de goma que dice 'intacta' siempre."""
    cipher = _cipher()
    evento_id = await _ingestar(db_session, cipher)

    evento = await db_session.get(ProctoringEventModel, evento_id)
    assert evento is not None
    # Se manosea la columna donde vive la captura HOY (la binaria). Tocar la
    # base64 legacy no probaría nada: el lector ni la mira si hay binario.
    evento.screenshot_bin = cipher.encrypt_bytes(b"otra-imagen-completamente-distinta")
    await db_session.commit()

    cert = await _servicio(db_session, cipher).verify(evento_id, actor="test")

    assert cert.status == ChainVerificationStatus.BROKEN
