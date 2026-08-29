"""Retencion de CAPTURAS de proctoring (screenshot_b64) — purgado + config + endpoint.

Cubre, TODO contra DB REAL (regla dura: nunca mockear la DB):
  - Dominio: piso de 90 dias (validar_retencion_capturas_dias)
  - purgar_capturas_vencidas: borra la IMAGEN de eventos con sesion vieja,
    CONSERVA screenshot_sha256/worm_object_key/worm_uri/el resto del evento,
    no toca sesiones recientes, es idempotente
  - configuracion_sistema.retencion_capturas_dias: default 180
  - PATCH /api/v1/config: rechaza < 90 con 422 y mensaje entendible
  - POST /api/v1/admin/retention/capturas: purga segun la config, audita
    SIEMPRE (incluso con 0 purgadas), exige admin_sistema

TDD Cycle: RED -> GREEN -> TRIANGULATE -> REFACTOR.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.compliance.retencion_capturas import purgar_capturas_vencidas
from app.domain.retention.policy import (
    RETENCION_CAPTURAS_DIAS_MINIMO,
    validar_retencion_capturas_dias,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
)
from app.infrastructure.persistence.repositories.config_sistema import (
    ConfiguracionSistemaSqlRepository,
)
from app.presentation.api.v1.admin import admin_retention_router
from app.presentation.api.v1.config.router import router as config_router
from tests._audit_schema import DDL_COMPLETA as _AUDIT_DDL
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers


# ---------------------------------------------------------------------------
# Tests puros de dominio (sin DB)
# ---------------------------------------------------------------------------


def test_valida_retencion_capturas_dias_acepta_el_minimo():
    """90 (el piso exacto) NO rechaza."""
    validar_retencion_capturas_dias(RETENCION_CAPTURAS_DIAS_MINIMO)


def test_valida_retencion_capturas_dias_rechaza_por_debajo_del_minimo():
    with pytest.raises(ValueError, match="90"):
        validar_retencion_capturas_dias(89)


def test_valida_retencion_capturas_dias_acepta_el_default():
    validar_retencion_capturas_dias(180)


# ---------------------------------------------------------------------------
# Fixtures de integracion (DB real, base aislada por modulo)
# ---------------------------------------------------------------------------

_TABLES_TO_DROP = [
    "proctoring_event",
    "proctoring_session",
    "examen_contenido",
    "configuracion_sistema",
    "audit_log",
]
_TABLES_TO_CREATE = [
    # examen_contenido PRIMERO: proctoring_session tiene un FK hacia ella (C-69).
    ExamenContenidoModel.__table__,
    ConfiguracionSistemaModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
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
        # audit_log necesita su DDL propia (tabla + triggers de cadena de hash +
        # pgcrypto) — el modelo ORM no la describe (ver tests/_audit_schema.py).
        for sentencia in _AUDIT_DDL:
            await conn.execute(text(sentencia))
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _limpiar(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE proctoring_event, proctoring_session, configuracion_sistema, "
                "audit_log RESTART IDENTITY CASCADE"
            )
        )


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_entre_tests(engine):
    await _limpiar(engine)
    yield


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


async def _crear_sesion_con_evento(
    factory: async_sessionmaker[AsyncSession],
    *,
    creada_hace_dias: int,
    con_worm: bool = False,
) -> tuple[str, str]:
    """Crea una sesion + 1 evento CON captura. Devuelve (session_id, event_id)."""
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"ret-cap-{_suffix()}")
        s.add(sesion)
        await s.flush()
        sesion.creada_en = datetime.now(timezone.utc) - timedelta(days=creada_hace_dias)

        evento = ProctoringEventModel(
            session_id=sesion.id,
            tipo="FACE_ABSENT",
            severidad="medio",
            ts_cliente=datetime.now(timezone.utc),
            ts_backend=datetime.now(timezone.utc),
            payload={},
            screenshot_b64="ZmFrZS1iYXNlNjQtaW1hZ2U=",
            screenshot_sha256="a" * 64,
        )
        if con_worm:
            evento.worm_object_key = f"{sesion.id}/evt.bin"
            evento.worm_uri = f"s3://bucket/{sesion.id}/evt.bin"
        s.add(evento)
        await s.flush()
        await s.commit()
        return sesion.id, evento.id


# ---------------------------------------------------------------------------
# purgar_capturas_vencidas — integracion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purga_captura_de_sesion_vieja_y_conserva_hash_y_worm(factory):
    _, evento_id = await _crear_sesion_con_evento(
        factory, creada_hace_dias=200, con_worm=True
    )
    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()
    assert purgadas == 1

    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 is None
        # Lo mas importante del diseño: se borra la IMAGEN, no la huella ni el
        # puntero WORM ni el resto del evento.
        assert evento.screenshot_sha256 == "a" * 64
        assert evento.worm_object_key == f"{evento.session_id}/evt.bin"
        assert evento.worm_uri is not None
        assert evento.tipo == "FACE_ABSENT"


@pytest.mark.asyncio
async def test_no_toca_capturas_de_sesion_reciente(factory):
    _, evento_id = await _crear_sesion_con_evento(factory, creada_hace_dias=5)
    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()
    assert purgadas == 0

    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 == "ZmFrZS1iYXNlNjQtaW1hZ2U="


@pytest.mark.asyncio
async def test_purgado_es_idempotente(factory):
    await _crear_sesion_con_evento(factory, creada_hace_dias=200)
    async with factory() as s:
        primera = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()
    assert primera == 1

    async with factory() as s:
        segunda = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()
    assert segunda == 0


# ---------------------------------------------------------------------------
# Evidencia PROTEGIDA: la que sostiene un caso no se purga (decision del dueño)
# ---------------------------------------------------------------------------
#
# El plazo se pensó para las fotos de quien rindió normal, que son el grueso del
# peso en la base y no le sirven a nadie. Pero borrar la foto de un examen
# anulado deja al alumno sin la parte más fuerte de su expediente: el verify-chain
# pasa a devolver `material_missing` y ya no hay nada que peritar. Lo mismo vale
# para una sesión que sigue en cola de revisión: todavía no hay veredicto, así que
# la evidencia sigue en juego.


async def _crear_sesion(
    factory: async_sessionmaker[AsyncSession],
    *,
    creada_hace_dias: int,
    decision: str | None = None,
    severidad: str = "medio",
    eventos: int = 1,
) -> tuple[str, list[str]]:
    """Sesion + N eventos con captura. Devuelve (session_id, [event_ids]).

    ``severidad`` importa: el vocabulario canónico es femenino
    (baja/media/alta/critica). "medio" no matchea ninguna y pesa 0, que es
    justo lo que se quiere para una sesión que NO debe quedar flaggeada.
    """
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"ret-cap-{_suffix()}")
        if decision is not None:
            sesion.decision = decision
        s.add(sesion)
        await s.flush()
        sesion.creada_en = datetime.now(timezone.utc) - timedelta(days=creada_hace_dias)
        ids = []
        for _ in range(eventos):
            evento = ProctoringEventModel(
                session_id=sesion.id,
                tipo="multiples_rostros",
                severidad=severidad,
                ts_cliente=datetime.now(timezone.utc),
                ts_backend=datetime.now(timezone.utc),
                payload={},
                screenshot_b64="ZmFrZS1iYXNlNjQtaW1hZ2U=",
                screenshot_sha256="c" * 64,
            )
            s.add(evento)
            await s.flush()
            ids.append(evento.id)
        await s.commit()
        return sesion.id, ids


@pytest.mark.asyncio
async def test_no_purga_la_captura_de_un_examen_anulado(factory):
    """Es la evidencia en la que se apoyó la anulación: sin ella el expediente
    del alumno queda sin nada que mostrar."""
    _, (evento_id,) = await _crear_sesion(
        factory, creada_hace_dias=400, decision="anulado"
    )

    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()

    assert purgadas == 0
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 == "ZmFrZS1iYXNlNjQtaW1hZ2U="


@pytest.mark.asyncio
async def test_no_purga_la_captura_de_una_sesion_en_cola_de_revision(factory):
    """Score >= umbral (70 por default) y sin decisión: el caso sigue abierto.

    Una severidad `critica` pesa 80, así que un solo evento la deja flaggeada.
    """
    _, (evento_id,) = await _crear_sesion(
        factory, creada_hace_dias=400, severidad="critica"
    )

    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()

    assert purgadas == 0
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 == "ZmFrZS1iYXNlNjQtaW1hZ2U="


@pytest.mark.asyncio
async def test_si_purga_la_captura_de_un_examen_aprobado(factory):
    """Triangulación: revisado y cerrado limpio, la foto ya no sostiene nada."""
    _, (evento_id,) = await _crear_sesion(
        factory, creada_hace_dias=400, decision="aprobado", severidad="critica"
    )

    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()

    assert purgadas == 1
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 is None


@pytest.mark.asyncio
async def test_protege_una_sesion_sin_tocar_a_las_demas(factory):
    """La exclusión es por sesión, no un freno global del purgado."""
    _, (protegido,) = await _crear_sesion(
        factory, creada_hace_dias=400, decision="anulado"
    )
    _, (purgable,) = await _crear_sesion(factory, creada_hace_dias=400)

    async with factory() as s:
        purgadas = await purgar_capturas_vencidas(s, dias=180)
        await s.commit()

    assert purgadas == 1
    async with factory() as s:
        assert (await s.get(ProctoringEventModel, protegido)).screenshot_b64 is not None
        assert (await s.get(ProctoringEventModel, purgable)).screenshot_b64 is None


@pytest.mark.asyncio
async def test_purgar_capturas_rechaza_dias_por_debajo_del_minimo(factory):
    await _crear_sesion_con_evento(factory, creada_hace_dias=200)
    async with factory() as s:
        with pytest.raises(ValueError, match="90"):
            await purgar_capturas_vencidas(s, dias=30)


# ---------------------------------------------------------------------------
# configuracion_sistema.retencion_capturas_dias — default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_retencion_capturas_dias_es_180(factory):
    async with factory() as s:
        cfg = await ConfiguracionSistemaSqlRepository(s).ensure_singleton()
        await s.commit()
        assert cfg.retencion_capturas_dias == 180


# ---------------------------------------------------------------------------
# Endpoints HTTP — PATCH /api/v1/config + POST /api/v1/admin/retention/capturas
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(factory) -> FastAPI:
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.include_router(config_router, prefix="/api/v1/config")
    application.include_router(admin_retention_router, prefix="/api/v1/admin")
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_patch_config_rechaza_retencion_capturas_por_debajo_del_minimo(client):
    resp = await client.patch(
        "/api/v1/config",
        json={"retencion_capturas_dias": 30},
        headers=auth_headers(["admin_sistema"]),
    )
    assert resp.status_code == 422
    cuerpo = resp.json()
    assert "90" in str(cuerpo)


@pytest.mark.asyncio
async def test_patch_config_acepta_retencion_capturas_en_el_piso(client):
    resp = await client.patch(
        "/api/v1/config",
        json={"retencion_capturas_dias": 90},
        headers=auth_headers(["admin_sistema"]),
    )
    assert resp.status_code == 200
    assert resp.json()["retencion_capturas_dias"] == 90

    efectiva = await client.get(
        "/api/v1/config/effective", headers=auth_headers(["admin_sistema"])
    )
    assert efectiva.json()["retencion_capturas_dias"] == 90


@pytest.mark.asyncio
async def test_purgar_capturas_endpoint_exige_admin_sistema(client):
    resp = await client.post(
        "/api/v1/admin/retention/capturas",
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_purgar_capturas_endpoint_purga_segun_config_y_audita(client, factory):
    # Config default (180 dias) — sesion de 200 dias cae, sesion de 5 dias no.
    await _crear_sesion_con_evento(factory, creada_hace_dias=200)
    _, evento_reciente_id = await _crear_sesion_con_evento(factory, creada_hace_dias=5)

    async with factory() as s:
        audit_antes = (
            await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == "retention.capturas.purgadas"
                )
            )
        ).all()

    resp = await client.post(
        "/api/v1/admin/retention/capturas",
        headers=auth_headers(["admin_sistema"], subject="admin-test"),
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["capturas_purgadas"] == 1
    assert cuerpo["retencion_capturas_dias"] == 180

    async with factory() as s:
        evento_reciente = await s.get(ProctoringEventModel, evento_reciente_id)
        assert evento_reciente.screenshot_b64 is not None

        audit_despues = (
            await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == "retention.capturas.purgadas"
                )
            )
        ).all()
    assert len(audit_despues) == len(audit_antes) + 1


@pytest.mark.asyncio
async def test_purgar_capturas_endpoint_audita_incluso_con_cero_purgadas(client, factory):
    """0 purgadas TAMBIEN se audita: deja constancia de que se corrio."""
    resp = await client.post(
        "/api/v1/admin/retention/capturas",
        headers=auth_headers(["admin_sistema"], subject="admin-test"),
    )
    assert resp.status_code == 200
    assert resp.json()["capturas_purgadas"] == 0

    async with factory() as s:
        filas = (
            await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == "retention.capturas.purgadas"
                )
            )
        ).all()
    assert len(filas) == 1
