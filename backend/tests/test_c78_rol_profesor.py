"""c-78 §11 (E-03/E-04/E-05, D11) — el rol PROFESOR y el recorte del TUTOR.

Cubre contra DB REAL:
- el PROFESOR crea/opera exámenes y el banco de SUS materias (materia_profesor);
- el PROFESOR NO emite veredicto: `revisar_sesion` sigue siendo de COORDINADOR;
- el TUTOR pierde crear exámenes y el banco EN EL BACKEND (403 aunque escriba la
  URL a mano), pero conserva notas, inscripciones y su catálogo;
- el PROFESOR queda acotado a SUS materias: una ajena da 403;
- el registro de sesiones del TUTOR se acota EN LA QUERY.

Sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad
from app.domain.auth.roles import Rol
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
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "materia_profesor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    MateriaProfesorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
]


# ===========================================================================
# Bloque A — el mapa de capacidades (puro, sin DB)
# ===========================================================================


def test_profesor_no_puede_emitir_veredicto():
    """D11: es LO QUE LO DEFINE. Si esto pasa a True, PROFESOR y COORDINADOR
    son el mismo rol con dos nombres."""
    assert not tiene_capacidad(Rol.PROFESOR, "revisar_sesion")
    assert tiene_capacidad(Rol.COORDINADOR, "revisar_sesion")


def test_profesor_crea_examenes_banco_estadisticas_y_supervisa():
    for capacidad in (
        "crear_examenes",
        "gestionar_banco",
        "ver_estadisticas",
        "supervisar_vivo",
        "gestionar_academico",
        "gestionar_notas",
    ):
        assert tiene_capacidad(Rol.PROFESOR, capacidad), capacidad


def test_tutor_pierde_examenes_banco_y_estadisticas():
    """E-03: las tres que el dueño decidió sacarle."""
    for capacidad in ("crear_examenes", "gestionar_banco", "ver_estadisticas"):
        assert not tiene_capacidad(Rol.TUTOR, capacidad), capacidad


def test_tutor_conserva_lo_suyo():
    """Triangulación: el recorte NO se llevó puesto el trabajo real del tutor."""
    for capacidad in ("gestionar_academico", "gestionar_notas", "supervisar_vivo"):
        assert tiene_capacidad(Rol.TUTOR, capacidad), capacidad


def test_profesor_no_administra_el_sistema():
    """El profesor administra lo ACADÉMICO, no el SISTEMA.

    `gestionar_estructura` NO está en esta lista a propósito: administrar
    materias, comisiones e inscripciones es trabajo académico y es del profesor
    (decisión del dueño, c-78). Lo que no toca es la configuración del sistema,
    los usuarios y la auditoría.
    """
    for capacidad in (
        "configurar_sistema",
        "gestionar_usuarios",
        "ver_auditoria",
    ):
        assert not tiene_capacidad(Rol.PROFESOR, capacidad), capacidad


def test_el_tutor_no_administra_materias_comisiones_ni_padron():
    """Decisión del dueño (c-78): el tutor no toca NADA de Materias y comisiones."""
    assert not tiene_capacidad(Rol.TUTOR, "gestionar_estructura")
    assert tiene_capacidad(Rol.PROFESOR, "gestionar_estructura")
    assert tiene_capacidad(Rol.COORDINADOR, "gestionar_estructura")


def test_ningun_rol_nuevo_quedo_sin_declarar():
    """Fail-closed: toda capacidad declarada tiene al menos admin_sistema."""
    for capacidad, roles in CAPABILITY_ROLES.items():
        assert Rol.ADMIN_SISTEMA in roles, capacidad


# ===========================================================================
# Bloque B — endpoints (DB real)
# ===========================================================================


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
        prefix="/api/v1/exam-content",
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


async def _crear_materia_con_examen(
    factory, *, profesor_id: str | None = None, tutor_id: str | None = None
) -> tuple[str, str, str]:
    """Materia + comisión + examen. Devuelve (materia_id, comision_id, examen_id)."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        if profesor_id is not None:
            s.add(MateriaProfesorModel(materia_id=materia.id, profesor_id=profesor_id))
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        if tutor_id is not None:
            s.add(ComisionTutorModel(comision_id=comision.id, tutor_id=tutor_id))
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        ids = (materia.id, comision.id, examen.id)
        await s.commit()
    return ids


def _cliente(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


# --- El PROFESOR opera SUS materias ---------------------------------------


# La config de examen exige la ventana de rendición completa (apertura y cierre):
# un examen va de una fecha/hora a otra. Se define acá para que los tests de RBAC
# manden un cuerpo válido y el 200/403 hable SOLO del permiso.
_CONFIG_VALIDA = {
    "intentos_permitidos": 2,
    "apertura": "2026-09-01T09:00:00+00:00",
    "cierre": "2026-09-01T11:00:00+00:00",
}


async def test_profesor_puede_configurar_examen_de_su_materia(app, factory):
    profesor = await _crear_usuario(factory, "profesor")
    _m, _c, examen_id = await _crear_materia_con_examen(factory, profesor_id=profesor)

    async with _cliente(app, ["profesor"], profesor) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA
        )

    assert resp.status_code == 200, resp.text


async def test_profesor_no_puede_configurar_examen_de_materia_ajena(app, factory):
    """Acotado por pertenencia: tener el rol no alcanza."""
    profesor = await _crear_usuario(factory, "profesor")
    otro_profesor = await _crear_usuario(factory, "profesor")
    _m, _c, examen_id = await _crear_materia_con_examen(
        factory, profesor_id=otro_profesor
    )

    async with _cliente(app, ["profesor"], profesor) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA
        )

    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["error"] == "examen_ajeno"


async def test_profesor_opera_el_banco_de_su_materia(app, factory):
    profesor = await _crear_usuario(factory, "profesor")
    materia_id, _c, _e = await _crear_materia_con_examen(factory, profesor_id=profesor)

    async with _cliente(app, ["profesor"], profesor) as c:
        resp = await c.get(
            "/api/v1/exam-content/categorias", params={"materia_id": materia_id}
        )

    assert resp.status_code == 200, resp.text


async def test_profesor_no_opera_el_banco_de_una_materia_ajena(app, factory):
    profesor = await _crear_usuario(factory, "profesor")
    otro = await _crear_usuario(factory, "profesor")
    materia_id, _c, _e = await _crear_materia_con_examen(factory, profesor_id=otro)

    async with _cliente(app, ["profesor"], profesor) as c:
        resp = await c.get(
            "/api/v1/exam-content/categorias", params={"materia_id": materia_id}
        )

    assert resp.status_code == 403, resp.text


# --- El TUTOR pierde exámenes y banco EN EL BACKEND ------------------------


async def test_tutor_no_puede_configurar_examen_aunque_sea_de_su_comision(app, factory):
    """E-03: el 403 no depende de que el menú no ofreciera el destino."""
    tutor = await _crear_usuario(factory, "tutor")
    _m, _c, examen_id = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA
        )

    assert resp.status_code == 403, (
        "el tutor NO debe poder configurar exámenes; el gate es del backend, "
        f"no del menú. Respuesta: {resp.status_code} {resp.text}"
    )


async def test_tutor_no_puede_entrar_al_banco_escribiendo_la_url(app, factory):
    tutor = await _crear_usuario(factory, "tutor")
    materia_id, _c, _e = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        categorias = await c.get(
            "/api/v1/exam-content/categorias", params={"materia_id": materia_id}
        )
        preguntas = await c.get(
            "/api/v1/exam-content/preguntas", params={"materia_id": materia_id}
        )

    assert categorias.status_code == 403, categorias.text
    assert preguntas.status_code == 403, preguntas.text


async def test_tutor_no_puede_dar_de_baja_un_examen(app, factory):
    tutor = await _crear_usuario(factory, "tutor")
    _m, _c, examen_id = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        resp = await c.delete(f"/api/v1/exam-content/{examen_id}")

    assert resp.status_code == 403, resp.text


async def test_tutor_conserva_la_lectura_de_su_catalogo(app, factory):
    """Triangulación: el recorte NO le sacó lo que sí es suyo."""
    tutor = await _crear_usuario(factory, "tutor")
    _m, _c, examen_id = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        config = await c.get(f"/api/v1/exam-content/{examen_id}/config")
        resultados = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")

    assert config.status_code == 200, config.text
    assert resultados.status_code == 200, resultados.text


# --- Asignación de profesores a materias ----------------------------------


async def test_admin_asigna_y_quita_profesor_de_una_materia(app, factory):
    admin = await _crear_usuario(factory, "admin_sistema")
    profesor = await _crear_usuario(factory, "profesor")
    materia_id, _c, _e = await _crear_materia_con_examen(factory)

    async with _cliente(app, ["admin_sistema"], admin) as c:
        alta = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/profesores",
            json={"profesor_id": profesor},
        )
        assert alta.status_code == 201, alta.text
        assert [p["id"] for p in alta.json()["profesores"]] == [profesor]

        baja = await c.delete(
            f"/api/v1/exam-content/materias/{materia_id}/profesores/{profesor}"
        )
        assert baja.status_code == 200, baja.text
        assert baja.json()["profesores"] == []


