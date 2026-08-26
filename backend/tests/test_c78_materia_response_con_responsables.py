"""Asignar y quitar responsables NO puede dar 500 (c-78). Postgres real.

## El bug

`catalog_router.py` llamaba a TRES helpers que **no estaban definidos en ningun
lado del repo**:

    _materia_response_con_coordinadores   (5 llamadas)
    _comision_response_con_tutores        (2 llamadas)
    _validar_usuario_tutor                (1 llamada)

Python no resuelve los nombres hasta ejecutar la linea, asi que el servidor
arrancaba bien, las rutas aparecian en el OpenAPI y todo parecia normal — hasta
que alguien las usaba y se comia un 500 (`NameError`).

Los SIETE endpoints rotos eran justamente la pantalla de responsables de c-79:

    POST   /materias/{id}/reactivar
    POST   /materias/{id}/profesores
    DELETE /materias/{id}/profesores/{profesor_id}
    POST   /materias/{id}/coordinadores
    DELETE /materias/{id}/coordinadores/{coordinador_id}
    POST   /comisiones/{id}/tutores
    DELETE /comisiones/{id}/tutores/{tutor_id}

## Por que no lo agarro ningun test

Los que existian verificaban la capa de repositorio (que `agregar_profesor`
escriba la fila), donde estos helpers no participan. Nadie recorria el endpoint
de punta a punta, que es donde vive el `NameError`. Por eso estos tests pegan por
HTTP y ademas hay un barrido que busca la CLASE de bug, no este nombre puntual.
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
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
    MateriaProfesorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content import catalog_router
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/exam-content"

_TABLES_TO_DROP = [
    "materia_profesor",
    "materia_coordinador",
    "comision_tutor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    MateriaCoordinadorModel.__table__,
    MateriaProfesorModel.__table__,
]


# ---------------------------------------------------------------------------
# Barrido: la CLASE de bug, no este nombre puntual. No necesita DB.
# ---------------------------------------------------------------------------


def test_no_quedan_nombres_sin_definir_en_el_router() -> None:
    """Compila el modulo y compara los nombres que USA contra los que puede
    resolver (globales del modulo + builtins). Un nombre que no resuelve por
    ningun lado es un `NameError` esperando a que alguien pise ese endpoint.

    Es la guarda barata contra volver a mergear una funcion que se llama y no se
    escribio: corre en milisegundos y no levanta nada.
    """
    import builtins
    import symtable
    from pathlib import Path

    ruta = Path(catalog_router.__file__)
    tabla = symtable.symtable(ruta.read_text(encoding="utf-8"), str(ruta), "exec")
    conocidos = set(dir(builtins)) | set(vars(catalog_router))

    faltantes: set[str] = set()

    def revisar(simbolos: symtable.SymbolTable) -> None:
        for s in simbolos.get_symbols():
            if s.is_global() and s.get_name() not in conocidos:
                faltantes.add(s.get_name())
        for hijo in simbolos.get_children():
            revisar(hijo)

    revisar(tabla)

    assert not faltantes, (
        "nombres usados en catalog_router.py que no resuelven a nada "
        f"(NameError en runtime): {sorted(faltantes)}"
    )


# ---------------------------------------------------------------------------
# Los endpoints, de punta a punta.
# ---------------------------------------------------------------------------


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
    application.state.session_factory = factory
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix=_BASE,
    )
    return application


async def _crear_usuario(factory, rol: str) -> str:
    legajo = f"{rol}-{uuid.uuid4().hex[:6]}"
    async with factory() as s:
        u = UsuarioModel(
            username=legajo,
            email=f"{legajo}@uni.edu",
            nombre=rol.capitalize(),
            apellido=legajo,
            roles=[rol],
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_materia_y_comision(factory) -> tuple[str, str]:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=sufijo,
        )
        s.add(comision)
        await s.commit()
        return materia.id, comision.id


def _admin(app, subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], subject=subject),
    )


async def test_asignar_y_quitar_un_PROFESOR_devuelve_la_materia_actualizada(
    app, factory
) -> None:
    admin = await _crear_usuario(factory, "admin_sistema")
    profesor = await _crear_usuario(factory, "profesor")
    materia_id, _ = await _crear_materia_y_comision(factory)

    async with _admin(app, admin) as c:
        alta = await c.post(
            f"{_BASE}/materias/{materia_id}/profesores", json={"profesor_id": profesor}
        )
        assert alta.status_code != 500, alta.text  # el NameError daba 500
        assert alta.status_code == 201, alta.text
        assert [p["id"] for p in alta.json()["profesores"]] == [profesor]

        baja = await c.delete(f"{_BASE}/materias/{materia_id}/profesores/{profesor}")
        assert baja.status_code == 200, baja.text
        assert baja.json()["profesores"] == []


async def test_asignar_y_quitar_un_COORDINADOR_devuelve_la_materia_actualizada(
    app, factory
) -> None:
    admin = await _crear_usuario(factory, "admin_sistema")
    coordinador = await _crear_usuario(factory, "coordinador")
    materia_id, _ = await _crear_materia_y_comision(factory)

    async with _admin(app, admin) as c:
        alta = await c.post(
            f"{_BASE}/materias/{materia_id}/coordinadores",
            json={"coordinador_id": coordinador},
        )
        assert alta.status_code != 500, alta.text  # el NameError daba 500
        assert alta.status_code == 201, alta.text
        assert [x["id"] for x in alta.json()["coordinadores"]] == [coordinador]

        baja = await c.delete(
            f"{_BASE}/materias/{materia_id}/coordinadores/{coordinador}"
        )
        assert baja.status_code == 200, baja.text
        assert baja.json()["coordinadores"] == []


async def test_asignar_y_quitar_un_TUTOR_devuelve_la_comision_actualizada(
    app, factory
) -> None:
    admin = await _crear_usuario(factory, "admin_sistema")
    tutor = await _crear_usuario(factory, "tutor")
    _, comision_id = await _crear_materia_y_comision(factory)

    async with _admin(app, admin) as c:
        alta = await c.post(
            f"{_BASE}/comisiones/{comision_id}/tutores", json={"tutor_id": tutor}
        )
        assert alta.status_code != 500, alta.text  # el NameError daba 500
        assert alta.status_code == 201, alta.text
        assert [t["id"] for t in alta.json()["tutores"]] == [tutor]

        baja = await c.delete(f"{_BASE}/comisiones/{comision_id}/tutores/{tutor}")
        assert baja.status_code == 200, baja.text
        assert baja.json()["tutores"] == []


async def test_no_se_puede_asignar_como_tutor_a_alguien_que_no_lo_es(
    app, factory
) -> None:
    """La FK sola dejaría asignar a cualquier usuario —un alumno, por ejemplo—
    como tutor de una comisión, y ahí la pertenencia deja de significar algo."""
    admin = await _crear_usuario(factory, "admin_sistema")
    alumno = await _crear_usuario(factory, "estudiante")
    _, comision_id = await _crear_materia_y_comision(factory)

    async with _admin(app, admin) as c:
        resp = await c.post(
            f"{_BASE}/comisiones/{comision_id}/tutores", json={"tutor_id": alumno}
        )

    assert resp.status_code == 422, resp.text


async def test_reactivar_una_materia_dada_de_baja_no_revienta(app, factory) -> None:
    admin = await _crear_usuario(factory, "admin_sistema")
    materia_id, _ = await _crear_materia_y_comision(factory)

    async with _admin(app, admin) as c:
        await c.delete(f"{_BASE}/materias/{materia_id}")
        resp = await c.post(f"{_BASE}/materias/{materia_id}/reactivar")

    assert resp.status_code != 500, resp.text
    assert resp.status_code == 200, resp.text
    assert resp.json()["activa"] is True
