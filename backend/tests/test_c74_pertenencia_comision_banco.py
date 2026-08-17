"""C-74 post-cierre: aislamiento por comisión entre docentes de la MISMA materia.

Tres bugs reales encontrados en vivo (E2E, no en tests — cero cobertura previa):

1. `_exigir_pertenencia_materia` (banco de preguntas) rechazaba con falso
   negativo a un docente real que dicta una comisión distinta de la que
   `docente_de_materia()` (``.limit(1)`` sin filtrar por quién pregunta)
   devolvía primero.

2. `crear-desde-banco` solo validaba pertenencia a la MATERIA — un docente que
   dicta la Comisión 2 podía crear un examen apuntando a la Comisión 1 de OTRO
   docente, con solo compartir materia/banco.

3. `POST /{examen_id}/comision` (asociar examen ya importado a una comisión)
   no tenía NINGÚN chequeo de pertenencia — cualquier docente con
   `gestionar_academico` podía asociar cualquier examen a cualquier comisión.

DB real (DATABASE_URL). Sin mocks de DB. Sigue el mismo patrón que
``test_c73_pertenencia_docente.py``.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_banco",
    "pregunta_banco",
    "categoria_pregunta",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    CategoriaPreguntaModel.__table__,
    PreguntaBancoModel.__table__,
    OpcionBancoModel.__table__,
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
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_docente(factory, legajo: str) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=legajo,
            email=f"{legajo.lower()}@uni.edu",
            nombre="Docente",
            apellido=legajo,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_materia_con_dos_comisiones(factory, docente_c1: str, docente_c2: str | None):
    """Una materia con 2 comisiones: C1 (docente_c1) y C2 (docente_c2).

    Crea C1 primero a propósito — es el caso que gatillaba el bug 1
    (``.limit(1)`` devolvía el docente de la primera comisión creada)."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        c1 = ComisionModel(
            materia_id=materia.id, codigo=f"C1-{sufijo}", nombre="Comisión 1",
            codigo_matriculacion=f"K1-{sufijo}", docente_id=docente_c1,
        )
        s.add(c1)
        await s.flush()
        c2 = ComisionModel(
            materia_id=materia.id, codigo=f"C2-{sufijo}", nombre="Comisión 2",
            codigo_matriculacion=f"K2-{sufijo}", docente_id=docente_c2,
        )
        s.add(c2)
        await s.flush()
        materia_id, c1_id, c2_id = materia.id, c1.id, c2.id
        await s.commit()
    return materia_id, c1_id, c2_id


async def _crear_examen_importado(factory, comision_id: str | None = None) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(titulo="Examen importado", comision_id=comision_id)
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


def _client(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


# ---------------------------------------------------------------------------
# Bug 1: docente de una comisión NO-primera de la materia no debe ser rechazado
# al operar el banco de preguntas (categorías) de su propia materia.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_de_la_segunda_comision_puede_crear_categoria_en_su_materia(app, factory):
    """RED→GREEN: antes, docente_de_materia() devolvía el docente de C1 (creada
    primero) y comparaba contra el principal — el docente de C2 era rechazado."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1-{uuid.uuid4().hex[:4]}")
    docente_c2 = await _crear_docente(factory, f"DOC-C2-{uuid.uuid4().hex[:4]}")
    materia_id, _c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2
    )

    async with _client(app, ["tutor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/categorias",
            json={"materia_id": materia_id, "nombre": "Unidad 1"},
        )

    assert resp.status_code == 201, (
        "El docente de la Comisión 2 fue rechazado al operar el banco de SU "
        f"propia materia. Respuesta: {resp.status_code} {resp.text}"
    )


# ---------------------------------------------------------------------------
# Bug 2: crear-desde-banco debe validar el comision_id puntual, no solo la materia.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_no_puede_crear_examen_para_comision_ajena_de_su_misma_materia(app, factory):
    """RED→GREEN: docente de C2 no puede crear un examen que apunte a C1 (de otro
    docente), aunque comparta materia/banco con esa comisión."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1B-{uuid.uuid4().hex[:4]}")
    docente_c2 = await _crear_docente(factory, f"DOC-C2B-{uuid.uuid4().hex[:4]}")
    materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2
    )

    async with _client(app, ["tutor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/crear-desde-banco",
            json={
                "titulo": "Examen colado",
                "materia_id": materia_id,
                "comision_id": c1_id,
                "sorteo": [{"categoria_id": None, "cantidad": 1}],
            },
        )

    assert resp.status_code == 403, (
        "Un docente de OTRA comisión pudo crear un examen apuntando a una "
        f"comisión ajena de la misma materia. Respuesta: {resp.status_code} {resp.text}"
    )
    assert resp.json()["detail"]["error"] == "comision_ajena"


@pytest.mark.asyncio
async def test_docente_si_puede_crear_examen_para_su_propia_comision(app, factory):
    """Triangulación: el mismo docente SÍ puede crear un examen para su propia
    comisión (falla más adelante por falta de preguntas en el banco — 422/500 son
    aceptables acá, lo que NO debe pasar es un 403 de pertenencia)."""
    docente_c2 = await _crear_docente(factory, f"DOC-C2C-{uuid.uuid4().hex[:4]}")
    materia_id, _c1_id, c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1=None, docente_c2=docente_c2
    )

    async with _client(app, ["tutor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/crear-desde-banco",
            json={
                "titulo": "Examen propio",
                "materia_id": materia_id,
                "comision_id": c2_id,
                "sorteo": [{"categoria_id": None, "cantidad": 1}],
            },
        )

    assert resp.status_code != 403, resp.text


# ---------------------------------------------------------------------------
# Bug 3: asociar examen importado a comisión exige pertenencia sobre la comisión.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_no_puede_asociar_examen_a_comision_ajena(app, factory):
    """RED→GREEN: antes este endpoint no tenía NINGÚN chequeo de pertenencia."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1D-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-X-{uuid.uuid4().hex[:4]}")
    _materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2=None
    )
    examen_id = await _crear_examen_importado(factory)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/comision",
            json={"comision_id": c1_id},
        )

    assert resp.status_code == 403, (
        "Cualquier docente pudo asociar un examen importado a una comisión "
        f"ajena. Respuesta: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_asociar_examen_a_su_comision(app, factory):
    """Triangulación: el docente titular de la comisión sí puede asociarla."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1E-{uuid.uuid4().hex[:4]}")
    _materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2=None
    )
    examen_id = await _crear_examen_importado(factory)

    async with _client(app, ["tutor"], subject=docente_c1) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/comision",
            json={"comision_id": c1_id},
        )

    assert resp.status_code == 200, resp.text
