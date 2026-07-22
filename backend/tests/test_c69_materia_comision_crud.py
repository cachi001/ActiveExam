"""CRUD admin de Materias y Comisiones independiente del import (C-69, D11).

Endpoints (admin-only, SIN MFA — mismo guard de router que el import):
- POST  /api/v1/exam-content/materias                       → crear materia
- PATCH /api/v1/exam-content/materias/{materia_id}          → editar nombre de materia
- POST  /api/v1/exam-content/materias/{materia_id}/comisiones → crear comisión
- PATCH /api/v1/exam-content/comisiones/{comision_id}       → editar comisión

Reglas verificadas (por endpoint: happy path + errores):
- Admin → 201/200; no-admin (estudiante) → 403.
- 409 'duplicado' al repetir codigo de materia / (materia_id, codigo) de comisión.
- 404 'materia_no_encontrada' / 'comision_no_encontrada' cuando el id no existe.
- 422 'validacion_dominio' con codigo/nombre vacíos; 422 extra='forbid'.
- PATCH persiste de verdad (se re-lee desde la DB).
- codigo EDITABLE: el PATCH permite cambiar el codigo; duplicado → 409 (C-72 §15).

Requieren DATABASE_URL para los tests funcionales; los tests de 403 no necesitan DB.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    UsuarioModel,
)
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_NEW_TABLES = (
    "inscripcion",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
    "usuario",
)
_FK_EXAMEN_COMISION = "fk_examen_contenido_comision"
_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Fixtures sin DB (tests de auth 403)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_noauth():
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=None), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures con DB
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
                UsuarioModel.__table__,
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                InscripcionModel.__table__,
            ],
        )
        await conn.execute(
            text(
                f'ALTER TABLE examen_contenido ADD CONSTRAINT "{_FK_EXAMEN_COMISION}" '
                "FOREIGN KEY (comision_id) REFERENCES comision(id) ON DELETE SET NULL"
            )
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app_admin(factory):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    app.include_router(
        create_exam_taking_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"], mfa=False),
    ) as c:
        yield c


async def _crear_materia(client_admin, codigo: str, nombre: str = "Materia") -> str:
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": codigo, "nombre": nombre},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _crear_comision(
    client_admin, materia_id: str, codigo: str, nombre: str = "Comisión", **extra
) -> dict:
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": codigo, "nombre": nombre, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# auth (sin DB) — no-admin → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_materia_estudiante_403(client_noauth):
    resp = await client_noauth.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "M1", "nombre": "Mat"},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_actualizar_materia_estudiante_403(client_noauth):
    resp = await client_noauth.patch(
        f"/api/v1/exam-content/materias/{_INEXISTENTE}",
        json={"nombre": "Nuevo"},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_crear_comision_estudiante_403(client_noauth):
    resp = await client_noauth.post(
        f"/api/v1/exam-content/materias/{_INEXISTENTE}/comisiones",
        json={"codigo": "C1", "nombre": "Com"},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_actualizar_comision_estudiante_403(client_noauth):
    resp = await client_noauth.patch(
        f"/api/v1/exam-content/comisiones/{_INEXISTENTE}",
        json={"nombre": "Com"},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /materias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_materia_201(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "ALG-CRUD-1", "nombre": "Álgebra"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"]
    assert data["codigo"] == "ALG-CRUD-1"
    assert data["nombre"] == "Álgebra"
    # id/codigo/nombre + activa (C-72 §17); una materia nueva nace activa.
    assert set(data.keys()) == {"id", "codigo", "nombre", "activa"}
    assert data["activa"] is True


@pytest.mark.asyncio
async def test_crear_materia_codigo_duplicado_409(client_admin):
    await _crear_materia(client_admin, "DUP-MAT-1", "Una")
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "DUP-MAT-1", "nombre": "Otra"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "duplicado"


@pytest.mark.asyncio
async def test_crear_materia_codigo_vacio_422(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "   ", "nombre": "Mat"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "validacion_dominio"


@pytest.mark.asyncio
async def test_crear_materia_nombre_vacio_422(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "VAC-NOM-1", "nombre": ""},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "validacion_dominio"


@pytest.mark.asyncio
async def test_crear_materia_extra_forbid_422(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias",
        json={"codigo": "EXF-1", "nombre": "Mat", "desconocido": 1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /materias/{materia_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actualizar_materia_200_persiste(client_admin):
    materia_id = await _crear_materia(client_admin, "UPD-MAT-1", "Nombre viejo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}",
        json={"nombre": "Nombre nuevo"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == materia_id
    assert data["codigo"] == "UPD-MAT-1"  # sin codigo en el body → se preserva
    assert data["nombre"] == "Nombre nuevo"

    # Re-lectura: el cambio se persistió en la DB.
    listado = await client_admin.get("/api/v1/exam-content/materias")
    materias = {m["id"]: m for m in listado.json()}
    assert materias[materia_id]["nombre"] == "Nombre nuevo"
    assert materias[materia_id]["codigo"] == "UPD-MAT-1"


@pytest.mark.asyncio
async def test_actualizar_materia_inexistente_404(client_admin):
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{_INEXISTENTE}",
        json={"nombre": "X"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "materia_no_encontrada"


@pytest.mark.asyncio
async def test_actualizar_materia_nombre_vacio_422(client_admin):
    materia_id = await _crear_materia(client_admin, "UPD-VAC-1", "Algo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}",
        json={"nombre": "   "},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "validacion_dominio"


@pytest.mark.asyncio
async def test_actualizar_materia_codigo_editable_200(client_admin):
    """El codigo AHORA es editable: PATCH con codigo nuevo libre → 200 y persiste."""
    materia_id = await _crear_materia(client_admin, "UPD-COD-1", "Algo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}",
        json={"nombre": "Algo", "codigo": "UPD-COD-2"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["codigo"] == "UPD-COD-2"

    # Re-lectura: el codigo nuevo quedó persistido.
    listado = await client_admin.get("/api/v1/exam-content/materias")
    materias = {m["id"]: m for m in listado.json()}
    assert materias[materia_id]["codigo"] == "UPD-COD-2"


@pytest.mark.asyncio
async def test_actualizar_materia_codigo_duplicado_409(client_admin):
    """Editar el codigo a uno ya en uso por OTRA materia → 409 'duplicado'."""
    await _crear_materia(client_admin, "UPD-DUP-A", "A")
    materia_b = await _crear_materia(client_admin, "UPD-DUP-B", "B")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_b}",
        json={"nombre": "B", "codigo": "UPD-DUP-A"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "duplicado"


@pytest.mark.asyncio
async def test_actualizar_materia_sin_codigo_preserva_200(client_admin):
    """PATCH con solo nombre (sin codigo) preserva el codigo vigente → 200."""
    materia_id = await _crear_materia(client_admin, "UPD-PRE-1", "Nombre viejo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}",
        json={"nombre": "Nombre nuevo"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["codigo"] == "UPD-PRE-1"  # preservado


# ---------------------------------------------------------------------------
# POST /materias/{materia_id}/comisiones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_comision_201(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-COM-1", "Mat")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": "C-1", "nombre": "Comisión 1", "periodo": "1C", "anio": 2026},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"]
    assert data["materia_id"] == materia_id
    assert data["codigo"] == "C-1"
    assert data["nombre"] == "Comisión 1"
    assert data["periodo"] == "1C"
    assert data["anio"] == 2026


@pytest.mark.asyncio
async def test_crear_comision_periodo_anio_opcionales_201(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-COM-OPC", "Mat")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": "C-OPC", "nombre": "Sin periodo"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["periodo"] is None
    assert data["anio"] is None


@pytest.mark.asyncio
async def test_crear_comision_materia_inexistente_404(client_admin):
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{_INEXISTENTE}/comisiones",
        json={"codigo": "C-NX", "nombre": "Com"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "materia_no_encontrada"


@pytest.mark.asyncio
async def test_crear_comision_duplicada_409(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-DUP-COM", "Mat")
    await _crear_comision(client_admin, materia_id, "C-DUP", "Primera")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": "C-DUP", "nombre": "Segunda"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "duplicado"


@pytest.mark.asyncio
async def test_crear_comision_mismo_codigo_otra_materia_201(client_admin):
    """La unicidad es (materia_id, codigo): mismo codigo en otra materia se permite."""
    m1 = await _crear_materia(client_admin, "MAT-X-1", "Mat 1")
    m2 = await _crear_materia(client_admin, "MAT-X-2", "Mat 2")
    await _crear_comision(client_admin, m1, "C-SHARE", "En m1")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{m2}/comisiones",
        json={"codigo": "C-SHARE", "nombre": "En m2"},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_crear_comision_codigo_vacio_422(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-COM-VAC", "Mat")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": "", "nombre": "Com"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "validacion_dominio"


@pytest.mark.asyncio
async def test_crear_comision_extra_forbid_422(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-COM-EXF", "Mat")
    resp = await client_admin.post(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones",
        json={"codigo": "C", "nombre": "Com", "desconocido": 1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /comisiones/{comision_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actualizar_comision_200_persiste(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-UPD-COM", "Mat")
    comision = await _crear_comision(
        client_admin, materia_id, "C-UPD", "Viejo", periodo="1C", anio=2025
    )
    comision_id = comision["id"]

    resp = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{comision_id}",
        json={"nombre": "Nuevo", "periodo": "2C", "anio": 2027},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == comision_id
    assert data["materia_id"] == materia_id  # materia inmutable
    assert data["codigo"] == "C-UPD"  # codigo inmutable
    assert data["nombre"] == "Nuevo"
    assert data["periodo"] == "2C"
    assert data["anio"] == 2027

    # Re-lectura desde la DB: el cambio se persistió.
    listado = await client_admin.get(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones"
    )
    comisiones = {c["id"]: c for c in listado.json()}
    assert comisiones[comision_id]["nombre"] == "Nuevo"
    assert comisiones[comision_id]["periodo"] == "2C"
    assert comisiones[comision_id]["anio"] == 2027
    assert comisiones[comision_id]["codigo"] == "C-UPD"


@pytest.mark.asyncio
async def test_actualizar_comision_a_nulos_persiste(client_admin):
    """periodo/anio se pueden limpiar a null en el PATCH."""
    materia_id = await _crear_materia(client_admin, "MAT-UPD-NUL", "Mat")
    comision = await _crear_comision(
        client_admin, materia_id, "C-NUL", "Con datos", periodo="1C", anio=2025
    )
    comision_id = comision["id"]

    resp = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{comision_id}",
        json={"nombre": "Sin datos", "periodo": None, "anio": None},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["periodo"] is None
    assert data["anio"] is None


@pytest.mark.asyncio
async def test_actualizar_comision_inexistente_404(client_admin):
    resp = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{_INEXISTENTE}",
        json={"nombre": "X"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "comision_no_encontrada"


@pytest.mark.asyncio
async def test_actualizar_comision_nombre_vacio_422(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-UPD-VAC", "Mat")
    comision = await _crear_comision(client_admin, materia_id, "C-VAC", "Algo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{comision['id']}",
        json={"nombre": "   "},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "validacion_dominio"


@pytest.mark.asyncio
async def test_actualizar_comision_extra_forbid_422(client_admin):
    materia_id = await _crear_materia(client_admin, "MAT-UPD-EXF", "Mat")
    comision = await _crear_comision(client_admin, materia_id, "C-EXF", "Algo")
    resp = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{comision['id']}",
        json={"nombre": "Nuevo", "codigo": "OTRO"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /materias/{id} y /comisiones/{id} — borrado solo si 100% vacío (C-72 §16)
# ---------------------------------------------------------------------------


async def _insertar_examen(factory, comision_id: str) -> None:
    async with factory() as s:
        await s.execute(
            text("INSERT INTO examen_contenido (titulo, comision_id) VALUES (:t, :c)"),
            {"t": "Examen de prueba", "c": comision_id},
        )
        await s.commit()


async def _insertar_inscripto(factory, comision_id: str) -> None:
    async with factory() as s:
        r = await s.execute(
            text(
                "INSERT INTO usuario (id_institucional, email) VALUES (:i, :e) "
                "RETURNING id"
            ),
            {"i": f"leg-{comision_id[:8]}", "e": "a@u.edu"},
        )
        uid = r.scalar_one()
        await s.execute(
            text("INSERT INTO inscripcion (usuario_id, comision_id) VALUES (:u, :c)"),
            {"u": uid, "c": comision_id},
        )
        await s.commit()


@pytest.mark.asyncio
async def test_eliminar_materia_vacia_204(client_admin):
    materia_id = await _crear_materia(client_admin, "DEL-MAT-1", "Vacía")
    resp = await client_admin.delete(f"/api/v1/exam-content/materias/{materia_id}")
    assert resp.status_code == 204, resp.text
    listado = await client_admin.get("/api/v1/exam-content/materias")
    assert materia_id not in {m["id"] for m in listado.json()}


@pytest.mark.asyncio
async def test_eliminar_materia_con_comision_vacia_cascade_204(client_admin):
    materia_id = await _crear_materia(client_admin, "DEL-MAT-2", "Con comisión vacía")
    await _crear_comision(client_admin, materia_id, "1A")
    resp = await client_admin.delete(f"/api/v1/exam-content/materias/{materia_id}")
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_eliminar_materia_con_examen_409(client_admin, factory):
    materia_id = await _crear_materia(client_admin, "DEL-MAT-3", "Con examen")
    com = await _crear_comision(client_admin, materia_id, "1A")
    await _insertar_examen(factory, com["id"])
    resp = await client_admin.delete(f"/api/v1/exam-content/materias/{materia_id}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "materia_no_vacia"


@pytest.mark.asyncio
async def test_eliminar_materia_con_inscripto_409(client_admin, factory):
    materia_id = await _crear_materia(client_admin, "DEL-MAT-4", "Con inscripto")
    com = await _crear_comision(client_admin, materia_id, "1A")
    await _insertar_inscripto(factory, com["id"])
    resp = await client_admin.delete(f"/api/v1/exam-content/materias/{materia_id}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "materia_no_vacia"


@pytest.mark.asyncio
async def test_eliminar_materia_inexistente_404(client_admin):
    resp = await client_admin.delete(f"/api/v1/exam-content/materias/{_INEXISTENTE}")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_eliminar_comision_vacia_204(client_admin):
    materia_id = await _crear_materia(client_admin, "DEL-COM-1", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    resp = await client_admin.delete(f"/api/v1/exam-content/comisiones/{com['id']}")
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_eliminar_comision_con_examen_409(client_admin, factory):
    materia_id = await _crear_materia(client_admin, "DEL-COM-2", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    await _insertar_examen(factory, com["id"])
    resp = await client_admin.delete(f"/api/v1/exam-content/comisiones/{com['id']}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "comision_no_vacia"


@pytest.mark.asyncio
async def test_eliminar_comision_inexistente_404(client_admin):
    resp = await client_admin.delete(f"/api/v1/exam-content/comisiones/{_INEXISTENTE}")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# PATCH /materias/{id}/activa + freeze de rendición (C-72 §17)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_activa_desactiva_y_activa_200(client_admin):
    materia_id = await _crear_materia(client_admin, "ACT-1", "M")
    # Desactivar
    r1 = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}/activa", json={"activa": False}
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["activa"] is False
    # Reactivar
    r2 = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}/activa", json={"activa": True}
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["activa"] is True


@pytest.mark.asyncio
async def test_set_activa_inexistente_404(client_admin):
    r = await client_admin.patch(
        f"/api/v1/exam-content/materias/{_INEXISTENTE}/activa", json={"activa": False}
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_set_activa_extra_forbid_422(client_admin):
    materia_id = await _crear_materia(client_admin, "ACT-2", "M")
    r = await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}/activa",
        json={"activa": False, "otro": 1},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_rendir_examen_bloqueado_si_materia_inactiva_409(client_admin, factory):
    materia_id = await _crear_materia(client_admin, "FRZ-1", "Congelable")
    com = await _crear_comision(client_admin, materia_id, "1A")
    # Insertar examen y capturar su id
    async with factory() as s:
        r = await s.execute(
            text(
                "INSERT INTO examen_contenido (titulo, comision_id) "
                "VALUES (:t, :c) RETURNING id"
            ),
            {"t": "Examen congelable", "c": com["id"]},
        )
        examen_id = r.scalar_one()
        await s.commit()
    # Con materia activa: se puede leer para rendir.
    ok = await client_admin.get(f"/api/v1/exam-content/{examen_id}")
    assert ok.status_code == 200, ok.text
    # Desactivar la materia → rendir queda bloqueado (409 materia_inactiva).
    await client_admin.patch(
        f"/api/v1/exam-content/materias/{materia_id}/activa", json={"activa": False}
    )
    blocked = await client_admin.get(f"/api/v1/exam-content/{examen_id}")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["error"] == "materia_inactiva"


# ---------------------------------------------------------------------------
# PATCH /comisiones/{id}/activa + freeze de rendición por comisión (C-72 §17)
#
# Espejo del freeze de materia, un nivel más abajo: desactivar UNA comisión
# congela solo esa comisión (no toda la materia). Baja lógica: es la alternativa
# al DELETE cuando la comisión NO está vacía.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comision_nace_activa(client_admin):
    materia_id = await _crear_materia(client_admin, "CACT-0", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    assert com["activa"] is True


@pytest.mark.asyncio
async def test_set_activa_comision_desactiva_y_activa_200(client_admin):
    materia_id = await _crear_materia(client_admin, "CACT-1", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    r1 = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa", json={"activa": False}
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["activa"] is False
    r2 = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa", json={"activa": True}
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["activa"] is True


@pytest.mark.asyncio
async def test_set_activa_comision_persiste(client_admin):
    """La baja lógica se relee desde la DB (no es solo el eco del PATCH)."""
    materia_id = await _crear_materia(client_admin, "CACT-2", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa", json={"activa": False}
    )
    listado = await client_admin.get(
        f"/api/v1/exam-content/materias/{materia_id}/comisiones"
    )
    assert listado.status_code == 200, listado.text
    fila = next(c for c in listado.json() if c["id"] == com["id"])
    assert fila["activa"] is False


@pytest.mark.asyncio
async def test_set_activa_comision_inexistente_404(client_admin):
    r = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{_INEXISTENTE}/activa", json={"activa": False}
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["error"] == "comision_no_encontrada"


@pytest.mark.asyncio
async def test_set_activa_comision_extra_forbid_422(client_admin):
    materia_id = await _crear_materia(client_admin, "CACT-3", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    r = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa",
        json={"activa": False, "otro": 1},
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_set_activa_comision_estudiante_403(client_noauth):
    r = await client_noauth.patch(
        f"/api/v1/exam-content/comisiones/{_INEXISTENTE}/activa",
        json={"activa": False},
        headers=auth_headers(["estudiante"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rendir_examen_bloqueado_si_comision_inactiva_409(client_admin, factory):
    materia_id = await _crear_materia(client_admin, "CFRZ-1", "Materia activa")
    com = await _crear_comision(client_admin, materia_id, "1A")
    async with factory() as s:
        r = await s.execute(
            text(
                "INSERT INTO examen_contenido (titulo, comision_id) "
                "VALUES (:t, :c) RETURNING id"
            ),
            {"t": "Examen de comisión congelable", "c": com["id"]},
        )
        examen_id = r.scalar_one()
        await s.commit()
    ok = await client_admin.get(f"/api/v1/exam-content/{examen_id}")
    assert ok.status_code == 200, ok.text
    # La MATERIA sigue activa; se congela SOLO la comisión.
    await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa", json={"activa": False}
    )
    blocked = await client_admin.get(f"/api/v1/exam-content/{examen_id}")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["error"] == "comision_inactiva"


@pytest.mark.asyncio
async def test_comision_desactivada_no_bloquea_examen_de_otra_comision(
    client_admin, factory
):
    """Aislamiento: congelar la comisión A no toca los exámenes de la comisión B."""
    materia_id = await _crear_materia(client_admin, "CFRZ-2", "M")
    com_a = await _crear_comision(client_admin, materia_id, "1A")
    com_b = await _crear_comision(client_admin, materia_id, "1B")
    async with factory() as s:
        r = await s.execute(
            text(
                "INSERT INTO examen_contenido (titulo, comision_id) "
                "VALUES (:t, :c) RETURNING id"
            ),
            {"t": "Examen de B", "c": com_b["id"]},
        )
        examen_b = r.scalar_one()
        await s.commit()
    await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com_a['id']}/activa", json={"activa": False}
    )
    resp = await client_admin.get(f"/api/v1/exam-content/{examen_b}")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_eliminar_comision_con_inscripto_409_sugiere_desactivar(
    client_admin, factory
):
    """El DELETE sigue bloqueado con contenido: la baja lógica es la salida."""
    materia_id = await _crear_materia(client_admin, "CACT-4", "M")
    com = await _crear_comision(client_admin, materia_id, "1A")
    await _insertar_inscripto(factory, com["id"])
    resp = await client_admin.delete(f"/api/v1/exam-content/comisiones/{com['id']}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "comision_no_vacia"
    # Pero SÍ se puede desactivar.
    off = await client_admin.patch(
        f"/api/v1/exam-content/comisiones/{com['id']}/activa", json={"activa": False}
    )
    assert off.status_code == 200, off.text
    assert off.json()["activa"] is False
