"""2.5 RED → 2.6 GREEN: tests del endpoint admin-only de importación Moodle XML.

- Sin rol admin_examenes → 403
- Admin + MFA → 201 con reporte
- XML inválido → 422
- XML vacío (sin preguntas soportadas) → 400

Requieren DATABASE_URL para los tests 201.
Los tests de 403/auth no necesitan DB.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.application.exam_content.import_service import ImportacionMoodleService
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

FIXTURES = Path(__file__).parent / "fixtures" / "moodle"
_NEW_TABLES = ("opcion_respuesta", "pregunta_examen", "examen_contenido")


# ---------------------------------------------------------------------------
# Fixtures sin DB (para tests de auth 403)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_noauth():
    """App mínima con el router de exam_content pero sin DB — para tests 403."""
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_content_router(session_factory=None)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_noauth(app_noauth):
    async with AsyncClient(
        transport=ASGITransport(app=app_noauth), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures con DB (para tests 201/400/422)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_admin(db_engine):
    """App con router de exam_content + DB real + JWT de test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_content_router(session_factory=factory)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"], mfa=True),
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# 2.5 RED — tests de autorización (no requieren DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_sin_token_401(client_noauth):
    """Sin Authorization header → 401 (o 403 según policy)."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    resp = await client_noauth.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("exam.xml", xml, "application/xml")},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_import_estudiante_403(client_noauth):
    """Rol 'estudiante' → 403 (sin admin_examenes)."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    resp = await client_noauth.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("exam.xml", xml, "application/xml")},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2.6 GREEN — tests funcionales (requieren DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_admin_201(client_admin):
    """Admin + MFA → 201 con reporte de importación."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("exam.xml", xml, "application/xml")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["importadas"] == 2
    assert "examen_id" in data
    assert isinstance(data["omitidas"], list)


@pytest.mark.asyncio
async def test_import_con_titulo_201(client_admin):
    """Admin puede enviar título opcional."""
    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={
            "file": ("exam.xml", xml, "application/xml"),
            "titulo": (None, "Mi examen personalizado"),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["importadas"] == 2


@pytest.mark.asyncio
async def test_import_con_moodle_target_201(client_admin, db_engine):
    """D12: admin puede enviar moodle_courseid/cmid en el form; se persisten."""
    from sqlalchemy import select

    xml = (FIXTURES / "sample_export_multichoice_truefalse.xml").read_bytes()
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={
            "file": ("exam.xml", xml, "application/xml"),
            "moodle_courseid": (None, "555"),
            "moodle_cmid": (None, "13"),
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        row = (
            await s.execute(
                select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one()
        assert row.moodle_courseid == 555
        assert row.moodle_cmid == 13


@pytest.mark.asyncio
async def test_import_xml_invalido_422(client_admin):
    """XML malformado → 422."""
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("bad.xml", b"not xml <<<", "application/xml")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_xml_vacio_400(client_admin):
    """XML sin preguntas soportadas → 400."""
    xml = (FIXTURES / "invalid_empty.xml").read_bytes()
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("empty.xml", xml, "application/xml")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_mixto_omitidas_reportadas(client_admin):
    """XML mixto: soportados + no soportados → omitidas en el reporte."""
    xml = (FIXTURES / "mixed_unsupported.xml").read_bytes()
    resp = await client_admin.post(
        "/api/v1/exam-content/moodle-import",
        files={"file": ("mixed.xml", xml, "application/xml")},
    )
    assert resp.status_code == 201
    data = resp.json()
    # C-74 agregó soporte de cloze: se importa multichoice + cloze, omite essay.
    assert data["importadas"] == 2
    assert len(data["omitidas"]) == 1
