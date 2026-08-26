"""c-78 §18.4 — avisar que falta un responsable ANTES de que el alumno rinda.

## El problema que esto cierra

Verificado en producción el 26/8/2026: las tres materias estaban sin profesor y
sin coordinador, y las cinco comisiones sin tutor. Con eso se puede crear una
materia, sus comisiones, sus exámenes, y que los alumnos rindan de punta a punta
**sin que nada advierta que no hay quién firme las notas**. El write-back sale
con la credencial del TUTOR de la comisión: sin tutor devuelve `sin_docente` y la
nota se retiene. Se descubre al final, con el examen ya rendido.

El aviso tiene que llegar donde se arma la estructura y en el detalle del examen.
Estos tests cubren los dos datos que la UI necesita para poder darlo:

1. `GET /{examen_id}/resumen` informa si la comisión del examen quedó sin tutor.
2. `GET /materias` devuelve los PROFESORES además de los coordinadores (sin ellos
   la pantalla no puede decir que la materia no tiene ningún responsable).

Postgres real, sin mocks: el dato sale de tres tablas puente y un JOIN mal escrito
es exactamente la clase de error que un mock no encuentra.
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
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from app.presentation.api.v1.exam_content.taking_router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/exam-content"

_TABLES_TO_DROP = [
    "inscripcion",
    "examen_contenido",
    "materia_profesor",
    "materia_coordinador",
    "comision_tutor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    ComisionTutorModel.__table__,
    MateriaCoordinadorModel.__table__,
    MateriaProfesorModel.__table__,
    InscripcionModel.__table__,
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
    application.state.session_factory = factory
    # Los DOS routers, igual que producción: el catálogo monta las escrituras y
    # `GET /materias` vive en el de rendición. Con uno solo, el listado da 405.
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix=_BASE,
    )
    application.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=None),
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


async def _crear_materia_comision_y_examen(factory) -> tuple[str, str, str]:
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
        await s.flush()
        examen = ExamenContenidoModel(
            titulo=f"Parcial {sufijo}", comision_id=comision.id
        )
        s.add(examen)
        await s.commit()
        return materia.id, comision.id, examen.id


def _admin(app, subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], subject=subject),
    )


# ---------------------------------------------------------------------------
# 1. El detalle del examen tiene que poder avisar que la nota no va a salir.
# ---------------------------------------------------------------------------


async def test_resumen_avisa_cuando_la_comision_del_examen_no_tiene_tutor(
    app, factory
) -> None:
    """Sin tutor, el write-back de ESTE examen va a responder `sin_docente`. El
    encabezado del detalle lo dice antes, no después de que el alumno rindió."""
    admin = await _crear_usuario(factory, "admin_sistema")
    _, _, examen_id = await _crear_materia_comision_y_examen(factory)

    async with _admin(app, admin) as c:
        resp = await c.get(f"{_BASE}/{examen_id}/resumen")

    assert resp.status_code == 200, resp.text
    assert resp.json()["comision_sin_tutor"] is True


async def test_resumen_no_avisa_cuando_la_comision_tiene_tutor(app, factory) -> None:
    """Triangulación: con tutor asignado el aviso se apaga. Si quedara prendido,
    la pantalla gritaría en el caso normal y nadie volvería a mirarlo."""
    admin = await _crear_usuario(factory, "admin_sistema")
    tutor = await _crear_usuario(factory, "tutor")
    _, comision_id, examen_id = await _crear_materia_comision_y_examen(factory)

    async with _admin(app, admin) as c:
        alta = await c.post(
            f"{_BASE}/comisiones/{comision_id}/tutores", json={"tutor_id": tutor}
        )
        assert alta.status_code == 201, alta.text
        resp = await c.get(f"{_BASE}/{examen_id}/resumen")

    assert resp.status_code == 200, resp.text
    assert resp.json()["comision_sin_tutor"] is False


async def test_resumen_de_examen_sin_comision_no_afirma_nada_sobre_el_tutor(
    app, factory
) -> None:
    """Un examen sin comisión (D11: la asociación es opcional) no tiene tutor que
    buscar. `null`, no `true`: "no aplica" no es lo mismo que "falta alguien", y
    la UI ya muestra "Sin comisión" por su cuenta."""
    admin = await _crear_usuario(factory, "admin_sistema")
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=f"Suelto {sufijo}", comision_id=None)
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()

    async with _admin(app, admin) as c:
        resp = await c.get(f"{_BASE}/{examen_id}/resumen")

    assert resp.status_code == 200, resp.text
    assert resp.json()["comision_sin_tutor"] is None


# ---------------------------------------------------------------------------
# 2. La pantalla de estructura tiene que poder ver que la materia está huérfana.
# ---------------------------------------------------------------------------


async def test_listar_materias_devuelve_los_profesores_no_solo_los_coordinadores(
    app, factory
) -> None:
    """`MateriaResponse` declara `profesores` desde c-78, pero el listado no los
    llenaba: devolvía `[]` incluso con profesor asignado. Con ese dato faltando,
    la pantalla no puede distinguir "sin ningún responsable" de "sin coordinador",
    que es justo la distinción que el aviso necesita."""
    admin = await _crear_usuario(factory, "admin_sistema")
    profesor = await _crear_usuario(factory, "profesor")
    materia_id, _, _ = await _crear_materia_comision_y_examen(factory)

    async with _admin(app, admin) as c:
        alta = await c.post(
            f"{_BASE}/materias/{materia_id}/profesores", json={"profesor_id": profesor}
        )
        assert alta.status_code == 201, alta.text
        listado = await c.get(f"{_BASE}/materias")

    assert listado.status_code == 200, listado.text
    materia = next(m for m in listado.json() if m["id"] == materia_id)
    assert [p["id"] for p in materia["profesores"]] == [profesor]


async def test_listar_materias_sin_responsables_las_devuelve_vacias(app, factory) -> None:
    """Triangulación: la materia recién creada no tiene a nadie. Las dos listas
    vacías son la señal exacta que la pantalla pinta como "sin responsable"."""
    admin = await _crear_usuario(factory, "admin_sistema")
    materia_id, _, _ = await _crear_materia_comision_y_examen(factory)

    async with _admin(app, admin) as c:
        listado = await c.get(f"{_BASE}/materias")

    assert listado.status_code == 200, listado.text
    materia = next(m for m in listado.json() if m["id"] == materia_id)
    assert materia["profesores"] == []
    assert materia["coordinadores"] == []
