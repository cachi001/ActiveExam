"""Read-model de resultados de un examen para el admin (C-69 admin-sync, tarea 2).

Deriva de proctoring_session (sesiones FINALIZADAS vinculadas al examen) + el estado
de write-back (moodle_writeback_estado, LEFT JOIN) + la nota calculada/persistida.

L2.5 / D3: NUNCA expone es_correcta ni las respuestas — solo identidad del alumno,
nota académica, estado del envío a Moodle y la marca de actualización.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

# Estados de display posibles para el admin.
ESTADO_SIN_TOKEN = "sin_token"
ESTADO_PENDIENTE = "pendiente"


@dataclass(frozen=True, slots=True)
class ResultadoAlumno:
    """Una fila de resultados: identidad + nota + estado del envío a Moodle."""

    session_id: str
    alumno_idnumber: str | None
    alumno_email: str | None
    alumno_nombre: str | None
    nota: float | None
    estado_moodle: str
    actualizado_en: object | None  # datetime tz-aware (lo serializa Pydantic)


def estado_moodle_display(db_estado: str | None, *, moodle_configurado: bool) -> str:
    """Mapea el estado persistido al estado que ve el admin.

    Si Moodle no está configurado, una nota 'pendiente' se muestra como 'sin_token'
    (no se puede enviar todavía). 'enviado'/'fallido' se muestran tal cual.
    """
    estado = db_estado or ESTADO_PENDIENTE
    if not moodle_configurado and estado == ESTADO_PENDIENTE:
        return ESTADO_SIN_TOKEN
    return estado


def _base_stmt(examen_id: str):
    """Sesiones FINALIZADAS del examen + su estado de write-back (LEFT JOIN)."""
    return (
        select(
            ProctoringSessionModel.id.label("session_id"),
            ProctoringSessionModel.finalizada_en.label("finalizada_en"),
            MoodleWritebackEstadoModel.alumno_idnumber,
            MoodleWritebackEstadoModel.alumno_email,
            MoodleWritebackEstadoModel.nota,
            MoodleWritebackEstadoModel.estado,
            MoodleWritebackEstadoModel.updated_at,
        )
        .select_from(ProctoringSessionModel)
        .outerjoin(
            MoodleWritebackEstadoModel,
            MoodleWritebackEstadoModel.session_id == ProctoringSessionModel.id,
        )
        .where(
            ProctoringSessionModel.examen_contenido_id == examen_id,
            ProctoringSessionModel.finalizada_en.isnot(None),
        )
    )


def _aplicar_filtros(stmt, *, q: str | None, estado: str | None):
    """Búsqueda por alumno (idnumber/email) y filtro por estado — SIEMPRE en SQL."""
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                MoodleWritebackEstadoModel.alumno_idnumber.ilike(patron),
                MoodleWritebackEstadoModel.alumno_email.ilike(patron),
            )
        )
    if estado:
        # 'sin_token' es un alias de display de 'pendiente' (mismo valor en DB).
        db_estado = ESTADO_PENDIENTE if estado == ESTADO_SIN_TOKEN else estado
        stmt = stmt.where(
            func.coalesce(MoodleWritebackEstadoModel.estado, ESTADO_PENDIENTE) == db_estado
        )
    return stmt


async def listar_resultados_examen(
    *,
    db: AsyncSession,
    examen_id: str,
    q: str | None = None,
    estado: str | None = None,
    page: int = 1,
    page_size: int = 20,
    moodle_configurado: bool = True,
) -> tuple[list[ResultadoAlumno], int]:
    """Lista paginada de alumnos que rindieron el examen + total global filtrado.

    Orden estable: por finalizada_en descendente (más reciente primero), luego
    session_id para desempatar. Filtrado/orden SIEMPRE serverside (SQL).
    """
    page = max(1, page)
    page_size = max(1, page_size)

    base = _aplicar_filtros(_base_stmt(examen_id), q=q, estado=estado)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    page_stmt = (
        base.order_by(
            ProctoringSessionModel.finalizada_en.desc(),
            ProctoringSessionModel.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(page_stmt)).all()

    items = [
        ResultadoAlumno(
            session_id=row.session_id,
            alumno_idnumber=row.alumno_idnumber,
            alumno_email=row.alumno_email,
            alumno_nombre=None,  # identidad por idnumber/email; nombre = enhancement futuro
            nota=float(row.nota) if row.nota is not None else None,
            estado_moodle=estado_moodle_display(
                row.estado, moodle_configurado=moodle_configurado
            ),
            actualizado_en=row.updated_at or row.finalizada_en,
        )
        for row in rows
    ]
    return items, int(total)


async def listar_estados_sincronizables(
    *, db: AsyncSession, examen_id: str
) -> list[MoodleWritebackEstadoModel]:
    """Filas de write-back en estado 'pendiente'/'fallido' del examen (para sincronizar).

    Las 'enviado' se excluyen (idempotencia: no se re-mandan).
    """
    stmt = (
        select(MoodleWritebackEstadoModel)
        .join(
            ProctoringSessionModel,
            ProctoringSessionModel.id == MoodleWritebackEstadoModel.session_id,
        )
        .where(
            ProctoringSessionModel.examen_contenido_id == examen_id,
            MoodleWritebackEstadoModel.estado.in_(
                (ESTADO_PENDIENTE, "fallido")
            ),
        )
    )
    return list((await db.execute(stmt)).scalars().all())
