"""Servicio de estadísticas institucionales (C-20 re-alcanzado, standalone).

Computa MÉTRICAS AGREGADAS sobre datos que YA existen — sin depender de C-13
(continuous aggregates) ni C-16 (decisiones humanas):
- conteos: exámenes, materias, comisiones, sesiones (totales / finalizadas).
- personas en riesgo: sesiones con score >= umbral_cola_revision.
- distribución de scores por buckets.

L2.5 (RN-SC-01, DD-01): el "riesgo" es una SEÑAL DE PRIORIZACIÓN para la revisión
humana, NUNCA un veredicto ni una acusación. Este servicio SOLO lee y agrega.

Reusa las fuentes canónicas del umbral y los pesos vivos (misma verdad que la Cola
de Revisión y el detalle de sesión del proctor).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.moodle.resultados_query import (
    _pesos_vivos_por_tipo,
    _umbral_cola_revision,
)
from app.application.proctoring.scoring import calcular_score
from app.infrastructure.persistence.models.exam_content import (
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)


@dataclass(frozen=True, slots=True)
class ResumenStats:
    """Sumario institucional agregado (sin PII)."""

    total_examenes: int
    total_materias: int
    total_comisiones: int
    total_sesiones: int
    sesiones_finalizadas: int
    sesiones_en_riesgo: int
    umbral_riesgo: int
    distribucion_scores: dict[str, int]


async def _count(db: AsyncSession, model) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def obtener_resumen(db: AsyncSession) -> ResumenStats:
    """Agrega las métricas institucionales. Solo lee; no muta nada (invariante)."""
    total_examenes = await _count(db, ExamenContenidoModel)
    total_materias = await _count(db, MateriaModel)
    total_comisiones = await _count(db, ComisionModel)
    total_sesiones = await _count(db, ProctoringSessionModel)
    sesiones_finalizadas = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ProctoringSessionModel)
                .where(ProctoringSessionModel.finalizada_en.is_not(None))
            )
        ).scalar_one()
    )

    umbral = await _umbral_cola_revision(db)
    pesos = await _pesos_vivos_por_tipo(db)

    # Eventos agrupados por sesión (una pasada) para computar el score server-side,
    # con la MISMA función que la Cola de Revisión (calcular_score + pesos vivos).
    ev_rows = (
        await db.execute(
            select(
                ProctoringEventModel.session_id,
                ProctoringEventModel.tipo,
                ProctoringEventModel.severidad,
            )
        )
    ).all()
    eventos_por_sesion: dict[str, list] = {}
    for r in ev_rows:
        eventos_por_sesion.setdefault(r.session_id, []).append(r)

    # Buckets fijos 0-100 (el score está capeado a 100). El bucket "en riesgo" se
    # deriva del umbral (default 70), no se hardcodea.
    dist = {"0-24": 0, "25-49": 0, "50-69": 0, "70-100": 0}
    en_riesgo = 0
    sid_rows = (await db.execute(select(ProctoringSessionModel.id))).all()
    for (sid,) in sid_rows:
        score = calcular_score(eventos_por_sesion.get(sid, []), pesos_por_tipo=pesos)
        if score >= umbral:
            en_riesgo += 1
        if score < 25:
            dist["0-24"] += 1
        elif score < 50:
            dist["25-49"] += 1
        elif score < 70:
            dist["50-69"] += 1
        else:
            dist["70-100"] += 1

    return ResumenStats(
        total_examenes=total_examenes,
        total_materias=total_materias,
        total_comisiones=total_comisiones,
        total_sesiones=total_sesiones,
        sesiones_finalizadas=sesiones_finalizadas,
        sesiones_en_riesgo=en_riesgo,
        umbral_riesgo=umbral,
        distribucion_scores=dist,
    )
