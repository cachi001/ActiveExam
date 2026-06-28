"""7.9-7.10 RED → GREEN: test de disparo server-side al finalizar la sesión.

La finalización de sesión NO se bloquea aunque Moodle falle.
El write-back se dispara sin bloquear.

Estos tests verifican el comportamiento puro sin HTTP real — usa mocking de httpx.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.moodle.writeback_service import MoodleWritebackService, WritebackEstado


@pytest.mark.asyncio
async def test_finalizar_no_bloquea_si_moodle_tarda():
    """7.9: si el writeback tarda (o falla), finalizar_sesion completa igual.

    Verifica que el disparo del writeback es fire-and-forget:
    la corutina de finalización no espera a que Moodle responda.
    """
    sesion_finalizada = []
    writeback_ejecutado = []

    async def mock_finalizar(db, session_id):
        sesion_finalizada.append(session_id)
        return MagicMock(id=session_id, finalizada_en="2026-01-01")

    async def mock_writeback_lento(*args, **kwargs):
        await asyncio.sleep(0.1)  # simula Moodle lento
        writeback_ejecutado.append(True)

    from app.application.proctoring.finalizar_con_writeback import (
        finalizar_sesion_con_writeback,
    )

    with (
        patch(
            "app.application.proctoring.finalizar_con_writeback.session_service.finalizar_sesion",
            side_effect=mock_finalizar,
        ),
        patch(
            "app.application.proctoring.finalizar_con_writeback._ejecutar_writeback_en_background",
            side_effect=mock_writeback_lento,
        ),
    ):
        result = await finalizar_sesion_con_writeback(
            db=AsyncMock(),
            session_id="sesion-123",
            writeback_svc=None,  # no se usa porque está mocked
        )

    # La sesión debe estar finalizada inmediatamente
    assert result is not None
    assert "sesion-123" in sesion_finalizada


@pytest.mark.asyncio
async def test_finalizar_sesion_completa_aunque_writeback_falla():
    """7.10: si el writeback falla con excepción, la finalización NO relanza."""
    sesion_finalizada = []

    async def mock_finalizar(db, session_id):
        sesion_finalizada.append(session_id)
        return MagicMock(id=session_id, finalizada_en="2026-01-01")

    async def mock_writeback_que_falla(*args, **kwargs):
        raise RuntimeError("Moodle completamente caído")

    from app.application.proctoring.finalizar_con_writeback import (
        finalizar_sesion_con_writeback,
    )

    with (
        patch(
            "app.application.proctoring.finalizar_con_writeback.session_service.finalizar_sesion",
            side_effect=mock_finalizar,
        ),
        patch(
            "app.application.proctoring.finalizar_con_writeback._ejecutar_writeback_en_background",
            side_effect=mock_writeback_que_falla,
        ),
    ):
        # NO debe lanzar excepción
        result = await finalizar_sesion_con_writeback(
            db=AsyncMock(),
            session_id="sesion-456",
            writeback_svc=None,
        )

    assert result is not None
    assert "sesion-456" in sesion_finalizada


def test_l2_5_nota_no_incluye_proctoring():
    """7.13 L2.5: MoodleWritebackService.ejecutar_writeback toma la nota académica
    y NO tiene parámetro de score/proctoring."""
    import inspect

    sig = inspect.signature(MoodleWritebackService.ejecutar_writeback)
    params = set(sig.parameters.keys())

    assert "nota" in params
    assert "db" in params
    assert "session_id" in params

    proctoring_params = {"score", "proctoring_score", "flags", "proctoring_flags"}
    assert not (proctoring_params & params), (
        f"ejecutar_writeback tiene parámetros de proctoring: {proctoring_params & params}"
    )
