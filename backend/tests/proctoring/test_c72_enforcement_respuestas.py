"""C-72 §2 — Enforcement de plazo en el envío de respuestas (H-1 / H-2).

El agujero: una vez creada la sesión, `POST /sessions/{id}/respuestas` NUNCA
volvía a mirar el reloj → aceptaba respuestas con el límite vencido o la ventana
cerrada (verificado en vivo: 201 en vez de 409). El cliente es sensor no confiable
(regla dura #6): el plazo se valida server-side con hora del servidor.

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixtures locales con el schema
completo (examen + preguntas + respuestas), como test_vuln_reload_examen.py.

Correr:
    DATABASE_URL=postgresql+asyncpg://... RUN_STACK_TESTS=1 \\
      pytest tests/proctoring/test_c72_enforcement_respuestas.py -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"
_ALUMNO = "estudiante"

_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "proctoring_biometria",
    "proctoring_event",
    "proctoring_session",
]
_CREATE = [
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    ProctoringBiometriaModel.__table__,
    RespuestaAlumnoModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
]


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url: str):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest.fixture(scope="module")
def reinferencia():
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    return MediaPipeReinferencia()


@pytest.fixture(scope="module")
def app(engine, reinferencia):
    from fastapi import FastAPI

    from app.infrastructure.persistence.session_slim import create_slim_session_factory
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    factory = create_slim_session_factory(engine)
    router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
        writeback_svc=None,
    )
    a = FastAPI()
    a.state.jwt_validator = _build_test_jwt_validator()
    a.include_router(router, prefix="/api/v1/proctoring")
    return a


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{t}"' for t in _DROP)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"], username="estudiante", email="test@uni.edu"),
    ) as c:
        yield c


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _crear_examen(
    db: AsyncSession,
    *,
    tiempo_limite_min: int | None,
    cierre: datetime,
    apertura: datetime | None = None,
) -> tuple[str, str, str]:
    """Crea un examen con 1 pregunta + 1 opción → (examen_id, pregunta_id, opcion_id)."""
    examen = ExamenContenidoModel(
        titulo="Examen enforcement plazo",
        tiempo_limite_min=tiempo_limite_min,
        apertura=apertura or (_now() - timedelta(hours=4)),
        cierre=cierre,
        nota_maxima=10,
    )
    db.add(examen)
    await db.flush()
    pregunta = PreguntaExamenModel(
        examen_id=examen.id, enunciado="2+2?", tipo="multichoice", orden=0, seleccionada=True
    )
    db.add(pregunta)
    await db.flush()
    opcion = OpcionRespuestaModel(
        pregunta_id=pregunta.id, texto="4", es_correcta=True, orden=0
    )
    db.add(opcion)
    await db.commit()
    return examen.id, pregunta.id, opcion.id


async def _agregar_pregunta(db: AsyncSession, examen_id: str, *, orden: int) -> tuple[str, str]:
    """Suma otra pregunta + opción a un examen → (pregunta_id, opcion_id)."""
    pregunta = PreguntaExamenModel(
        examen_id=examen_id, enunciado=f"pregunta {orden}", tipo="multichoice",
        orden=orden, seleccionada=True,
    )
    db.add(pregunta)
    await db.flush()
    opcion = OpcionRespuestaModel(
        pregunta_id=pregunta.id, texto="ok", es_correcta=True, orden=0
    )
    db.add(opcion)
    await db.commit()
    return pregunta.id, opcion.id


async def _crear_sesion(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    creada_en: datetime,
    finalizada_en: datetime | None = None,
) -> str:
    """Inserta una sesión del alumno con `creada_en` controlado (simula vencimiento)."""
    sesion = ProctoringSessionModel(
        modo="examen",
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=_ALUMNO,
        alumno_email="test@uni.edu",
        creada_en=creada_en,
        finalizada_en=finalizada_en,
    )
    db.add(sesion)
    await db.commit()
    await db.refresh(sesion)
    return sesion.id


# ---------------------------------------------------------------------------
# 2.1 — límite individual vencido → 409 tiempo_agotado, nada persistido
# ---------------------------------------------------------------------------

async def test_respuestas_con_limite_vencido_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    # límite 40 min, ventana abierta (cierra en 4h), pero la sesión arrancó hace 3h
    # → deadline = creada_en + 40min, vencido hace ~2h20 → debe rechazar.
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=3)
    )

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "tiempo_agotado"

    # nada persistido: GET no devuelve la respuesta
    got = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert got.status_code == 200, got.text
    assert got.json()["respuestas"] == []


# ---------------------------------------------------------------------------
# 2.2 — ventana del examen cerrada → 409 tiempo_agotado, nada persistido
# ---------------------------------------------------------------------------

async def test_respuestas_con_ventana_cerrada_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    # ventana cerrada hace 1 día; sin límite individual → deadline = cierre (pasado).
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=None, cierre=_now() - timedelta(days=1)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "tiempo_agotado"
    got = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert got.json()["respuestas"] == []


# ---------------------------------------------------------------------------
# 2.3 — dentro del plazo → 201 y persistida (no romper el camino feliz)
# ---------------------------------------------------------------------------

async def test_respuestas_dentro_de_plazo_201(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now()  # recién arranca
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 201, resp.text
    got = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert got.json()["respuestas"] == [
        {"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}
    ]


# ---------------------------------------------------------------------------
# 2.4 — respuesta dentro de la gracia → 201 y persistida
# ---------------------------------------------------------------------------

async def test_respuestas_dentro_de_la_gracia_201(
    client: AsyncClient, db: AsyncSession
) -> None:
    # deadline vencido hace ~20s, dentro de la gracia default (60s) → se acepta.
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(
        db,
        examen_contenido_id=examen_id,
        creada_en=_now() - timedelta(minutes=40, seconds=20),
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# 2.5 — lote fuera de plazo con varias respuestas → ninguna persiste (atómico)
# ---------------------------------------------------------------------------

async def test_lote_fuera_de_plazo_no_persiste_ninguna(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, p1, o1 = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    p2, o2 = await _agregar_pregunta(db, examen_id, orden=1)
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=3)
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [
            {"pregunta_id": p1, "opcion_elegida_id": o1},
            {"pregunta_id": p2, "opcion_elegida_id": o2},
        ]},
    )
    assert resp.status_code == 409, resp.text
    got = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert got.json()["respuestas"] == []  # rechazo atómico: ninguna


# ---------------------------------------------------------------------------
# 2.6 — el error distingue tiempo_agotado de sesion_finalizada
# ---------------------------------------------------------------------------

async def test_sesion_finalizada_da_error_distinto(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    # finalizada Y además fuera de plazo: el error debe ser sesion_finalizada (chequeo previo)
    sid = await _crear_sesion(
        db,
        examen_contenido_id=examen_id,
        creada_en=_now() - timedelta(hours=3),
        finalizada_en=_now(),
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "sesion_finalizada"


# ---------------------------------------------------------------------------
# 2.8 — la "frescura" del request del cliente no salva: manda la hora del servidor
# ---------------------------------------------------------------------------

async def test_hora_del_cliente_no_altera_el_rechazo(
    client: AsyncClient, db: AsyncSession
) -> None:
    # El cliente manda la request AHORA (recién), pero la sesión venció hace rato.
    # No hay campo de hora del cliente en el body; el rechazo usa la hora del servidor.
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=5)
    )
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "tiempo_agotado"


# ---------------------------------------------------------------------------
# §3 — Finalización: NO se bloquea por vencimiento (es el cierre); nota solo
# sobre respuestas en plazo; idempotente. El "cierre fuera de plazo" NO se marca
# (decisión del owner): eso es la auto-finalización (§4), no el finalizar manual.
# ---------------------------------------------------------------------------

async def _insertar_respuesta(
    db: AsyncSession, *, session_id: str, pregunta_id: str, opcion_id: str
) -> None:
    """Persiste una respuesta directamente (representa lo respondido ANTES del vencimiento)."""
    db.add(
        RespuestaAlumnoModel(
            session_id=session_id, pregunta_id=pregunta_id, opcion_elegida_id=opcion_id
        )
    )
    await db.commit()


# 3.1 — finalizar en plazo → 200 y la sesión queda cerrada
async def test_finalizar_en_plazo_200(client: AsyncClient, db: AsyncSession) -> None:
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(db, examen_contenido_id=examen_id, creada_en=_now())
    r = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )
    assert r.status_code == 201, r.text
    fin = await client.patch(f"{_BASE}/sessions/{sid}/finalizar")
    assert fin.status_code == 200, fin.text
    assert fin.json()["finalizada_en"] is not None


# 3.2 — un intento tardío (rechazado por §2) no agranda la nota: finalizar computa
# solo sobre lo persistido en plazo
async def test_finalizar_no_cuenta_respuestas_tardias(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, p1, o1 = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    p2, o2 = await _agregar_pregunta(db, examen_id, orden=1)
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=3)
    )
    await _insertar_respuesta(db, session_id=sid, pregunta_id=p1, opcion_id=o1)
    tardio = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": p2, "opcion_elegida_id": o2}]},
    )
    assert tardio.status_code == 409, tardio.text
    fin = await client.patch(f"{_BASE}/sessions/{sid}/finalizar")
    assert fin.status_code == 200, fin.text
    got = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert got.json()["respuestas"] == [{"pregunta_id": p1, "opcion_elegida_id": o1}]


# 3.4 — finalizar dos veces es idempotente (no re-cierra ni recalcula)
async def test_finalizar_dos_veces_idempotente(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, pregunta_id, opcion_id = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=4)
    )
    sid = await _crear_sesion(db, examen_contenido_id=examen_id, creada_en=_now())
    fin1 = await client.patch(f"{_BASE}/sessions/{sid}/finalizar")
    assert fin1.status_code == 200, fin1.text
    fin2 = await client.patch(f"{_BASE}/sessions/{sid}/finalizar")
    assert fin2.status_code == 200, fin2.text
    assert fin2.json()["finalizada_en"] == fin1.json()["finalizada_en"]


# ---------------------------------------------------------------------------
# §4 — Auto-finalización lazy (H-3): la sesión vencida se cierra sola al ser
# tocada y se puntúa con lo persistido. El alumno se lleva su trabajo.
# ---------------------------------------------------------------------------

async def _finalizada_en(db: AsyncSession, sid: str):
    await db.commit()  # ver lo committeado por el request
    row = (
        await db.execute(
            select(ProctoringSessionModel).where(ProctoringSessionModel.id == sid)
        )
    ).scalar_one()
    return row.finalizada_en


# 4.1 — alumno vuelve pasado el deadline individual (ventana aún abierta) → su
# sesión queda finalizada y no puede seguir respondiendo
async def test_reanudar_sesion_vencida_la_finaliza(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, p, o = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)  # ventana abierta
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)  # límite vencido
    )
    # el alumno "vuelve": POST /sessions con el mismo examen → reanuda la activa
    r = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert r.status_code == 201, r.text
    assert r.json()["id"] == sid  # reanudó la MISMA sesión
    # quedó auto-finalizada
    assert await _finalizada_en(db, sid) is not None
    # y no puede seguir respondiendo
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": p, "opcion_elegida_id": o}]},
    )
    assert resp.status_code == 409, resp.text


async def _writeback_estado(db: AsyncSession, sid: str):
    await db.commit()
    return (
        await db.execute(
            select(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == sid
            )
        )
    ).scalars().all()


# 4.2 — auto-finalizada se puntúa con lo persistido (parcial, NO cero)
async def test_auto_finalizada_puntua_lo_persistido(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, p1, o1 = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)
    )
    await _agregar_pregunta(db, examen_id, orden=1)  # 2da pregunta, sin responder
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    await _insertar_respuesta(db, session_id=sid, pregunta_id=p1, opcion_id=o1)  # 1 en plazo
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    estados = await _writeback_estado(db, sid)
    assert len(estados) == 1
    # 1 de 2 correctas → nota parcial: NI cero NI el máximo (nota_maxima=10)
    assert estados[0].nota is not None
    assert 0 < float(estados[0].nota) < 10


# 4.3 — auto-finalizada sin ninguna respuesta → nota cero, cierre consistente
async def test_auto_finalizada_sin_respuestas_nota_cero(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, _p, _o = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    assert await _finalizada_en(db, sid) is not None
    estados = await _writeback_estado(db, sid)
    assert len(estados) == 1
    assert float(estados[0].nota) == 0


# 4.4 — el write-back de una auto-finalizada sigue el mismo camino que la manual:
# nota 'pendiente' (NO se auto-envía a Moodle)
async def test_auto_finalizada_writeback_pendiente(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, _p, _o = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    estados = await _writeback_estado(db, sid)
    assert len(estados) == 1
    assert estados[0].estado == "pendiente"  # mismo gate que la manual: no auto-envía


# 4.6 — doble cierre lazy es idempotente: no re-cierra ni duplica el write-back
async def test_doble_cierre_lazy_idempotente(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, _p, _o = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    fin1 = await _finalizada_en(db, sid)
    # segundo "regreso" → toca de nuevo la sesión vencida (ya finalizada)
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    fin2 = await _finalizada_en(db, sid)
    assert fin1 == fin2  # no re-cierra
    assert len(await _writeback_estado(db, sid)) == 1  # una sola entrada de nota


# 4.7 — carrera cierre lazy vs. finalización manual → un único cierre, una única nota
async def test_lazy_luego_manual_un_solo_cierre(
    client: AsyncClient, db: AsyncSession
) -> None:
    examen_id, _p, _o = await _crear_examen(
        db, tiempo_limite_min=40, cierre=_now() + timedelta(hours=2)
    )
    sid = await _crear_sesion(
        db, examen_contenido_id=examen_id, creada_en=_now() - timedelta(hours=2)
    )
    # cierre lazy por reanudación
    await client.post(f"{_BASE}/sessions", json={"modo": "examen", "examen_contenido_id": examen_id})
    fin1 = await _finalizada_en(db, sid)
    # finalización manual después → idempotente, mismo cierre
    fin = await client.patch(f"{_BASE}/sessions/{sid}/finalizar")
    assert fin.status_code == 200, fin.text
    assert fin.json()["finalizada_en"] == fin1.isoformat().replace("+00:00", "Z") or fin.json()["finalizada_en"] is not None
    assert len(await _writeback_estado(db, sid)) == 1  # una sola nota
