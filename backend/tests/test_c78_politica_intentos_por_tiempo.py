"""c-78 F-04 (D7) — las políticas ULTIMO/PRIMERO ordenan por tiempo real.

`_aplicar_politica` usaba `min/max` sobre `session_id` para PRIMERO/ULTIMO. Los ids
son UUID v4 (`gen_random_uuid()`): el orden es ALEATORIO. Con dos intentos, "la
última" era la que saliera — y eso decide QUÉ NOTA se escribe en Moodle.

El dataset de cada test es adversarial a propósito: el `session_id` ordena AL REVÉS
que `creada_en`. Si la implementación volviera a ordenar por id, estos tests fallan.

DB real (DATABASE_URL). Sin mocks de DB (regla dura #4) — el único doble es el
cliente de Moodle, que es un servicio externo, no la base.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

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
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_TABLES_TO_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "comision",
    "materia",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "usuario",
]
_TABLES_TO_CREATE = [
    UsuarioModel.__table__,
    MateriaModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    RespuestaAlumnoModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
]

# Legajo del alumno con dos intentos. Compartido por todos los tests: la
# deduplicación de la política es por `alumno_idnumber`.
_LEGAJO = "EST-DOBLE-INTENTO"


class _WritebackEspia:
    """Doble del cliente de Moodle: registra a qué sesiones se les mandó nota.

    NO es un mock de la base (regla dura #4): la base es real, lo que se
    reemplaza es la llamada HTTP al campus, que es un tercero.
    """

    def __init__(self) -> None:
        self.enviadas: list[str] = []

    async def ejecutar_writeback(
        self, *, db, session_id, nota, alumno_idnumber, alumno_email
    ) -> None:
        from sqlalchemy import select

        from app.application.moodle.writeback_service import WritebackEstado

        self.enviadas.append(session_id)
        # Marca la fila como enviada sobre el MISMO objeto que tiene el endpoint en
        # la sesión (lee `fila.estado` después de llamar acá para contar enviadas).
        fila = (
            await db.execute(
                select(MoodleWritebackEstadoModel).where(
                    MoodleWritebackEstadoModel.session_id == session_id
                )
            )
        ).scalar_one()
        fila.estado = WritebackEstado.ENVIADO


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
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def espia():
    return _WritebackEspia()


@pytest_asyncio.fixture
async def app(factory, espia):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=espia),
        prefix="/api/v1/exam-content",
    )
    return application


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"]),
    )


async def _crear_examen(factory, *, politica: str) -> str:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(
            titulo=f"Parcial {sufijo}",
            comision_id=comision.id,
            politica_intentos=politica,
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


async def _crear_intento(
    factory,
    examen_id: str,
    *,
    session_id: str,
    creada_en: datetime,
    nota: float,
) -> str:
    """Sesión finalizada + su fila pendiente de write-back, con id EXPLÍCITO.

    El id se fija a mano para poder construir el caso adversarial (id que ordena
    al revés que el tiempo); en producción lo genera `gen_random_uuid()`.
    """
    async with factory() as s:
        sesion = ProctoringSessionModel(
            id=session_id,
            modo="examen",
            examen_contenido_id=examen_id,
            alumno_idnumber=_LEGAJO,
            alumno_email=f"{_LEGAJO.lower()}@uni.edu",
            creada_en=creada_en,
            finalizada_en=creada_en + timedelta(minutes=30),
        )
        s.add(sesion)
        await s.flush()
        s.add(
            MoodleWritebackEstadoModel(
                session_id=session_id,
                alumno_idnumber=_LEGAJO,
                alumno_email=f"{_LEGAJO.lower()}@uni.edu",
                nota=nota,
                estado="pendiente",
            )
        )
        await s.commit()
    return session_id


async def _dos_intentos_con_id_al_reves(factory, examen_id: str) -> dict:
    """Dos intentos del mismo alumno donde el id ordena AL REVÉS que el tiempo.

    - `viejo`:  creado hace 2 horas, id que empieza con 'ffff…' (ordena ÚLTIMO por id)
    - `nuevo`:  creado hace 1 hora,  id que empieza con '0000…' (ordena PRIMERO por id)

    Con el bug (orden por session_id), ULTIMO elegiría `viejo` y PRIMERO `nuevo`:
    exactamente al revés de lo correcto.
    """
    ahora = datetime.now(timezone.utc)
    id_viejo = f"ffffffff-ffff-4fff-8fff-{uuid.uuid4().hex[:12]}"
    id_nuevo = f"00000000-0000-4000-8000-{uuid.uuid4().hex[:12]}"

    await _crear_intento(
        factory,
        examen_id,
        session_id=id_viejo,
        creada_en=ahora - timedelta(hours=2),
        nota=90.0,  # el MÁS VIEJO tiene la nota MÁS ALTA (separa MAS_ALTA de ULTIMO)
    )
    await _crear_intento(
        factory,
        examen_id,
        session_id=id_nuevo,
        creada_en=ahora - timedelta(hours=1),
        nota=40.0,
    )
    return {"viejo": id_viejo, "nuevo": id_nuevo}


async def _sincronizar(app, examen_id: str) -> dict:
    async with _admin_client(app) as c:
        r = await c.post(f"/api/v1/exam-content/{examen_id}/sincronizar-moodle")
    assert r.status_code == 200, r.text
    return r.json()


async def test_ultimo_elige_la_sesion_mas_reciente_no_el_uuid_mas_alto(
    app, factory, espia
):
    examen_id = await _crear_examen(factory, politica="ultimo")
    ids = await _dos_intentos_con_id_al_reves(factory, examen_id)

    await _sincronizar(app, examen_id)

    assert espia.enviadas == [ids["nuevo"]], (
        "ULTIMO debe elegir el intento más RECIENTE por `creada_en`. Eligió "
        f"{espia.enviadas} y el más reciente es {ids['nuevo']}."
    )


async def test_primero_elige_la_sesion_mas_antigua_no_el_uuid_mas_bajo(
    app, factory, espia
):
    examen_id = await _crear_examen(factory, politica="primero")
    ids = await _dos_intentos_con_id_al_reves(factory, examen_id)

    await _sincronizar(app, examen_id)

    assert espia.enviadas == [ids["viejo"]], (
        "PRIMERO debe elegir el intento más ANTIGUO por `creada_en`. Eligió "
        f"{espia.enviadas} y el más antiguo es {ids['viejo']}."
    )


async def test_mas_alta_sigue_eligiendo_por_nota(app, factory, espia):
    """Triangulación: el cambio de criterio temporal NO tocó MAS_ALTA."""
    examen_id = await _crear_examen(factory, politica="mas_alta")
    ids = await _dos_intentos_con_id_al_reves(factory, examen_id)

    await _sincronizar(app, examen_id)

    # El más viejo tiene 90 y el más nuevo 40: gana la nota, no el tiempo.
    assert espia.enviadas == [ids["viejo"]], (
        f"MAS_ALTA debe elegir por nota. Eligió {espia.enviadas}."
    )


async def test_manual_no_deduplica_y_manda_los_dos_intentos(app, factory, espia):
    """Triangulación: MANUAL sigue mandando todo (el admin eligió a mano)."""
    examen_id = await _crear_examen(factory, politica="manual")
    ids = await _dos_intentos_con_id_al_reves(factory, examen_id)

    resp = await _sincronizar(app, examen_id)

    assert set(espia.enviadas) == {ids["viejo"], ids["nuevo"]}
    assert resp["total"] == 2


async def test_listar_sincronizables_proyecta_creada_en_de_la_sesion(factory):
    """El eje temporal llega a la fila: sin esto la política no tiene con qué ordenar."""
    from app.application.moodle.resultados_query import listar_estados_sincronizables

    examen_id = await _crear_examen(factory, politica="ultimo")
    await _dos_intentos_con_id_al_reves(factory, examen_id)

    async with factory() as s:
        filas = await listar_estados_sincronizables(db=s, examen_id=examen_id)

    assert len(filas) == 2
    for fila in filas:
        assert getattr(fila, "sesion_creada_en", None) is not None, (
            "cada fila sincronizable debe traer `sesion_creada_en` proyectado"
        )
