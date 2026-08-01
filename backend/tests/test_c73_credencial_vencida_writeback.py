"""`_credencial_para` distingue POR QUE no hay token (C-73 §12).

`sin_docente` / `sin_credencial_docente` / `caida` / `vencida` son motivos
DISTINTOS y necesitan mensajes distintos: no es lo mismo "nunca conectaste tu
cuenta" que "el campus rechazó tu llave" que "pasaron 30 días, volvé a
demostrar tu contraseña actual" — el docente tiene que saber a cuál de los
tres responder.

DB real (DATABASE_URL). Sin mocks de DB.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.credencial_docente_service import (
    DIAS_VENCIMIENTO_CREDENCIAL,
    CredencialDocenteService,
)
from app.application.moodle.writeback_service import (
    MENSAJE_POR_MOTIVO_BLOQUEO,
    MoodleWritebackService,
)
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    MoodleCredencialDocenteModel,
    UsuarioModel,
)

_KEY = "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
_TOKEN = "t0ken-de-moodle-abcd"  # noqa: S105

_TABLES_TO_DROP = [
    "proctoring_session",
    "examen_contenido",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    ProctoringSessionModel.__table__,
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
        # `usuario` y `moodle_credencial_docente` ya existen via migraciones; create_all
        # es idempotente, esto es solo para que el archivo corra contra una DB nueva.
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[UsuarioModel.__table__, MoodleCredencialDocenteModel.__table__],
        )
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
async def cred_service(factory):
    return CredencialDocenteService(session_factory=factory, cipher=SecretCipher(key=_KEY))


@pytest.fixture
def writeback_svc(cred_service):
    config = MoodleClientConfig(base_url="https://campus.test", ws_token="institucional")  # noqa: S106
    client = MoodleRestClient(config=config)
    return MoodleWritebackService(moodle_client=client, credencial_docente=cred_service)


async def _crear_docente(factory, legajo: str, creados: list[str]) -> str:
    async with factory() as s:
        u = UsuarioModel(id_institucional=legajo, email=f"{legajo.lower()}@uni.edu")
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    creados.append(uid)
    return uid


async def _crear_sesion(factory, docente_id: str | None) -> str:
    """Materia + comisión (con el docente dado) + examen + sesión. Devuelve session_id."""
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
            docente_id=docente_id,
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        sesion = ProctoringSessionModel(
            modo="examen", examen_contenido_id=examen.id
        )
        s.add(sesion)
        await s.flush()
        session_id = sesion.id
        await s.commit()
    return session_id


@pytest_asyncio.fixture
async def docentes(engine):
    """Trackea los usuario_id creados por el test para borrar SOLO esos —
    nunca un `DELETE FROM usuario` sin filtro contra la DB compartida de dev.
    `comision.docente_id` es ON DELETE SET NULL y `moodle_credencial_docente`
    es ON DELETE CASCADE: borrar el usuario alcanza, sin dejar huérfanos."""
    creados: list[str] = []
    yield creados
    if not creados:
        return
    async with async_sessionmaker(engine, class_=AsyncSession)() as s:
        await s.execute(text("DELETE FROM usuario WHERE id = ANY(:ids)"), {"ids": creados})
        await s.commit()


@pytest.mark.asyncio
async def test_sin_comision_docente_motivo_sin_docente(writeback_svc, factory, docentes):
    session_id = await _crear_sesion(factory, docente_id=None)
    async with factory() as db:
        token, docente_id, nombre, motivo = await writeback_svc._credencial_para(
            db, session_id
        )
    assert token is None
    assert motivo == "sin_docente"


@pytest.mark.asyncio
async def test_docente_nunca_conecto_motivo_sin_credencial_docente(
    writeback_svc, factory, docentes
):
    docente_id = await _crear_docente(factory, f"D-{uuid.uuid4().hex[:8]}", docentes)
    session_id = await _crear_sesion(factory, docente_id=docente_id)
    async with factory() as db:
        token, did, nombre, motivo = await writeback_svc._credencial_para(db, session_id)
    assert token is None
    assert motivo == "sin_credencial_docente"


@pytest.mark.asyncio
async def test_docente_con_credencial_activa_motivo_none(
    writeback_svc, cred_service, factory, docentes
):
    docente_id = await _crear_docente(factory, f"D-{uuid.uuid4().hex[:8]}", docentes)
    await cred_service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    session_id = await _crear_sesion(factory, docente_id=docente_id)
    async with factory() as db:
        token, did, nombre, motivo = await writeback_svc._credencial_para(db, session_id)
    assert token == _TOKEN
    assert motivo is None


@pytest.mark.asyncio
async def test_docente_con_credencial_caida_motivo_caida(
    writeback_svc, cred_service, factory, docentes
):
    docente_id = await _crear_docente(factory, f"D-{uuid.uuid4().hex[:8]}", docentes)
    await cred_service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await cred_service.marcar_caida(docente_id)
    session_id = await _crear_sesion(factory, docente_id=docente_id)
    async with factory() as db:
        token, did, nombre, motivo = await writeback_svc._credencial_para(db, session_id)
    assert token is None
    assert motivo == "caida"


@pytest.mark.asyncio
async def test_docente_con_credencial_vencida_motivo_vencida(
    writeback_svc, cred_service, factory, docentes
):
    docente_id = await _crear_docente(factory, f"D-{uuid.uuid4().hex[:8]}", docentes)
    await cred_service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    async with factory() as s:
        await s.execute(
            text(
                "UPDATE moodle_credencial_docente SET actualizado_en = :ts "
                "WHERE usuario_id = :uid"
            ),
            {
                "ts": datetime.now(timezone.utc)
                - timedelta(days=DIAS_VENCIMIENTO_CREDENCIAL),
                "uid": docente_id,
            },
        )
        await s.commit()
    session_id = await _crear_sesion(factory, docente_id=docente_id)
    async with factory() as db:
        token, did, nombre, motivo = await writeback_svc._credencial_para(db, session_id)
    assert token is None
    assert motivo == "vencida"


# ---------------------------------------------------------------------------
# Mapeo motivo -> mensaje (pura, sin DB): distinguir "se cayó" de "venció" del
# lado del docente, no solo internamente.
# ---------------------------------------------------------------------------


def test_mensaje_de_vencida_no_sugiere_que_moodle_la_rechazo():
    msg = MENSAJE_POR_MOTIVO_BLOQUEO["vencida"]
    assert "30 día" in msg or "30 dias" in msg
    assert "campus" in msg.lower()


def test_mensaje_de_caida_distinto_del_de_vencida():
    assert MENSAJE_POR_MOTIVO_BLOQUEO["caida"] != MENSAJE_POR_MOTIVO_BLOQUEO["vencida"]


def test_mensaje_sin_credencial_docente_se_mantiene():
    assert (
        "sin_credencial_docente" in MENSAJE_POR_MOTIVO_BLOQUEO["sin_credencial_docente"]
    )
