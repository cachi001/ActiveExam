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

from app.application.proctoring.scoring import calcular_score
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)

# Estados de display posibles para el admin.
ESTADO_SIN_TOKEN = "sin_token"
ESTADO_PENDIENTE = "pendiente"

# Umbral de cola de revision por defecto si el singleton de config no existe (mismo
# default que ConfiguracionSistemaModel.umbral_cola_revision y el mock del frontend).
UMBRAL_COLA_REVISION_DEFAULT = 70


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


async def obtener_target_examen(
    *, db: AsyncSession, examen_id: str
) -> tuple[int | None, int | None]:
    """Destino de write-back POR EXAMEN actual (moodle_courseid, moodle_cmid).

    D12 (parte B). Devuelve (None, None) si el examen no existe o no tiene destino
    propio (en cuyo caso el write-back cae al global).
    """
    row = await db.execute(
        select(
            ExamenContenidoModel.moodle_courseid,
            ExamenContenidoModel.moodle_cmid,
        ).where(ExamenContenidoModel.id == examen_id)
    )
    target = row.one_or_none()
    if target is None:
        return None, None
    return target.moodle_courseid, target.moodle_cmid


async def listar_estados_sincronizables(
    *, db: AsyncSession, examen_id: str
) -> list[MoodleWritebackEstadoModel]:
    """Filas de write-back en estado 'pendiente'/'fallido' del examen (para sincronizar).

    Las 'enviado' se excluyen (idempotencia: no se re-mandan).

    D12 (parte B): refresca el destino (moodle_courseid/cmid) de cada fila desde el
    valor ACTUAL del examen, para que un admin que fija el target DESPUÉS de finalizar
    sincronice al curso correcto. NULL en el examen → la fila queda NULL y el cliente
    cae al global. El refresco es en memoria sobre la misma sesión (mismo identity map);
    el commit del caller lo persiste.
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
    filas = list((await db.execute(stmt)).scalars().all())

    courseid, cmid = await obtener_target_examen(db=db, examen_id=examen_id)
    for fila in filas:
        fila.moodle_courseid = courseid
        fila.moodle_cmid = cmid

    return filas


# ===========================================================================
# Read-model de "mis notas" para el ALUMNO (C-69, student-facing).
#
# Mismo origen de datos que el read-model del admin (proctoring_session FINALIZADA
# + moodle_writeback_estado), pero SCOPED a un solo alumno (idnumber/email del JWT)
# y enriquecido con el estado L2.5 "en cola de revision": el score de la sesion vs
# el umbral_cola_revision del singleton de config. score >= umbral -> en cola.
#
# Consistente con la Cola de revision humana:
# - umbral  = configuracion_sistema.umbral_cola_revision (ConfigService.get_efectiva)
# - score   = calcular_score(eventos) con pesos vivos por tipo (evento_score_config)
#             — la MISMA funcion que usa el detalle de sesion del proctor.
# - compara = score >= umbral (igual que el frontend `enriquecerYFiltrar`).
#
# L2.5 / D3: NUNCA expone es_correcta ni respuestas. El score PRIORIZA, no sanciona.
# ===========================================================================


@dataclass(frozen=True, slots=True)
class MiNota:
    """Una fila de "mis notas": nota academica + estado de envio + estado L2.5."""

    examen_id: str
    examen_titulo: str
    nota: float | None
    nota_maxima: float | None
    aprobado: bool
    estado_moodle: str
    en_cola_revision: bool
    score: float | None
    umbral_revision: float | None
    eventos: int
    finalizada_en: object | None  # datetime tz-aware (lo serializa Pydantic)


async def _umbral_cola_revision(db: AsyncSession) -> int:
    """Umbral de cola de revision desde el singleton de config (default si falta).

    Misma fuente que la Cola de revision humana (ConfigService.get_efectiva
    -> ConfiguracionSistemaModel.umbral_cola_revision). Degradacion graceful: si la
    tabla/singleton no esta disponible, cae al default institucional (70)."""
    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
    )

    try:
        row = await db.execute(select(ConfiguracionSistemaModel.umbral_cola_revision))
        val = row.scalars().first()
    except Exception:  # noqa: BLE001 — degradacion: sin config, usa el default
        return UMBRAL_COLA_REVISION_DEFAULT
    return int(val) if val is not None else UMBRAL_COLA_REVISION_DEFAULT


async def _pesos_vivos_por_tipo(db: AsyncSession) -> dict[str, int] | None:
    """Pesos vivos por tipo de evento desde evento_score_config (activos).

    None si la tabla no esta disponible (degradacion graceful, RN-GLB-03): en ese
    caso calcular_score cae al fallback por severidad. Misma fuente que el detalle
    de sesion del proctor (consumo server-side de la config, no constantes)."""
    from app.infrastructure.persistence.models.transactional import (
        EventoScoreConfigModel,
    )

    try:
        result = await db.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
            ).where(EventoScoreConfigModel.activo.is_(True))
        )
        return {row.tipo_evento: row.peso for row in result.all()}
    except Exception:  # noqa: BLE001 — sin config, fallback por severidad
        return None


async def listar_mis_notas(
    *,
    db: AsyncSession,
    alumno_idnumber: str,
    alumno_email: str,
    moodle_configurado: bool = True,
) -> tuple[list[MiNota], int]:
    """Notas finalizadas del alumno (idnumber/email del JWT) + estado L2.5.

    Deriva de las sesiones FINALIZADAS del alumno con nota persistida
    (moodle_writeback_estado), join con examen_contenido para el titulo. Para cada
    sesion calcula el score de proctoring y lo compara contra umbral_cola_revision
    para marcar ``en_cola_revision`` (score >= umbral). Orden: finalizada_en desc.

    Identidad: un alumno ve SOLO sus filas (match exacto por idnumber O email; los
    valores vacios no matchean para no colisionar entre alumnos sin idnumber)."""
    conds = []
    if alumno_idnumber:
        conds.append(MoodleWritebackEstadoModel.alumno_idnumber == alumno_idnumber)
    if alumno_email:
        conds.append(MoodleWritebackEstadoModel.alumno_email == alumno_email)
    if not conds:
        # Sin identidad utilizable: no se puede aislar al alumno -> sin resultados.
        return [], 0

    stmt = (
        select(
            ProctoringSessionModel.id.label("session_id"),
            ProctoringSessionModel.examen_contenido_id,
            ProctoringSessionModel.finalizada_en,
            ExamenContenidoModel.titulo.label("examen_titulo"),
            ExamenContenidoModel.nota_maxima,
            ExamenContenidoModel.nota_aprobacion,
            MoodleWritebackEstadoModel.nota,
            MoodleWritebackEstadoModel.estado,
        )
        .select_from(ProctoringSessionModel)
        .join(
            MoodleWritebackEstadoModel,
            MoodleWritebackEstadoModel.session_id == ProctoringSessionModel.id,
        )
        .outerjoin(
            ExamenContenidoModel,
            ExamenContenidoModel.id == ProctoringSessionModel.examen_contenido_id,
        )
        .where(
            ProctoringSessionModel.finalizada_en.isnot(None),
            or_(*conds),
        )
        .order_by(
            ProctoringSessionModel.finalizada_en.desc(),
            ProctoringSessionModel.id,
        )
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return [], 0

    session_ids = [r.session_id for r in rows]

    # Eventos de las sesiones del alumno (tipo + severidad para el score, conteo).
    ev_rows = (
        await db.execute(
            select(
                ProctoringEventModel.session_id,
                ProctoringEventModel.tipo,
                ProctoringEventModel.severidad,
            ).where(ProctoringEventModel.session_id.in_(session_ids))
        )
    ).all()
    eventos_por_sesion: dict[str, list] = {}
    for ev in ev_rows:
        eventos_por_sesion.setdefault(ev.session_id, []).append(ev)

    pesos = await _pesos_vivos_por_tipo(db)
    umbral = await _umbral_cola_revision(db)

    items: list[MiNota] = []
    for r in rows:
        evs = eventos_por_sesion.get(r.session_id, [])
        score = calcular_score(evs, pesos_por_tipo=pesos)
        nota = float(r.nota) if r.nota is not None else None
        nota_aprobacion = (
            float(r.nota_aprobacion) if r.nota_aprobacion is not None else None
        )
        aprobado = (
            nota is not None
            and nota_aprobacion is not None
            and nota >= nota_aprobacion
        )
        items.append(
            MiNota(
                examen_id=r.examen_contenido_id or "",
                examen_titulo=r.examen_titulo or "",
                nota=nota,
                nota_maxima=float(r.nota_maxima) if r.nota_maxima is not None else None,
                aprobado=aprobado,
                estado_moodle=estado_moodle_display(
                    r.estado, moodle_configurado=moodle_configurado
                ),
                en_cola_revision=score >= umbral,
                score=float(score),
                umbral_revision=float(umbral),
                eventos=len(evs),
                finalizada_en=r.finalizada_en,
            )
        )
    return items, len(items)
