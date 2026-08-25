"""c-78 (deuda c-79): la credencial del write-back sale de `comision_tutor`, no de `docente_id`.

## El bug que estos tests cierran

`_credencial_para` resolvía "con la credencial de quién se devuelve esta nota"
leyendo `comision.docente_id`, la columna 1:1 previa a c-79. Desde que la
pertenencia pasó a la tabla puente `comision_tutor` (migración 0086), **ningún
endpoint escribe esa columna**: el alta de comisión no la tiene y asignar tutores
escribe solo en la tabla puente.

Resultado: toda comisión creada o gestionada desde la UI actual tiene
`docente_id IS NULL` aunque tenga N tutores a cargo, y el write-back devolvía
`sin_docente` y retenía la nota. Y ese camino NO tiene respaldo institucional a
propósito (C-73 §10.4: la nota sale con la credencial del docente o no sale), así
que la nota simplemente no llegaba nunca al campus.

## El criterio de desempate, y por qué

Con varios tutores por comisión hay que elegir con cuál credencial se firma. Se
adopta el modelo del sistema de referencia (JuanCruzRobledo/active-ia-correccion-
automatica): **acceso simétrico por pertenencia, sin tutor "principal"** — su
`comision_tutor` no tiene ningún campo de responsable y cualquier tutor de la
comisión puede corregir cualquier entrega.

Acá hace falta igual elegir UNA credencial para firmar, así que se elige la del
**tutor con credencial usable que primero quedó a cargo** (`created_at`, desempate
por `tutor_id` para que sea determinístico). Determinístico importa: dos
sincronizaciones seguidas de la misma nota tienen que salir firmadas por la misma
persona, si no la columna *Fuente* de la libreta cambiaría sola.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.credencial_docente_service import CredencialDocenteService
from app.application.moodle.writeback_service import MoodleWritebackService
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    MoodleCredencialDocenteModel,
    UsuarioModel,
)

_KEY = "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
_TOKEN = "t0ken-de-moodle-abcd"  # noqa: S105

_TABLES = [
    "comision_tutor",
    "proctoring_session",
    "examen_contenido",
    "comision",
    "materia",
    "moodle_credencial_docente",
    "usuario",
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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                UsuarioModel.__table__,
                MoodleCredencialDocenteModel.__table__,
                MateriaModel.__table__,
                ComisionModel.__table__,
                ComisionTutorModel.__table__,
                ExamenContenidoModel.__table__,
                ProctoringSessionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
def cred_service(factory):
    return CredencialDocenteService(session_factory=factory, cipher=SecretCipher(key=_KEY))


@pytest_asyncio.fixture
def writeback_svc(cred_service):
    config = MoodleClientConfig(base_url="https://campus.test", ws_token="institucional")  # noqa: S106
    return MoodleWritebackService(
        moodle_client=MoodleRestClient(config=config), credencial_docente=cred_service
    )


async def _docente(factory, legajo: str, *, nombre: str | None = None) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=legajo, email=f"{legajo.lower()}@uni.edu", nombre=nombre
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _con_credencial(cred_service, usuario_id: str) -> None:
    await cred_service.guardar_token(
        usuario_id=usuario_id, moodle_username=f"m-{usuario_id[:6]}", token=_TOKEN
    )


async def _sesion_con_tutores(factory, tutores: list[str]) -> str:
    """Materia + comisión + N tutores en la tabla puente + examen + sesión.

    Los tutores se insertan en el orden de la lista, con `created_at` creciente,
    para que el desempate por "el primero que quedó a cargo" sea observable.
    """
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
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for i, tutor_id in enumerate(tutores):
            s.add(
                ComisionTutorModel(
                    comision_id=comision.id,
                    tutor_id=tutor_id,
                    created_at=base.replace(day=1 + i),
                )
            )
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        sesion = ProctoringSessionModel(modo="examen", examen_contenido_id=examen.id)
        s.add(sesion)
        await s.flush()
        session_id = sesion.id
        await s.commit()
    return session_id


@pytest.mark.asyncio
async def test_resuelve_la_credencial_desde_la_tabla_puente(
    writeback_svc, factory, cred_service
):
    """RED→GREEN: el bug. Comisión SIN `docente_id` pero CON tutor a cargo.

    Es el estado de toda comisión creada desde c-79. Antes devolvía `sin_docente`
    y la nota no salía nunca.
    """
    tutor = await _docente(factory, "T-NM1", nombre="Ana")
    await _con_credencial(cred_service, tutor)
    session_id = await _sesion_con_tutores(factory, [tutor])

    async with factory() as db:
        token, docente_id, nombre, motivo = await writeback_svc._credencial_para(
            db, session_id
        )

    assert motivo is None
    assert token == _TOKEN
    assert docente_id == tutor
    assert nombre == "Ana"


@pytest.mark.asyncio
async def test_con_varios_tutores_elige_el_primero_que_quedo_a_cargo(
    writeback_svc, factory, cred_service
):
    """Determinístico: dos sincronizaciones seguidas firman con la misma persona.

    Si variara, la columna *Fuente* de la libreta cambiaría sola entre sincros.
    """
    primero = await _docente(factory, "T-NM2A", nombre="Ana")
    segundo = await _docente(factory, "T-NM2B", nombre="Beto")
    await _con_credencial(cred_service, primero)
    await _con_credencial(cred_service, segundo)
    session_id = await _sesion_con_tutores(factory, [primero, segundo])

    async with factory() as db:
        _, docente_id, nombre, motivo = await writeback_svc._credencial_para(
            db, session_id
        )
        _, docente_id_2, _, _ = await writeback_svc._credencial_para(db, session_id)

    assert motivo is None
    assert docente_id == primero
    assert nombre == "Ana"
    assert docente_id_2 == primero


@pytest.mark.asyncio
async def test_saltea_al_tutor_sin_credencial_y_usa_al_que_si_tiene(
    writeback_svc, factory, cred_service
):
    """TRIANGULATE: el modelo es simétrico, cualquier tutor de la comisión sirve.

    Que el primero no haya conectado su cuenta no puede retener la nota si otro
    tutor de la misma comisión sí la tiene.
    """
    sin_cred = await _docente(factory, "T-NM3A", nombre="Ana")
    con_cred = await _docente(factory, "T-NM3B", nombre="Beto")
    await _con_credencial(cred_service, con_cred)
    session_id = await _sesion_con_tutores(factory, [sin_cred, con_cred])

    async with factory() as db:
        token, docente_id, nombre, motivo = await writeback_svc._credencial_para(
            db, session_id
        )

    assert motivo is None
    assert token == _TOKEN
    assert docente_id == con_cred
    assert nombre == "Beto"


@pytest.mark.asyncio
async def test_comision_sin_ningun_tutor_sigue_bloqueando(
    writeback_svc, factory
):
    """El bloqueo sigue existiendo cuando de verdad no hay a quién atribuirle la nota.

    C-73 §10.4: no hay respaldo institucional para este camino a propósito — una
    nota firmada por la cuenta de servicio llega a la libreta sin dueño.
    """
    session_id = await _sesion_con_tutores(factory, [])

    async with factory() as db:
        token, _, _, motivo = await writeback_svc._credencial_para(db, session_id)

    assert token is None
    assert motivo == "sin_docente"


@pytest.mark.asyncio
async def test_tutores_sin_credencial_reportan_el_motivo_correcto(
    writeback_svc, factory
):
    """TRIANGULATE: hay tutor pero ninguno conectó su cuenta.

    El motivo tiene que ser `sin_credencial_docente` ("nunca conectaste tu
    cuenta"), no `sin_docente` ("no hay docente a cargo"): son problemas distintos
    y el docente tiene que saber a cuál responder.
    """
    tutor = await _docente(factory, "T-NM4", nombre="Ana")
    session_id = await _sesion_con_tutores(factory, [tutor])

    async with factory() as db:
        token, docente_id, _, motivo = await writeback_svc._credencial_para(
            db, session_id
        )

    assert token is None
    assert motivo == "sin_credencial_docente"
    # Se informa DE QUIÉN es la cuenta que falta: si no, el mensaje no dice a quién
    # hay que ir a buscar.
    assert docente_id == tutor
