"""Servicio de estadísticas institucionales (C-20 re-alcanzado, standalone).

Computa MÉTRICAS AGREGADAS sobre datos que YA existen — sin depender de C-13
(continuous aggregates) ni C-16 (decisiones humanas):
- conteos: exámenes, materias, comisiones, sesiones (totales / finalizadas).
- personas en riesgo: sesiones con score >= umbral_cola_revision.
- distribución de scores por buckets.
- desgloses: por materia, top de tipos de evento, por día, por decisión de revisión.

Soporta FILTROS (materia / comisión / examen / rango de fechas) sobre las métricas
derivadas de sesiones. Los conteos de catálogo (materias/comisiones/exámenes) son
contexto global y NO se filtran.

L2.5 (RN-SC-01, DD-01): el "riesgo" es una SEÑAL DE PRIORIZACIÓN para la revisión
humana, NUNCA un veredicto ni una acusación. Este servicio SOLO lee y agrega.

Reusa las fuentes canónicas del umbral y los pesos vivos (misma verdad que la Cola
de Revisión y el detalle de sesión del proctor).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import false, func, select
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
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)

# Cuántos tipos de evento devolver en el "top" (los detectores que más disparan).
TOP_EVENTOS_N = 8


@dataclass(frozen=True, slots=True)
class FiltrosStats:
    """Filtros opcionales de la vista de estadísticas. None = sin filtrar."""

    materia_id: str | None = None
    comision_id: str | None = None
    examen_contenido_id: str | None = None
    desde: str | None = None  # ISO 8601 (aplica a creada_en >=)
    hasta: str | None = None  # ISO 8601 (aplica a creada_en <=)


@dataclass(frozen=True, slots=True)
class MateriaStat:
    """Sesiones (y cuántas en riesgo) de una materia."""

    materia_id: str
    nombre: str
    sesiones: int
    en_riesgo: int


@dataclass(frozen=True, slots=True)
class EventoStat:
    """Cantidad de veces que disparó un tipo de evento (detector)."""

    tipo: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class DiaStat:
    """Sesiones creadas en un día (YYYY-MM-DD)."""

    fecha: str
    sesiones: int


@dataclass(frozen=True, slots=True)
class ComisionCatalogo:
    """Una comisión del catálogo con su volumen real (inscriptos y exámenes)."""

    id: str
    codigo: str
    nombre: str
    activa: bool
    periodo: str | None
    anio: int | None
    inscriptos: int
    examenes: int


@dataclass(frozen=True, slots=True)
class MateriaCatalogo:
    """Una materia del catálogo con TODAS sus comisiones.

    A diferencia de ``MateriaStat`` (que se agrega desde las SESIONES y por lo tanto
    omite lo que todavía no se rindió), esto es el INVENTARIO: qué hay dado de alta
    hoy, se haya usado o no. Una materia recién creada aparece acá con 0 sesiones.
    """

    id: str
    codigo: str
    nombre: str
    activa: bool
    comisiones: list[ComisionCatalogo] = field(default_factory=list)


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
    por_materia: list[MateriaStat] = field(default_factory=list)
    top_eventos: list[EventoStat] = field(default_factory=list)
    por_dia: list[DiaStat] = field(default_factory=list)
    decisiones: dict[str, int] = field(default_factory=dict)
    catalogo: list[MateriaCatalogo] = field(default_factory=list)


async def _catalogo_materias(db: AsyncSession) -> list[MateriaCatalogo]:
    """Inventario del catálogo: materias con sus comisiones, inscriptos y exámenes.

    Es una foto de lo DADO DE ALTA, no de lo rendido: responde "qué materias y
    comisiones existen hoy" — que es justamente lo que el desglose por sesiones no
    puede mostrar (una comisión sin nadie que haya rendido no aparece ahí).

    Dos queries agregadas (no N+1): una cuenta inscriptos por comisión y otra
    exámenes por comisión; después se arma el árbol en memoria. El catálogo es de
    cientos de filas, no de millones.
    """
    inscriptos_por_comision = {
        cid: total
        for cid, total in (
            await db.execute(
                select(InscripcionModel.comision_id, func.count())
                .group_by(InscripcionModel.comision_id)
            )
        ).all()
    }
    examenes_por_comision = {
        cid: total
        for cid, total in (
            await db.execute(
                select(ExamenContenidoModel.comision_id, func.count())
                .where(ExamenContenidoModel.comision_id.is_not(None))
                .group_by(ExamenContenidoModel.comision_id)
            )
        ).all()
    }

    filas = (
        await db.execute(
            select(MateriaModel, ComisionModel)
            .outerjoin(ComisionModel, ComisionModel.materia_id == MateriaModel.id)
            .order_by(MateriaModel.nombre, ComisionModel.codigo)
        )
    ).all()

    materias: dict[str, dict] = {}
    for materia, comision in filas:
        entrada = materias.setdefault(
            materia.id,
            {
                "id": materia.id,
                "codigo": materia.codigo,
                "nombre": materia.nombre,
                "activa": bool(materia.activa),
                "comisiones": [],
            },
        )
        # outerjoin: una materia SIN comisiones trae la fila con comision=None.
        if comision is None:
            continue
        entrada["comisiones"].append(
            ComisionCatalogo(
                id=comision.id,
                codigo=comision.codigo,
                nombre=comision.nombre,
                activa=bool(getattr(comision, "activa", True)),
                periodo=comision.periodo,
                anio=comision.anio,
                inscriptos=int(inscriptos_por_comision.get(comision.id, 0)),
                examenes=int(examenes_por_comision.get(comision.id, 0)),
            )
        )

    return [MateriaCatalogo(**datos) for datos in materias.values()]


async def _count(db: AsyncSession, model) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def _contar_catalogo(
    db: AsyncSession, filtros: FiltrosStats
) -> tuple[int, int, int]:
    """``(examenes, materias, comisiones)`` DENTRO del alcance de los filtros.

    Antes eran conteos globales: al filtrar por una materia, las tarjetas seguían
    mostrando el inventario entero. Se notaba con un id inexistente — "0 sesiones"
    junto a "1 materia, 1 examen" — pero el problema real aparece con varias
    materias cargadas: el tablero dice "12 exámenes" mientras el resto de la
    pantalla habla de una sola materia. Un número que no responde al filtro que la
    persona acaba de aplicar es un número en el que no se puede confiar.

    Sin filtros de catálogo (solo fechas, o ninguno) devuelve los totales globales:
    las fechas acotan la ACTIVIDAD, no el inventario — un examen existe se haya
    rendido o no en ese rango.
    """
    examenes_stmt = select(func.count()).select_from(ExamenContenidoModel)
    materias_stmt = select(func.count()).select_from(MateriaModel)
    comisiones_stmt = select(func.count()).select_from(ComisionModel)

    if filtros.examen_contenido_id:
        # El examen manda: define su comisión y, a través de ella, su materia.
        examenes_stmt = examenes_stmt.where(
            ExamenContenidoModel.id == filtros.examen_contenido_id
        )
        comisiones_stmt = comisiones_stmt.where(
            ComisionModel.id.in_(
                select(ExamenContenidoModel.comision_id).where(
                    ExamenContenidoModel.id == filtros.examen_contenido_id
                )
            )
        )
        materias_stmt = materias_stmt.where(
            MateriaModel.id.in_(
                select(ComisionModel.materia_id).join(
                    ExamenContenidoModel,
                    ExamenContenidoModel.comision_id == ComisionModel.id,
                ).where(ExamenContenidoModel.id == filtros.examen_contenido_id)
            )
        )
    elif filtros.comision_id:
        examenes_stmt = examenes_stmt.where(
            ExamenContenidoModel.comision_id == filtros.comision_id
        )
        comisiones_stmt = comisiones_stmt.where(
            ComisionModel.id == filtros.comision_id
        )
        materias_stmt = materias_stmt.where(
            MateriaModel.id.in_(
                select(ComisionModel.materia_id).where(
                    ComisionModel.id == filtros.comision_id
                )
            )
        )
    elif filtros.materia_id:
        comisiones_de_materia = select(ComisionModel.id).where(
            ComisionModel.materia_id == filtros.materia_id
        )
        examenes_stmt = examenes_stmt.where(
            ExamenContenidoModel.comision_id.in_(comisiones_de_materia)
        )
        comisiones_stmt = comisiones_stmt.where(
            ComisionModel.materia_id == filtros.materia_id
        )
        materias_stmt = materias_stmt.where(MateriaModel.id == filtros.materia_id)

    return (
        int((await db.execute(examenes_stmt)).scalar_one()),
        int((await db.execute(materias_stmt)).scalar_one()),
        int((await db.execute(comisiones_stmt)).scalar_one()),
    )


def _parse_dt(valor: str) -> datetime | None:
    """ISO 8601 → datetime. Tolerante: valor inválido → None (se ignora el filtro)."""
    try:
        return datetime.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


def _es_uuid(valor: str) -> bool:
    """True si `valor` es un UUID válido. Las columnas de id son UUID: un valor
    malformado rompería el cast en la DB (500), así que se valida antes."""
    try:
        UUID(valor)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _session_conditions(filtros: FiltrosStats) -> list:
    """Condiciones WHERE sobre ProctoringSessionModel derivadas de los filtros.

    Para materia/comisión resuelve el vínculo sesión → examen_contenido →
    comisión → materia con subconsultas de `examen_contenido_id IN (...)`. Un id
    malformado (no-UUID) NO rompe: filtra a vacío (nada matchea), no un 500.
    """
    conds: list = []
    if filtros.examen_contenido_id:
        if _es_uuid(filtros.examen_contenido_id):
            conds.append(ProctoringSessionModel.examen_contenido_id == filtros.examen_contenido_id)
        else:
            conds.append(false())
    if filtros.comision_id:
        if _es_uuid(filtros.comision_id):
            conds.append(
                ProctoringSessionModel.examen_contenido_id.in_(
                    select(ExamenContenidoModel.id).where(
                        ExamenContenidoModel.comision_id == filtros.comision_id
                    )
                )
            )
        else:
            conds.append(false())
    if filtros.materia_id:
        if _es_uuid(filtros.materia_id):
            conds.append(
                ProctoringSessionModel.examen_contenido_id.in_(
                    select(ExamenContenidoModel.id).where(
                        ExamenContenidoModel.comision_id.in_(
                            select(ComisionModel.id).where(
                                ComisionModel.materia_id == filtros.materia_id
                            )
                        )
                    )
                )
            )
        else:
            conds.append(false())
    desde = _parse_dt(filtros.desde) if filtros.desde else None
    hasta = _parse_dt(filtros.hasta) if filtros.hasta else None
    if desde is not None:
        conds.append(ProctoringSessionModel.creada_en >= desde)
    if hasta is not None:
        conds.append(ProctoringSessionModel.creada_en <= hasta)
    return conds


def _bucket(score: int) -> str:
    if score < 25:
        return "0-24"
    if score < 50:
        return "25-49"
    if score < 70:
        return "50-69"
    return "70-100"


async def obtener_resumen(
    db: AsyncSession, filtros: FiltrosStats | None = None
) -> ResumenStats:
    """Agrega las métricas institucionales. Solo lee; no muta nada (invariante)."""
    filtros = filtros or FiltrosStats()
    conds = _session_conditions(filtros)

    # Catálogo ACOTADO al filtro: las tarjetas tienen que hablar del mismo recorte
    # que el resto de la pantalla (ver _contar_catalogo).
    total_examenes, total_materias, total_comisiones = await _contar_catalogo(
        db, filtros
    )

    umbral = await _umbral_cola_revision(db)
    pesos = await _pesos_vivos_por_tipo(db)

    # Sesiones que pasan el filtro, con las columnas que alimentan los desgloses.
    ses_rows = (
        await db.execute(
            select(
                ProctoringSessionModel.id,
                ProctoringSessionModel.examen_contenido_id,
                ProctoringSessionModel.creada_en,
                ProctoringSessionModel.finalizada_en,
                ProctoringSessionModel.decision,
            ).where(*conds)
        )
    ).all()
    total_sesiones = len(ses_rows)
    sesiones_finalizadas = sum(1 for r in ses_rows if r.finalizada_en is not None)
    sid_list = [r.id for r in ses_rows]

    # Eventos de las sesiones filtradas (una pasada): score por sesión + top de tipos.
    eventos_por_sesion: dict[str, list] = {}
    tipo_counts: dict[str, int] = {}
    if sid_list:
        ev_rows = (
            await db.execute(
                select(
                    ProctoringEventModel.session_id,
                    ProctoringEventModel.tipo,
                    ProctoringEventModel.severidad,
                ).where(ProctoringEventModel.session_id.in_(sid_list))
            )
        ).all()
        for r in ev_rows:
            eventos_por_sesion.setdefault(r.session_id, []).append(r)
            tipo_counts[r.tipo] = tipo_counts.get(r.tipo, 0) + 1

    # Score por sesión con la MISMA función que la Cola de Revisión.
    dist = {"0-24": 0, "25-49": 0, "50-69": 0, "70-100": 0}
    en_riesgo = 0
    score_por_sesion: dict[str, int] = {}
    for r in ses_rows:
        score = calcular_score(eventos_por_sesion.get(r.id, []), pesos_por_tipo=pesos)
        score_por_sesion[r.id] = score
        if score >= umbral:
            en_riesgo += 1
        dist[_bucket(score)] += 1

    # Mapa examen_contenido_id → (materia_id, nombre) para el desglose por materia.
    ec_ids = {r.examen_contenido_id for r in ses_rows if r.examen_contenido_id}
    ec_a_materia: dict[str, tuple[str, str]] = {}
    if ec_ids:
        mrows = (
            await db.execute(
                select(
                    ExamenContenidoModel.id,
                    MateriaModel.id,
                    MateriaModel.nombre,
                )
                .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .join(MateriaModel, ComisionModel.materia_id == MateriaModel.id)
                .where(ExamenContenidoModel.id.in_(ec_ids))
            )
        ).all()
        for ec_id, mid, nombre in mrows:
            ec_a_materia[ec_id] = (mid, nombre)

    # Agregados en Python sobre las filas ya cargadas (sin más viajes a la DB).
    materia_agg: dict[str, list] = {}  # mid → [nombre, sesiones, en_riesgo]
    dia_agg: dict[str, int] = {}
    dec_agg: dict[str, int] = {}
    for r in ses_rows:
        # por materia (solo sesiones con vínculo a examen → comisión → materia)
        mm = ec_a_materia.get(r.examen_contenido_id)
        if mm is not None:
            mid, nombre = mm
            agg = materia_agg.setdefault(mid, [nombre, 0, 0])
            agg[1] += 1
            if score_por_sesion[r.id] >= umbral:
                agg[2] += 1
        # por día
        if r.creada_en is not None:
            fecha = (
                r.creada_en.date().isoformat()
                if hasattr(r.creada_en, "date")
                else str(r.creada_en)[:10]
            )
            dia_agg[fecha] = dia_agg.get(fecha, 0) + 1
        # por decisión de revisión (None = todavía sin revisar)
        clave = r.decision or "sin_revisar"
        dec_agg[clave] = dec_agg.get(clave, 0) + 1

    por_materia = [
        MateriaStat(materia_id=mid, nombre=v[0], sesiones=v[1], en_riesgo=v[2])
        for mid, v in materia_agg.items()
    ]
    por_materia.sort(key=lambda m: (-m.sesiones, m.nombre))

    top_eventos = [
        EventoStat(tipo=t, cantidad=c)
        for t, c in sorted(tipo_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_EVENTOS_N]
    ]

    por_dia = [DiaStat(fecha=f, sesiones=n) for f, n in sorted(dia_agg.items())]

    return ResumenStats(
        total_examenes=total_examenes,
        total_materias=total_materias,
        total_comisiones=total_comisiones,
        total_sesiones=total_sesiones,
        sesiones_finalizadas=sesiones_finalizadas,
        sesiones_en_riesgo=en_riesgo,
        umbral_riesgo=umbral,
        distribucion_scores=dist,
        por_materia=por_materia,
        top_eventos=top_eventos,
        por_dia=por_dia,
        decisiones=dec_agg,
        catalogo=await _catalogo_materias(db),
    )
