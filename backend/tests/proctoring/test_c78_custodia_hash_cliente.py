"""Persistencia de la cadena de custodia cliente -> backend (c-78). Postgres real.

La parte pura (que se hashea y como se compara) vive en
`tests/test_c78_custodia_hash_cliente.py`. Aca se verifica lo que faltaba de
verdad: que el hash del cliente SE GUARDE en vez de descartarse, y que una
discrepancia no rechace el evento.

L2.5 (regla dura #5): el sistema nunca sanciona automaticamente. Una discrepancia
de hash es una senal para el revisor humano, no un veredicto.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
from app.application.proctoring.reinferencia import ResultadoReinferencia
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

pytestmark = pytest.mark.asyncio

_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_DATA_URL = f"data:image/png;base64,{_PNG_1X1_B64}"
_HASH_CLIENTE_OK = hashlib.sha256(base64.b64decode(_PNG_1X1_B64)).hexdigest()

_PRINCIPAL_TEST = AuthenticatedPrincipal(
    username="estudiante1", email="estudiante1@activeexam.local"
)


class _ReinferenciaStub:
    """Stub PURO del puerto — NO instancia MediaPipe."""

    def evaluar(
        self, screenshot_b64: str | None, face_count_cliente: int | None
    ) -> ResultadoReinferencia:
        return ResultadoReinferencia(face_count_servidor=1, veredicto="coincide")


async def _crear_sesion(db_session: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="test")
    db_session.add(sesion)
    await db_session.commit()
    await db_session.refresh(sesion)
    return sesion.id


async def test_el_hash_del_cliente_se_persiste_y_se_verifica(
    db_session: AsyncSession,
) -> None:
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="MULTIPLE_FACES",
        severidad="alto",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_DATA_URL,
        face_count_cliente=2,
        screenshot_sha256_cliente=_HASH_CLIENTE_OK,
    )

    assert evento.screenshot_sha256_cliente == _HASH_CLIENTE_OK
    assert evento.custodia_cliente == "coincide"


async def test_una_discrepancia_no_rechaza_el_evento_solo_la_deja_asentada(
    db_session: AsyncSession,
) -> None:
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="MULTIPLE_FACES",
        severidad="alto",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_DATA_URL,
        face_count_cliente=2,
        screenshot_sha256_cliente="f" * 64,
    )

    assert evento.id is not None  # se persistio igual (L2.5: nunca rechaza)
    assert evento.custodia_cliente == "discrepancia"
    assert evento.screenshot_sha256_cliente == "f" * 64


async def test_cliente_que_no_manda_hash_no_queda_marcado_como_sospechoso(
    db_session: AsyncSession,
) -> None:
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="FACE_ABSENT",
        severidad="medio",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_DATA_URL,
        face_count_cliente=0,
        screenshot_sha256_cliente=None,
    )

    assert evento.screenshot_sha256_cliente is None
    assert evento.custodia_cliente == "no_verificable"


async def test_el_evento_sin_screenshot_sigue_entrando_igual(
    db_session: AsyncSession,
) -> None:
    """Los eventos de contexto (cambio de pestana, copiar/pegar) pueden no traer
    captura. La custodia no aplica y no tiene que estorbar."""
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="TAB_CHANGED",
        severidad="medio",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=None,
        face_count_cliente=None,
    )

    assert evento.screenshot_sha256_cliente is None
    assert evento.custodia_cliente == "no_verificable"
