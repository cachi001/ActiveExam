"""Read-model de resultados de un examen para el admin (C-69 admin-sync, tarea 2).

Deriva de proctoring_session (sesiones FINALIZADAS vinculadas al examen) + el estado
de write-back (moodle_writeback_estado, LEFT JOIN) + la nota calculada/persistida.

L2.5 / D3: NUNCA expone es_correcta ni las respuestas — solo identidad del alumno,
nota académica, estado del envío a Moodle y la marca de actualización.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.scoring import calcular_score
from app.domain.exam_content.visibilidad import nota_visible, revision_visible
from app.domain.review.decision import nota_esta_anulada
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
) -> tuple[int | None, int | None, str | None]:
    """Destino de write-back POR EXAMEN actual (moodle_courseid, moodle_cmid, component).

    D12 (parte B) + C-73. Devuelve (None, None, None) si el examen no existe o no tiene
    destino propio (en cuyo caso el write-back cae al global).
    """
    row = await db.execute(
        select(
            ExamenContenidoModel.moodle_courseid,
            ExamenContenidoModel.moodle_cmid,
            ExamenContenidoModel.moodle_component,
        ).where(ExamenContenidoModel.id == examen_id)
    )
    target = row.one_or_none()
    if target is None:
        return None, None, None
    return target.moodle_courseid, target.moodle_cmid, target.moodle_component


async def listar_estados_sincronizables(
    *, db: AsyncSession, examen_id: str
) -> list[MoodleWritebackEstadoModel]:
    """Filas de write-back en estado 'pendiente'/'fallido' del examen (para sincronizar).

    Las 'enviado' se excluyen (idempotencia: no se re-mandan).

    C-71 slice 2 (D15): además se RETIENEN (hold) las sesiones cuyo estado de
    revisión no habilita el envío — flaggeada/`caso_abierto`/`anulado_por_fraude`.
    El gate se evalúa aquí, ANTES del envío (este es el único punto donde el
    estado pasa a 'enviado', en el sync manual del admin), de modo que una sesión
    problemática nunca alcanza 'enviado'. Release si resuelta limpia
    (`sin_hallazgos`/`aprobado`/`caso_descartado`) o si nunca se flaggeó.

    D12 (parte B): refresca el destino (moodle_courseid/cmid) de cada fila desde el
    valor ACTUAL del examen, para que un admin que fija el target DESPUÉS de finalizar
    sincronice al curso correcto. NULL en el examen → la fila queda NULL y el cliente
    cae al global. El refresco es en memoria sobre la misma sesión (mismo identity map);
    el commit del caller lo persiste.
    """
    stmt = (
        select(
            MoodleWritebackEstadoModel,
            ProctoringSessionModel.id.label("sid"),
            ProctoringSessionModel.decision,
            ProctoringSessionModel.resolucion,
        )
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
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    # Score por sesión (flaggeada = score >= umbral) para el gate D15.
    session_ids = [r.sid for r in rows]
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

    from app.domain.review.decision import (
        DecisionResolucion,
        DecisionRevision,
        writeback_en_hold,
    )

    filas: list[MoodleWritebackEstadoModel] = []
    for r in rows:
        estado = r[0]
        score = calcular_score(eventos_por_sesion.get(r.sid, []), pesos_por_tipo=pesos)
        flaggeada = score >= umbral
        decision = _parse_decision_val(r.decision)
        resolucion = _parse_resolucion_val(r.resolucion)
        if writeback_en_hold(
            flaggeada=flaggeada, decision=decision, resolucion=resolucion
        ):
            continue  # hold: no se envía (D15)
        filas.append(estado)

    courseid, cmid, component = await obtener_target_examen(db=db, examen_id=examen_id)
    for fila in filas:
        fila.moodle_courseid = courseid
        fila.moodle_cmid = cmid
        fila.moodle_component = component

    return filas


def _parse_decision_val(value: str | None):
    """Convierte el string persistido en ``DecisionRevision`` (pendiente si falta)."""
    from app.domain.review.decision import DecisionRevision

    if value is None:
        return DecisionRevision.PENDIENTE
    try:
        return DecisionRevision(value)
    except ValueError:
        try:
            return DecisionRevision.desde_valor_legado(value)
        except ValueError:
            return DecisionRevision.PENDIENTE


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
    # Visibilidad de resultados (C-69). Si nota_visible=False, ``nota`` viene None
    # (no se filtra el número) y la UI muestra "disponible al cerrar (cierre)".
    nota_visible: bool
    revision_disponible: bool
    cierre: object | None  # datetime tz-aware o None
    # Veredicto de resolución (C-71 slice 2, D11b). El alumno lo ve por PULL.
    session_id: str
    nota_anulada: bool  # efecto DERIVADO del último acto (D10b)
    veredicto: str | None  # 'anulado_por_fraude' cuando la nota fue anulada; si no, None
    # Informe de devolución disponible SOLO cuando la nota fue anulada por fraude
    # (D12, minimización Ley 25.326). El resto de los casos: no se expone evidencia.
    informe_disponible: bool


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
            ProctoringSessionModel.resolucion,
            ExamenContenidoModel.titulo.label("examen_titulo"),
            ExamenContenidoModel.nota_maxima,
            ExamenContenidoModel.nota_aprobacion,
            ExamenContenidoModel.cierre,
            ExamenContenidoModel.mostrar_nota,
            ExamenContenidoModel.revision_habilitada,
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
    restituidas = await _sesiones_con_restitucion(db, session_ids)

    ahora = datetime.now(tz=timezone.utc)
    items: list[MiNota] = []
    for r in rows:
        evs = eventos_por_sesion.get(r.session_id, [])
        score = calcular_score(evs, pesos_por_tipo=pesos)
        nota_real = float(r.nota) if r.nota is not None else None
        nota_aprobacion = (
            float(r.nota_aprobacion) if r.nota_aprobacion is not None else None
        )
        # Gate de visibilidad (C-69): si la nota aún no es visible NO se filtra el
        # número al cliente (nota=None); la UI muestra "disponible al cerrar".
        visible = nota_visible(
            mostrar_nota=r.mostrar_nota, cierre=r.cierre, ahora=ahora
        )
        rev_disp = revision_visible(
            revision_habilitada=r.revision_habilitada,
            mostrar_nota=r.mostrar_nota,
            cierre=r.cierre,
            ahora=ahora,
        )
        nota_out = nota_real if visible else None
        aprobado = (
            visible
            and nota_real is not None
            and nota_aprobacion is not None
            and nota_real >= nota_aprobacion
        )
        # Veredicto de resolución (C-71 slice 2): estado efectivo DERIVADO del
        # último acto (D10b). anulada = resolucion 'anulado_por_fraude' Y sin
        # acto compensatorio de restitución posterior (nota_restituida).
        resolucion = _parse_resolucion_val(r.resolucion)
        anulada = nota_esta_anulada(resolucion, r.session_id in restituidas)
        items.append(
            MiNota(
                examen_id=r.examen_contenido_id or "",
                examen_titulo=r.examen_titulo or "",
                nota=nota_out,
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
                nota_visible=visible,
                revision_disponible=rev_disp,
                cierre=r.cierre,
                session_id=r.session_id,
                nota_anulada=anulada,
                veredicto="anulado_por_fraude" if anulada else None,
                informe_disponible=anulada,
            )
        )
    return items, len(items)


def _parse_resolucion_val(value: str | None):
    """Convierte el string persistido en ``DecisionResolucion`` o None."""
    from app.domain.review.decision import DecisionResolucion

    if value is None:
        return None
    try:
        return DecisionResolucion(value)
    except ValueError:
        return None


async def _sesiones_con_restitucion(
    db: AsyncSession, session_ids: list[str]
) -> set[str]:
    """Sesiones con un acto compensatorio `nota_restituida` en el audit log.

    D10b: la reversión de una anulación es un acto append-only en el audit_log
    (`review.decision.nota_restituida`), NUNCA un UPDATE. Degradación graceful:
    si el audit_log no está disponible, se asume que no hubo restituciones."""
    if not session_ids:
        return set()
    from app.infrastructure.persistence.models.audit_log import AuditLogModel

    try:
        rows = await db.execute(
            select(AuditLogModel.evidencia_id).where(
                AuditLogModel.evidencia_id.in_(session_ids),
                AuditLogModel.accion == "review.decision.nota_restituida",
            )
        )
        return {r[0] for r in rows.all()}
    except Exception:  # noqa: BLE001 — degradación: sin audit, no hay restituciones
        return set()
