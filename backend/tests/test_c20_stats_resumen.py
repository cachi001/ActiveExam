"""C-20 (re-alcanzado): servicio de estadísticas institucionales standalone.

DB real (DATABASE_URL). Sin mocks de DB (regla dura). Verifica los conteos, las
personas en riesgo (score >= umbral) y la distribución de scores sobre datos que YA
existen — sin depender de C-13/C-16.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.stats.resumen_service import obtener_resumen
from app.infrastructure.auth.verifiers import encode_hs256
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    ConfiguracionSistemaModel,
    EventoScoreConfigModel,
)
from app.presentation.api.v1.stats.router import create_stats_router
from tests.proctoring.conftest import (
    _TEST_JWT_AUDIENCE,
    _TEST_JWT_ISSUER,
    _TEST_JWT_SECRET,
    _build_test_jwt_validator,
)

UMBRAL = 40

_TABLES_TO_DROP = [
    "examen_contenido",
    "comision",
    "materia",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "evento_score_config",
    "configuracion_sistema",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    ConfiguracionSistemaModel.__table__,
    EventoScoreConfigModel.__table__,
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _seed(s: AsyncSession) -> None:
    await s.execute(
        text(
            "TRUNCATE examen_contenido, comision, materia, proctoring_event, "
            "proctoring_session, configuracion_sistema, evento_score_config CASCADE"
        )
    )
    s.add(ConfiguracionSistemaModel(id="global", umbral_cola_revision=UMBRAL))
    s.add(
        EventoScoreConfigModel(
            tipo_evento="rostro_ausente", severidad="alta", peso=50, activo=True
        )
    )
    # 2 materias, 1 comisión, 2 exámenes
    m1 = MateriaModel(codigo="M1", nombre="Materia 1")
    m2 = MateriaModel(codigo="M2", nombre="Materia 2")
    s.add_all([m1, m2])
    await s.flush()
    s.add(
        ComisionModel(
            materia_id=m1.id, codigo="C1", nombre="Comisión 1",
            codigo_matriculacion="M1-C1",
        )
    )
    s.add_all([ExamenContenidoModel(titulo="E1"), ExamenContenidoModel(titulo="E2")])

    # sesión 1: finalizada + 1 evento rostro_ausente (score 50 >= 40 -> en riesgo)
    ses1 = ProctoringSessionModel(modo="examen")
    ses1.finalizada_en = datetime.now(UTC)
    # sesión 2: finalizada, sin eventos (score 0)
    ses2 = ProctoringSessionModel(modo="examen")
    ses2.finalizada_en = datetime.now(UTC)
    # sesión 3: NO finalizada, sin eventos
    ses3 = ProctoringSessionModel(modo="examen")
    s.add_all([ses1, ses2, ses3])
    await s.flush()
    s.add(
        ProctoringEventModel(
            session_id=ses1.id, tipo="rostro_ausente", severidad="alta",
            ts_cliente=datetime.now(UTC),
        )
    )
    await s.commit()


@pytest.mark.asyncio
async def test_resumen_conteos_y_riesgo(session):
    """Conteos correctos + 1 sesión en riesgo (score 50 >= umbral 40)."""
    await _seed(session)

    r = await obtener_resumen(session)

    assert r.total_materias == 2
    assert r.total_comisiones == 1
    assert r.total_examenes == 2
    assert r.total_sesiones == 3
    assert r.sesiones_finalizadas == 2
    assert r.umbral_riesgo == 40
    assert r.sesiones_en_riesgo == 1  # solo ses1 (score 50)


@pytest.mark.asyncio
async def test_resumen_distribucion_scores(session):
    """La distribución ubica ses1 en 50-69 y ses2/ses3 en 0-24."""
    await _seed(session)

    r = await obtener_resumen(session)

    assert r.distribucion_scores["50-69"] == 1
    assert r.distribucion_scores["0-24"] == 2
    assert r.distribucion_scores["25-49"] == 0
    assert r.distribucion_scores["70-100"] == 0


@pytest.mark.asyncio
async def test_resumen_vacio_da_ceros(session):
    """Sin datos: ceros legítimos (no error). Degradación segura."""
    await session.execute(
        text(
            "TRUNCATE examen_contenido, comision, materia, proctoring_event, "
            "proctoring_session, configuracion_sistema, evento_score_config CASCADE"
        )
    )
    await session.commit()

    r = await obtener_resumen(session)

    assert r.total_examenes == 0
    assert r.total_sesiones == 0
    assert r.sesiones_en_riesgo == 0


# ---------------------------------------------------------------------------
# Endpoint GET /api/v1/stats/resumen (RBAC admin_sistema/coordinador)
# ---------------------------------------------------------------------------


def _token(roles) -> str:
    claims = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": "sub-stats",
        "preferred_username": "u-stats",
        "email": "s@u.edu",
        "exp": 9999999999,
        "amr": ["otp"],
        "realm_access": {"roles": list(roles)},
    }
    return encode_hs256(claims, _TEST_JWT_SECRET)


@pytest_asyncio.fixture
async def app_stats(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await _seed(s)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_stats_router(session_factory=factory), prefix="/api/v1/stats"
    )
    return app


@pytest.mark.asyncio
async def test_endpoint_resumen_admin_200(app_stats):
    async with AsyncClient(
        transport=ASGITransport(app=app_stats),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(['admin_sistema'])}"},
    ) as c:
        resp = await c.get("/api/v1/stats/resumen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_materias"] == 2
    assert body["sesiones_en_riesgo"] == 1
    assert body["umbral_riesgo"] == 40
    assert "distribucion_scores" in body


@pytest.mark.asyncio
async def test_endpoint_resumen_estudiante_403(app_stats):
    async with AsyncClient(
        transport=ASGITransport(app=app_stats),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(['estudiante'])}"},
    ) as c:
        resp = await c.get("/api/v1/stats/resumen")
    assert resp.status_code == 403, resp.text
