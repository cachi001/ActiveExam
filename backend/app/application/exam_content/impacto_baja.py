"""c-78 — Qué se lleva puesto una baja: gente rindiendo AHORA y rendiciones ya hechas.

Un solo lugar para las dos preguntas que se hacen antes de dar de baja una
materia, una comisión o un examen:

  - ``sesiones_en_curso`` → **bloquea**. Dar de baja bloquea la rendición
    server-side, así que hacerlo con gente adentro le corta el examen a medio
    camino a alguien que no hizo nada mal.
  - ``rendiciones`` → **solo avisa** (Opción C, decisión del dueño). Un examen ya
    rendido SÍ se puede dar de baja — ese es justamente el caso que motivó la
    baja lógica — pero quien lo hace merece saber cuánta historia hay atrás.

**Qué cuenta como "en curso"**: la sesión sigue abierta (``finalizada_en IS
NULL``) *y* todavía no se le agotó el tiempo. El segundo término no es un
detalle: la auto-finalización es LAZY (se dispara al TOCAR la sesión), así que el
alumno que cerró el navegador y no volvió deja la fila abierta para siempre.
Contar esas sesiones fantasma dejaba la materia sin poder darse de baja nunca.
El vencimiento es el mismo del dominio (``deadline_efectivo``): el mínimo entre
el tiempo límite individual y el cierre de la ventana. Un examen sin cierre ni
tiempo límite no tiene vencimiento, y ahí la sesión sigue contando como en curso
— sin deadline no hay forma de distinguir una sesión viva de una abandonada.

Hora del servidor siempre; el cliente es sensor no confiable (regla dura #6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.enforcement import gracia_seg_default
from app.domain.exam_content.deadline import deadline_efectivo, vencido
from app.infrastructure.persistence.models.exam_content import (
    ComisionModel,
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


@dataclass(frozen=True)
class ImpactoBaja:
    """Lo que alcanza una baja. Conteos sobre el inventario VIGENTE.

    ``comisiones`` y ``examenes`` cuentan solo lo que sigue activo: lo que ya
    estaba dado de baja no se vuelve a anunciar. ``rendiciones``, en cambio,
    cuenta toda la historia — la evidencia no se da de baja.
    """

    sesiones_en_curso: int
    rendiciones: int
    examenes: int
    comisiones: int


async def impacto_baja_examen(
    db: AsyncSession, examen_id: str, *, ahora: datetime | None = None
) -> ImpactoBaja:
    """Impacto de dar de baja UN examen."""
    return await _impacto(db, [examen_id], comisiones=0, ahora=ahora)


async def impacto_baja_comision(
    db: AsyncSession, comision_id: str, *, ahora: datetime | None = None
) -> ImpactoBaja:
    """Impacto de dar de baja una comisión: sus exámenes vigentes."""
    examen_ids = await _examenes_vigentes_de_comisiones(db, [comision_id])
    return await _impacto(db, examen_ids, comisiones=1, ahora=ahora)


async def impacto_baja_materia(
    db: AsyncSession, materia_id: str, *, ahora: datetime | None = None
) -> ImpactoBaja:
    """Impacto de dar de baja una materia: sus comisiones y exámenes vigentes."""
    comision_ids = list(
        (
            await db.execute(
                select(ComisionModel.id).where(
                    ComisionModel.materia_id == materia_id,
                    ComisionModel.activa.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    examen_ids = await _examenes_vigentes_de_comisiones(db, comision_ids)
    return await _impacto(db, examen_ids, comisiones=len(comision_ids), ahora=ahora)


async def _examenes_vigentes_de_comisiones(
    db: AsyncSession, comision_ids: list[str]
) -> list[str]:
    if not comision_ids:
        return []
    filas = await db.execute(
        select(ExamenContenidoModel.id).where(
            ExamenContenidoModel.comision_id.in_(comision_ids),
            ExamenContenidoModel.eliminado_en.is_(None),
        )
    )
    return list(filas.scalars().all())


async def _impacto(
    db: AsyncSession,
    examen_ids: list[str],
    *,
    comisiones: int,
    ahora: datetime | None,
) -> ImpactoBaja:
    if not examen_ids:
        return ImpactoBaja(
            sesiones_en_curso=0, rendiciones=0, examenes=0, comisiones=comisiones
        )

    rendiciones = (
        await db.execute(
            select(func.count())
            .select_from(ProctoringSessionModel)
            .where(
                ProctoringSessionModel.examen_contenido_id.in_(examen_ids),
                ProctoringSessionModel.finalizada_en.is_not(None),
            )
        )
    ).scalar_one()

    return ImpactoBaja(
        sesiones_en_curso=await _contar_en_curso(db, examen_ids, ahora=ahora),
        rendiciones=int(rendiciones or 0),
        examenes=len(examen_ids),
        comisiones=comisiones,
    )


async def _contar_en_curso(
    db: AsyncSession, examen_ids: list[str], *, ahora: datetime | None
) -> int:
    """Sesiones abiertas a las que todavía NO se les agotó el tiempo.

    Las abiertas son pocas por definición (a lo sumo la gente que está rindiendo),
    así que se traen y se filtran con la función de dominio en vez de reimplementar
    el cálculo del deadline en SQL.
    """
    if not examen_ids:
        return 0

    abiertas = (
        await db.execute(
            select(
                ProctoringSessionModel.creada_en,
                ExamenContenidoModel.tiempo_limite_min,
                ExamenContenidoModel.cierre,
            )
            .join(
                ExamenContenidoModel,
                ExamenContenidoModel.id == ProctoringSessionModel.examen_contenido_id,
            )
            .where(
                ProctoringSessionModel.examen_contenido_id.in_(examen_ids),
                ProctoringSessionModel.finalizada_en.is_(None),
            )
        )
    ).all()

    ahora = ahora or datetime.now(UTC)
    gracia_seg = gracia_seg_default()
    return sum(
        1
        for creada_en, tiempo_limite_min, cierre in abiertas
        if _sigue_viva(
            creada_en=creada_en,
            tiempo_limite_min=tiempo_limite_min,
            cierre=cierre,
            ahora=ahora,
            gracia_seg=gracia_seg,
        )
    )


def _sigue_viva(
    *,
    creada_en: datetime,
    tiempo_limite_min: int | None,
    cierre: datetime | None,
    ahora: datetime,
    gracia_seg: int,
) -> bool:
    if tiempo_limite_min is None and cierre is None:
        # Sin vencimiento no hay forma de saber que murió: se la trata como viva.
        return True
    if cierre is None:
        deadline = _aware(creada_en) + _minutos(tiempo_limite_min)
    else:
        deadline = deadline_efectivo(
            creada_en=_aware(creada_en),
            tiempo_limite_min=tiempo_limite_min,
            cierre=_aware(cierre),
        )
    return not vencido(deadline=deadline, ahora=ahora, gracia_seg=gracia_seg)


def _minutos(minutos: int | None):
    from datetime import timedelta

    return timedelta(minutes=minutos or 0)


def _aware(valor: datetime) -> datetime:
    """Postgres puede devolver naive según la columna; se asume UTC del servidor."""
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)
