"""C-69 — enforcement SERVER-SIDE de ventana e intentos al crear la sesion.

Backstop duro (el frontend ya gatea, pero el cliente es un sensor no confiable,
regla dura #6). Solo aplica cuando la sesion se vincula a un ``examen_contenido_id``.

DB real (DATABASE_URL). Sin mocks de DB (regla dura de codigo). Reusa las fixtures
del conftest de proctoring (``client`` autenticado como estudiante, ``db_session``,
``slim_engine``). El alumno por defecto: id_institucional="estudiante",
email="test@uni.edu".

Correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_c69_sesion_enforcement.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

pytestmark = pytest.mark.asyncio

_ALUMNO = "estudiante"  # id_institucional del token por defecto del fixture client


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _crear_examen(
    db: AsyncSession,
    *,
    apertura: datetime | None = None,
    cierre: datetime | None = None,
    intentos_permitidos: int = 1,
) -> str:
    """Inserta un examen_contenido con la config dada y devuelve su id."""
    examen = ExamenContenidoModel(
        titulo="Examen enforcement",
        apertura=apertura,
        cierre=cierre,
        intentos_permitidos=intentos_permitidos,
    )
    db.add(examen)
    await db.commit()
    await db.refresh(examen)
    return examen.id


async def _sesion_finalizada(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    alumno_idnumber: str,
) -> None:
    """Inserta una sesion FINALIZADA del alumno para ese examen (cuenta como intento)."""
    sesion = ProctoringSessionModel(
        modo="examen",
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        finalizada_en=_now(),
    )
    db.add(sesion)
    await db.commit()


# ---------------------------------------------------------------------------
# Ventana de rendicion
# ---------------------------------------------------------------------------


async def test_crear_sesion_dentro_de_ventana_ok(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Dentro de [apertura, cierre] y con intentos disponibles → 201."""
    examen_id = await _crear_examen(
        db_session,
        apertura=_now() - timedelta(hours=1),
        cierre=_now() + timedelta(hours=1),
        intentos_permitidos=3,
    )
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 201
    assert resp.json()["examen_contenido_id"] == examen_id


async def test_crear_sesion_antes_de_apertura_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Antes de la apertura → 403 fuera_de_ventana."""
    apertura = _now() + timedelta(hours=2)
    examen_id = await _crear_examen(db_session, apertura=apertura)

    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 403
    detalle = resp.json()["detail"]
    assert detalle["error"] == "fuera_de_ventana"
    assert detalle["apertura"] is not None


async def test_crear_sesion_despues_de_cierre_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Despues del cierre → 403 fuera_de_ventana."""
    cierre = _now() - timedelta(hours=1)
    examen_id = await _crear_examen(db_session, cierre=cierre)

    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 403
    detalle = resp.json()["detail"]
    assert detalle["error"] == "fuera_de_ventana"
    assert detalle["cierre"] is not None


# ---------------------------------------------------------------------------
# Intentos permitidos
# ---------------------------------------------------------------------------


async def test_crear_sesion_intentos_agotados_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Con rendidos >= intentos_permitidos → 409 intentos_agotados."""
    examen_id = await _crear_examen(db_session, intentos_permitidos=2)
    # 2 sesiones finalizadas del alumno para ese examen
    await _sesion_finalizada(db_session, examen_contenido_id=examen_id, alumno_idnumber=_ALUMNO)
    await _sesion_finalizada(db_session, examen_contenido_id=examen_id, alumno_idnumber=_ALUMNO)

    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 409
    detalle = resp.json()["detail"]
    assert detalle["error"] == "intentos_agotados"
    assert detalle["intentos_permitidos"] == 2
    assert detalle["rendidos"] == 2


async def test_crear_sesion_intentos_disponibles_ok(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Con rendidos < intentos_permitidos → 201. Solo cuenta al alumno y finalizadas."""
    examen_id = await _crear_examen(db_session, intentos_permitidos=2)
    # 1 finalizada del alumno (cuenta)
    await _sesion_finalizada(db_session, examen_contenido_id=examen_id, alumno_idnumber=_ALUMNO)
    # 3 finalizadas de OTRO alumno (NO cuentan — filtro por alumno_idnumber)
    for _ in range(3):
        await _sesion_finalizada(
            db_session, examen_contenido_id=examen_id, alumno_idnumber="otro-alumno"
        )
    # 1 EN CURSO del alumno (NO cuenta — finalizada_en IS NULL)
    en_curso = ProctoringSessionModel(
        modo="examen", examen_contenido_id=examen_id, alumno_idnumber=_ALUMNO
    )
    db_session.add(en_curso)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Sin examen / config por defecto + persistencia de identidad
# ---------------------------------------------------------------------------


async def test_sin_examen_contenido_no_aplica_enforcement(
    client: AsyncClient,
) -> None:
    """Sesion sin examen_contenido_id (modo 'test') → 201 sin enforcement."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "etiqueta": "prueba"},
    )
    assert resp.status_code == 201


async def test_examen_sin_ventana_ni_intentos_previos_ok(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Examen con config por defecto (sin apertura/cierre, intentos=1, 0 rendidos) → 201."""
    examen_id = await _crear_examen(db_session)  # intentos_permitidos=1 por default
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 201


async def test_identidad_alumno_se_persiste(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Al crear la sesion se persiste alumno_idnumber/alumno_email del JWT."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    row = (
        await db_session.execute(
            select(ProctoringSessionModel).where(
                ProctoringSessionModel.id == session_id
            )
        )
    ).scalar_one()
    assert row.alumno_idnumber == _ALUMNO
    assert row.alumno_email == "test@uni.edu"
