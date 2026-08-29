"""La purga de capturas vencidas corre SOLA (decisión del dueño, 28/8/2026).

## Por qué existe

El consentimiento le declara al alumno un plazo concreto: las fotos que toma la
cámara se borran a los 180 días. Ese plazo solo es cierto si alguien lo ejecuta,
y hasta ahora dependía de que un admin se acordara de apretar
``POST /api/v1/admin/retention/capturas``. Prometer un borrado que nadie dispara
es exactamente lo que este proyecto ya corrigió una vez en el texto v1.

## El límite que NO se puede cruzar

Decisión explícita del dueño: **no se borran registros ni sesiones de examen,
son pruebas**. La purga automática toca UNA sola cosa: la imagen. El evento, su
``screenshot_sha256``, el puntero WORM y la sesión quedan intactos, así el
examen sigue siendo defendible ante un reclamo aunque la cara ya no se vea.

Los tests de abajo fijan ese límite: si alguien engancha la purga de sesiones
(``retention/session``, que sí borra filas) al arranque, se rompen.

TDD Cycle: RED -> GREEN -> TRIANGULATE -> REFACTOR.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.compliance.purga_programada import (
    ejecutar_purga_programada,
    programar_purga_capturas,
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
from tests._audit_schema import DDL_COMPLETA as _AUDIT_DDL

_TABLES_TO_DROP = [
    "proctoring_event",
    "proctoring_session",
    "examen_contenido",
    "configuracion_sistema",
    "audit_log",
]
_TABLES_TO_CREATE = [
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


@pytest_asyncio.fixture(autouse=True)
async def _limpiar_entre_tests(engine):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE proctoring_event, proctoring_session, configuracion_sistema, "
                "audit_log RESTART IDENTITY CASCADE"
            )
        )
    yield


async def _crear_sesion_con_evento(
    factory: async_sessionmaker[AsyncSession], *, creada_hace_dias: int
) -> tuple[str, str]:
    """Crea una sesion + 1 evento CON captura. Devuelve (session_id, event_id)."""
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen", etiqueta=f"purga-auto-{uuid.uuid4().hex[:8]}"
        )
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
            screenshot_sha256="b" * 64,
        )
        s.add(evento)
        await s.flush()
        await s.commit()
        return sesion.id, evento.id


async def _contar(factory, modelo) -> int:
    async with factory() as s:
        return (await s.execute(select(func.count()).select_from(modelo))).scalar_one()


# ---------------------------------------------------------------------------
# ejecutar_purga_programada — el ciclo completo sin pasar por HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_borra_la_imagen_vencida_leyendo_el_plazo_de_la_config(factory):
    """El plazo NO se hardcodea: sale de configuracion_sistema (default 180)."""
    async with factory() as s:
        cfg = await ConfiguracionSistemaSqlRepository(s).ensure_singleton()
        await s.commit()
        assert cfg.retencion_capturas_dias == 180

    _, evento_id = await _crear_sesion_con_evento(factory, creada_hace_dias=200)

    purgadas = await ejecutar_purga_programada(factory)

    assert purgadas == 1
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 is None


@pytest.mark.asyncio
async def test_no_borra_ni_la_sesion_ni_el_evento(factory):
    """El límite duro: la evidencia del examen es prueba y no se elimina.

    Si esto falla, alguien enganchó al arranque una purga que borra filas.
    """
    _, evento_id = await _crear_sesion_con_evento(factory, creada_hace_dias=400)

    await ejecutar_purga_programada(factory)

    assert await _contar(factory, ProctoringSessionModel) == 1
    assert await _contar(factory, ProctoringEventModel) == 1
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        # Queda constancia de QUE se capturó y con qué huella: solo falta la imagen.
        assert evento.screenshot_sha256 == "b" * 64
        assert evento.tipo == "FACE_ABSENT"
        assert evento.severidad == "medio"


@pytest.mark.asyncio
async def test_no_toca_las_capturas_que_todavia_no_vencieron(factory):
    """Triangulación: una sesión de 5 días conserva su imagen."""
    _, evento_id = await _crear_sesion_con_evento(factory, creada_hace_dias=5)

    purgadas = await ejecutar_purga_programada(factory)

    assert purgadas == 0
    async with factory() as s:
        evento = await s.get(ProctoringEventModel, evento_id)
        assert evento.screenshot_b64 == "ZmFrZS1iYXNlNjQtaW1hZ2U="


@pytest.mark.asyncio
async def test_deja_traza_en_el_audit_log(factory):
    """Un borrado de evidencia sin auditar es un borrado que nadie puede explicar."""
    await _crear_sesion_con_evento(factory, creada_hace_dias=200)

    await ejecutar_purga_programada(factory)

    async with factory() as s:
        filas = (await s.execute(select(AuditLogModel))).scalars().all()
    assert len(filas) == 1
    assert "sistema" in filas[0].actor
    assert "180" in (filas[0].proposito or "")


@pytest.mark.asyncio
async def test_es_idempotente(factory):
    """Correrla dos veces seguidas no purga de nuevo ni cuenta de más."""
    await _crear_sesion_con_evento(factory, creada_hace_dias=200)

    primera = await ejecutar_purga_programada(factory)
    segunda = await ejecutar_purga_programada(factory)

    assert (primera, segunda) == (1, 0)


@pytest.mark.asyncio
async def test_no_rompe_el_arranque_si_la_base_falla(factory):
    """Best-effort: la purga jamás puede impedir que la app levante.

    Se le pasa una factory que revienta al abrir sesión; tiene que devolver 0
    en vez de propagar.
    """

    def _factory_rota():
        raise RuntimeError("base caída")

    assert await ejecutar_purga_programada(_factory_rota) == 0


# ---------------------------------------------------------------------------
# programar_purga_capturas — la tarea de fondo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_la_tarea_de_fondo_purga_al_arrancar(factory):
    """Render duerme el proceso: si solo corriera cada 24h podría no correr nunca.

    Por eso la primera pasada es al arrancar, no dentro de un día.
    """
    _, evento_id = await _crear_sesion_con_evento(factory, creada_hace_dias=200)

    tarea = programar_purga_capturas(factory, intervalo_horas=24, demora_inicial_seg=0)
    try:
        for _ in range(50):
            await asyncio.sleep(0.05)
            async with factory() as s:
                evento = await s.get(ProctoringEventModel, evento_id)
                if evento.screenshot_b64 is None:
                    break
        else:
            pytest.fail("la tarea de fondo no purgó al arrancar")
    finally:
        tarea.cancel()


@pytest.mark.asyncio
async def test_la_tarea_de_fondo_se_puede_cancelar(factory):
    """El shutdown de la app la cancela: no debe quedar colgada ni tragarse el cancel."""
    tarea = programar_purga_capturas(factory, intervalo_horas=24, demora_inicial_seg=0)
    await asyncio.sleep(0.05)
    tarea.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarea
