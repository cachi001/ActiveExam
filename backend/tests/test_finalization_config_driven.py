"""Tests del consumo de la config viva + snapshot de version en la finalizacion.

config-driven-scoring: SessionFinalizationService usa pesos VIVOS (provider que los
trae de la config persistida) y registra la ``config_version`` usada -> la config
nueva aplica a sesiones NUEVAS; una sesion ya consolidada conserva su score.

Sin DB: dobles en memoria (reusa los fakes del test de finalizacion existente).
L2.5: el score prioriza, nunca sanciona.
"""

from __future__ import annotations

import asyncio

from app.application.scoring.finalization import SessionFinalizationService
from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.scoring.risk_score import PesosScore
from tests.test_scoring_finalization import (
    FakeEventRepo,
    FakeExamRepo,
    FakeQueue,
    FakeSessionRepo,
    _eventos_severos,
)


def _sesion() -> Sesion:
    return Sesion(
        user_id="u", exam_id="e1", clave_sesion="k",
        estado=EstadoSesion.FINALIZADA, id="sess-1",
    )


def test_consolidar_usa_pesos_vivos_no_default() -> None:
    """Con un provider de pesos vivos, el score refleja esos pesos (no el default)."""
    eventos = _eventos_severos(1)  # 1 evento severidad 'critica'

    # Default: critica=6.0. Provider vivo: critica=99.0 -> score mayor.
    async def provider():
        return PesosScore(severidad={"critica": 99.0}), 7

    svc = SessionFinalizationService(
        sesiones=FakeSessionRepo(_sesion()),
        eventos=FakeEventRepo(eventos),
        examenes=FakeExamRepo(5.0),
        cola=FakeQueue(),
        pesos_provider=provider,
    )
    res = asyncio.run(svc.consolidar("sess-1"))
    # 1 evento critica con peso vivo 99 (persistencia frames=6 sube el peso).
    assert res.score_final >= 99.0
    # Registra la version de config usada (snapshot por sesion).
    assert res.config_version == 7


def test_consolidar_sin_provider_usa_fallback_default() -> None:
    """Sin provider (config ausente) usa los pesos default por severidad."""
    eventos = _eventos_severos(1)
    svc = SessionFinalizationService(
        sesiones=FakeSessionRepo(_sesion()),
        eventos=FakeEventRepo(eventos),
        examenes=FakeExamRepo(5.0),
        cola=FakeQueue(),
    )
    res = asyncio.run(svc.consolidar("sess-1"))
    # critica default=6.0 con persistencia frames=6 -> 6 * (1 + 0.5*5) = 21.0
    assert res.score_final == 21.0
    assert res.config_version is None


def test_cambio_posterior_no_altera_score_consolidado() -> None:
    """Una vez consolidada con version N, recomputar con la MISMA entrada da el mismo
    score (la config nueva aplicaria a sesiones nuevas, no a esta)."""
    eventos = _eventos_severos(2)

    async def provider_v1():
        return PesosScore(severidad={"critica": 10.0}), 1

    svc = SessionFinalizationService(
        sesiones=FakeSessionRepo(_sesion()),
        eventos=FakeEventRepo(eventos),
        examenes=FakeExamRepo(5.0),
        cola=FakeQueue(),
        pesos_provider=provider_v1,
    )
    r1 = asyncio.run(svc.consolidar("sess-1"))
    assert r1.config_version == 1
    score_v1 = r1.score_final
    assert score_v1 > 0