async def test_no_se_puede_asignar_como_profesor_a_quien_no_tiene_el_rol(app, factory):
    admin = await _crear_usuario(factory, "admin_sistema")
    tutor = await _crear_usuario(factory, "tutor")
    materia_id, _c, _e = await _crear_materia_con_examen(factory)

    async with _cliente(app, ["admin_sistema"], admin) as c:
        resp = await c.post(
            f"/api/v1/exam-content/materias/{materia_id}/profesores",
            json={"profesor_id": tutor},
        )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "no_es_profesor"


# ===========================================================================
# El TUTOR no toca NADA de Materias y comisiones (decisión del dueño, c-78)
#
# No alcanza con ocultarle la pantalla: el gate es del backend. Estos endpoints
# antes quedaban abiertos con solo `gestionar_academico`, que el tutor tiene.
# ===========================================================================


async def test_tutor_no_puede_inscribir_ni_desinscribir_alumnos(app, factory):
    tutor = await _crear_usuario(factory, "tutor")
    alumno = await _crear_usuario(factory, "estudiante")
    _m, comision_id, _e = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        alta = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
            json={"usuario_id": alumno},
        )
        baja = await c.delete(
            f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones/{alumno}"
        )

    assert alta.status_code == 403, alta.text
    assert baja.status_code == 403, baja.text


async def test_tutor_no_puede_editar_ni_borrar_su_comision(app, factory):
    tutor = await _crear_usuario(factory, "tutor")
    _m, comision_id, _e = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        editar = await c.patch(
            f"/api/v1/exam-content/comisiones/{comision_id}",
            json={"nombre": "Renombrada", "periodo": None, "anio": None},
        )
        # c-78: `PATCH /{id}/activa` se eliminó — un solo patrón de baja lógica en
        # todo el sistema (DELETE da de baja, POST /reactivar revierte). El test
        # seguía apuntando al endpoint viejo y por eso recibía 404 en vez de 403.
        reactivar = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/reactivar"
        )
        borrar = await c.delete(f"/api/v1/exam-content/comisiones/{comision_id}")
        rotar = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/rotar-codigo"
        )

    for resp, que in (
        (editar, "editar"),
        (reactivar, "reactivar"),
        (borrar, "borrar"),
        (rotar, "rotar el código de"),
    ):
        assert resp.status_code == 403, f"el tutor pudo {que} una comisión: {resp.text}"


async def test_tutor_no_puede_asignarse_ni_sacarse_tutores(app, factory):
    """Si pudiera, la pertenencia dejaría de ser un control: se auto-otorgaría."""
    tutor = await _crear_usuario(factory, "tutor")
    otro = await _crear_usuario(factory, "tutor")
    _m, comision_id, _e = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        alta = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores",
            json={"tutor_id": otro},
        )
        baja = await c.delete(
            f"/api/v1/exam-content/comisiones/{comision_id}/tutores/{tutor}"
        )

    assert alta.status_code == 403, alta.text
    assert baja.status_code == 403, baja.text


async def test_el_profesor_si_administra_la_estructura_de_su_materia(app, factory):
    """Triangulación: lo que se le sacó al tutor lo tiene el profesor."""
    profesor = await _crear_usuario(factory, "profesor")
    alumno = await _crear_usuario(factory, "estudiante")
    _m, comision_id, _e = await _crear_materia_con_examen(factory, profesor_id=profesor)

    async with _cliente(app, ["profesor"], profesor) as c:
        alta = await c.post(
            f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
            json={"usuario_id": alumno},
        )

    assert alta.status_code in (201, 200), alta.text


async def test_tutor_conserva_la_lectura_de_materias_y_comisiones(app, factory):
    """El recorte es de ESCRITURA: el tutor sigue viendo lo suyo."""
    tutor = await _crear_usuario(factory, "tutor")
    _m, comision_id, _e = await _crear_materia_con_examen(factory, tutor_id=tutor)

    async with _cliente(app, ["tutor"], tutor) as c:
        alumnos = await c.get(
            f"/api/v1/exam-content/comisiones/{comision_id}/alumnos"
        )

    assert alumnos.status_code == 200, alumnos.text
