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
    _tipos_desactivados,
    _umbral_cola_revision,
)
from app.application.proctoring.scoring import SCORE_UMBRAL_MEDIO, calcular_score
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
from app.infrastructure.persistence.models.transactional import (
    ConsentimientoPerfilModel,
    EmbeddingReferenciaModel,
)
from app.domain.events.schema import TipoEvento

# Cuántos tipos de evento devolver en el "top" (los detectores que más disparan).
#
# Se deriva del enum y no se fija a mano: estaba en 8 con 17 tipos, y cuando
# varios empatan en cantidad el desempate es alfabético, así que quedaban afuera
# `tampering_camara_virtual` y `posible_cambio_identidad` — los dos más graves.
# Un panel que existe para verificar que los detectores registran no puede
# esconder justo los que más importan. Derivarlo evita que vuelva a quedar corto
# cuando se agregue un tipo nuevo.
TOP_EVENTOS_N = len(TipoEvento)


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
class ComisionStat:
    """Sesiones (y cuántas en riesgo) de una comisión."""

    comision_id: str
    nombre: str
    sesiones: int
    en_riesgo: int


@dataclass(frozen=True, slots=True)
class ElegibilidadStats:
    """Estado de habilitación del padrón de inscriptos para PODER RENDIR.

    Un alumno solo puede rendir si tiene consentimiento vigente (otorgado) Y
    biometría de referencia vigente. Sin alguno, queda BLOQUEADO. Es la señal
    operativa más importante antes de un examen: cuántos NO van a poder rendir y
    por qué (falta consentimiento, falta biometría, o ambas)."""

    total_inscriptos: int = 0
    #: Totales NO excluyentes: cuántos hay que perseguir para que firmen o para
    #: que capturen. Quien no tiene ninguna de las dos cuenta en los dos.
    con_consentimiento: int = 0
    sin_consentimiento: int = 0
    con_biometria: int = 0
    sin_biometria: int = 0
    pueden_rendir: int = 0
    no_pueden_rendir: int = 0
    #: Motivos EXCLUYENTES: suman exactamente `no_pueden_rendir`. Sin ellos, la
    #: pantalla mostraba dos barras que sumaban más que el total de bloqueados, y
    #: los números no coincidían con los del export (que ya cuenta excluyente).
    #: Los dos criterios conviven a propósito: uno responde "a cuántos les falta
    #: X", el otro "qué le falta a cada uno".
    solo_falta_consentimiento: int = 0
    solo_falta_biometria: int = 0
    faltan_ambas: int = 0


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
    por_comision: list[ComisionStat] = field(default_factory=list)
    top_eventos: list[EventoStat] = field(default_factory=list)
    por_dia: list[DiaStat] = field(default_factory=list)
    decisiones: dict[str, int] = field(default_factory=dict)
    elegibilidad: "ElegibilidadStats" = field(default_factory=lambda: ElegibilidadStats())


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

    Baja lógica (c-78 D2): los exámenes dados de baja NO cuentan acá — esto es
    inventario VIGENTE. La exclusión es exclusiva de este conteo: ``_session_conditions``
    y toda la actividad (sesiones, scores, distribución) siguen contando las
    sesiones de un examen dado de baja, porque esa actividad ocurrió y es un
    hecho histórico. O sea: al dar de baja un examen cae ``total_examenes`` y
    NO cae ``total_sesiones``.
    """
    examenes_stmt = (
        select(func.count())
        .select_from(ExamenContenidoModel)
        .where(ExamenContenidoModel.eliminado_en.is_(None))
    )
    materias_stmt = select(func.count()).select_from(MateriaModel)
    comisiones_stmt = select(func.count()).select_from(ComisionModel)

    # Las columnas de id son UUID: un valor malformado revienta el cast en la DB
    # (DataError → 500). ``_session_conditions`` ya lo filtraba a vacío, pero acá
    # no, así que un id basura en la query string tiraba la pantalla entera en vez
    # de devolver un resumen vacío. Un filtro invalido no matchea nada: 0.
    if not all(
        _es_uuid(v)
        for v in (filtros.examen_contenido_id, filtros.comision_id, filtros.materia_id)
        if v
    ):
        return (0, 0, 0)

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


async def describir_alcance(db: AsyncSession, filtros: FiltrosStats | None) -> str:
    """Texto legible del recorte aplicado, para la cabecera de los exports.

    Resuelve los NOMBRES contra la base a partir de los ids del filtro. Antes los
    exports derivaban la materia de ``por_materia[0]`` (la materia con más
    sesiones, no la filtrada — y "materia filtrada" cuando no había sesiones) y ni
    siquiera mencionaban los filtros de comisión y examen: un informe descargado
    con un recorte aplicado no decía de qué recorte hablaba.
    """
    if filtros is None:
        return "Todo el período (sin filtros)"
    partes: list[str] = []

    if filtros.materia_id and _es_uuid(filtros.materia_id):
        nombre = (
            await db.execute(
                select(MateriaModel.nombre).where(MateriaModel.id == filtros.materia_id)
            )
        ).scalar_one_or_none()
        partes.append(f"Materia: {nombre or 'no encontrada'}")
    if filtros.comision_id and _es_uuid(filtros.comision_id):
        nombre = (
            await db.execute(
                select(ComisionModel.nombre).where(
                    ComisionModel.id == filtros.comision_id
                )
            )
        ).scalar_one_or_none()
        partes.append(f"Comisión: {nombre or 'no encontrada'}")
    if filtros.examen_contenido_id and _es_uuid(filtros.examen_contenido_id):
        titulo = (
            await db.execute(
                select(ExamenContenidoModel.titulo).where(
                    ExamenContenidoModel.id == filtros.examen_contenido_id
                )
            )
        ).scalar_one_or_none()
        partes.append(f"Examen: {titulo or 'no encontrado'}")
    if filtros.desde:
        partes.append(f"desde {filtros.desde[:10]}")
    if filtros.hasta:
        partes.append(f"hasta {filtros.hasta[:10]}")

    return " · ".join(partes) if partes else "Todo el período (sin filtros)"


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

    SIEMPRE excluye sesiones de diagnóstico (sin examen vinculado, ej. "Grabar
    sesión" del Test de detección de Configuración): no son un examen rendido,
    contarlas infla "Sesiones iniciadas"/distribución de scores con actividad
    que no tiene nada que ver con exámenes reales. Mismo criterio que ya aplica
    la Cola de Revisión (`enriquecerYFiltrar`, frontend).

    SIEMPRE excluye también los ENSAYOS del docente (``es_prueba``), por la misma
    razón: probar el examen antes de soltarlo no es actividad académica, y cada
    ensayo sumaba a "Sesiones iniciadas" y a la distribución de riesgo
    institucional. Ya se excluían de resultados y del write-back a Moodle; acá
    faltaba.
    """
    conds: list = [
        ProctoringSessionModel.examen_contenido_id.is_not(None),
        ProctoringSessionModel.es_prueba.is_(False),
    ]
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


def _inscriptos_conditions(filtros: FiltrosStats) -> list:
    """WHERE sobre InscripcionModel según materia/comisión/examen.

    El rango de fechas NO aplica: la elegibilidad es un SNAPSHOT del padrón
    (quién está inscripto hoy y si puede rendir), no una serie temporal.
    """
    conds: list = []
    if filtros.examen_contenido_id:
        if _es_uuid(filtros.examen_contenido_id):
            conds.append(
                InscripcionModel.comision_id.in_(
                    select(ExamenContenidoModel.comision_id).where(
                        ExamenContenidoModel.id == filtros.examen_contenido_id
                    )
                )
            )
        else:
            conds.append(false())
    if filtros.comision_id:
        if _es_uuid(filtros.comision_id):
            conds.append(InscripcionModel.comision_id == filtros.comision_id)
        else:
            conds.append(false())
    if filtros.materia_id:
        if _es_uuid(filtros.materia_id):
            conds.append(
                InscripcionModel.comision_id.in_(
                    select(ComisionModel.id).where(
                        ComisionModel.materia_id == filtros.materia_id
                    )
                )
            )
        else:
            conds.append(false())
    return conds


async def _elegibilidad(db: AsyncSession, filtros: FiltrosStats) -> ElegibilidadStats:
    """Cuántos inscriptos pueden / NO pueden rendir (falta consentimiento y/o biometría).

    Mismo criterio que ``listar_alumnos_con_elegibilidad`` (consentimiento vigente
    'otorgado' + embedding de referencia vigente), pero AGREGADO por conjuntos para
    no hacer N+1: 3 queries (padrón, biometría vigente, último consentimiento por
    usuario) e intersección en Python.
    """
    conds = _inscriptos_conditions(filtros)
    usuario_ids = list(
        (
            await db.execute(
                select(InscripcionModel.usuario_id).where(*conds).distinct()
            )
        )
        .scalars()
        .all()
    )
    total = len(usuario_ids)
    if total == 0:
        return ElegibilidadStats()

    # Biometría: usuarios con embedding de referencia vigente.
    bio_set = set(
        (
            await db.execute(
                select(EmbeddingReferenciaModel.usuario_id)
                .where(
                    EmbeddingReferenciaModel.vigente.is_(True),
                    EmbeddingReferenciaModel.usuario_id.in_(usuario_ids),
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )

    # Consentimiento: última fila por usuario (append-only) → estado 'otorgado'.
    consent_rows = (
        await db.execute(
            select(
                ConsentimientoPerfilModel.usuario_id, ConsentimientoPerfilModel.estado
            )
            .where(ConsentimientoPerfilModel.usuario_id.in_(usuario_ids))
            .distinct(ConsentimientoPerfilModel.usuario_id)
            .order_by(
                ConsentimientoPerfilModel.usuario_id,
                ConsentimientoPerfilModel.timestamp.desc(),
                ConsentimientoPerfilModel.id.desc(),
            )
        )
    ).all()
    consent_ok = {uid for uid, estado in consent_rows if estado == "otorgado"}

    pueden = len(bio_set & consent_ok)
    # Motivos EXCLUYENTES sobre el conjunto de inscriptos: cada bloqueado cuenta
    # en uno solo, así los tres suman `no_pueden_rendir` y cruzan con el export.
    inscriptos = set(usuario_ids)
    faltan_ambas = len(inscriptos - bio_set - consent_ok)
    solo_falta_consentimiento = len((inscriptos & bio_set) - consent_ok)
    solo_falta_biometria = len((inscriptos & consent_ok) - bio_set)
    return ElegibilidadStats(
        total_inscriptos=total,
        con_consentimiento=len(consent_ok),
        sin_consentimiento=total - len(consent_ok),
        con_biometria=len(bio_set),
        sin_biometria=total - len(bio_set),
        pueden_rendir=pueden,
        no_pueden_rendir=total - pueden,
        solo_falta_consentimiento=solo_falta_consentimiento,
        solo_falta_biometria=solo_falta_biometria,
        faltan_ambas=faltan_ambas,
    )


# Corte de las bandas bajas: el MISMO que usa el filtro "nivel de riesgo" del
# Registro de sesiones (`nivel_riesgo()` → bajo/medio/alto). Antes acá había
# cortes propios (25 y 50) y el filtro usaba 30: una sesión con score 28 salía
# "bajo" en el filtro y caía en la banda "25-49" de la rosca. Dos criterios para
# lo mismo, y ninguno de los dos lo eligió nadie.
#
# El corte ALTO no es fijo: es el umbral vivo de la cola de revisión.
_CORTES_BAJOS = (SCORE_UMBRAL_MEDIO,)


def bandas_de_score(umbral: int) -> list[str]:
    """Etiquetas de las bandas de score, con la ÚLTIMA arrancando en ``umbral``.

    El umbral de cola de revisión es configurable (piso de producto 70, hasta 90).
    Con bandas fijas ``70-100``, un umbral de 80 dejaba la banda "de riesgo"
    mezclando sesiones en riesgo (85) y fuera de riesgo (75), y la UI —que marca
    la banda con ``límite_inferior >= umbral``— no marcaba NINGUNA. Haciendo que
    la última banda arranque exactamente en el umbral, "última banda" y "prioriza
    revisión humana" pasan a ser lo mismo por construcción.

    Los cortes bajos (25, 50) se conservan mientras queden por debajo del umbral,
    así el default 70 sigue dando las bandas de siempre y no hay churn visual.
    """
    cortes = [c for c in _CORTES_BAJOS if c < umbral] + [umbral]
    etiquetas: list[str] = []
    lo = 0
    for corte in cortes:
        etiquetas.append(f"{lo}-{corte - 1}")
        lo = corte
    etiquetas.append(f"{lo}-100")
    return etiquetas


def banda_de_score(score: int, bandas: list[str]) -> str:
    """Etiqueta de la banda donde cae ``score`` (bordes inclusivos)."""
    for etiqueta in bandas:
        hi = int(etiqueta.split("-")[1])
        if score <= hi:
            return etiqueta
    return bandas[-1]


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
    # Tipos APAGADOS por el admin: pesan 0 (no caen al fallback por severidad).
    desactivados = await _tipos_desactivados(db)

    # Elegibilidad del padrón (snapshot): quién puede / NO puede rendir.
    elegibilidad = await _elegibilidad(db, filtros)

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

    # Score por sesión con la MISMA función que la Cola de Revisión. Las bandas se
    # derivan del umbral VIVO: la última arranca en él, así la banda de riesgo del
    # gráfico y el conteo "en riesgo" no pueden desalinearse.
    bandas = bandas_de_score(umbral)
    dist = {etiqueta: 0 for etiqueta in bandas}
    en_riesgo = 0
    score_por_sesion: dict[str, int] = {}
    for r in ses_rows:
        score = calcular_score(
            eventos_por_sesion.get(r.id, []),
            pesos_por_tipo=pesos,
            tipos_desactivados=desactivados,
        )
        score_por_sesion[r.id] = score
        if score >= umbral:
            en_riesgo += 1
        dist[banda_de_score(score, bandas)] += 1

    # Mapa examen_contenido_id → (materia_id, nombre) para el desglose por materia.
    ec_ids = {r.examen_contenido_id for r in ses_rows if r.examen_contenido_id}
    ec_a_materia: dict[str, tuple[str, str]] = {}
    ec_a_comision: dict[str, tuple[str, str]] = {}
    if ec_ids:
        mrows = (
            await db.execute(
                select(
                    ExamenContenidoModel.id,
                    MateriaModel.id,
                    MateriaModel.nombre,
                    ComisionModel.id,
                    ComisionModel.nombre,
                )
                .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .join(MateriaModel, ComisionModel.materia_id == MateriaModel.id)
                .where(ExamenContenidoModel.id.in_(ec_ids))
            )
        ).all()
        for ec_id, mid, materia_nombre, cid, comision_nombre in mrows:
            ec_a_materia[ec_id] = (mid, materia_nombre)
            ec_a_comision[ec_id] = (cid, comision_nombre)

    # Agregados en Python sobre las filas ya cargadas (sin más viajes a la DB).
    materia_agg: dict[str, list] = {}  # mid → [nombre, sesiones, en_riesgo]
    comision_agg: dict[str, list] = {}  # cid → [nombre, sesiones, en_riesgo]
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
        # por comisión
        cc = ec_a_comision.get(r.examen_contenido_id)
        if cc is not None:
            cid, comision_nombre = cc
            cagg = comision_agg.setdefault(cid, [comision_nombre, 0, 0])
            cagg[1] += 1
            if score_por_sesion[r.id] >= umbral:
                cagg[2] += 1
        # por día
        if r.creada_en is not None:
            fecha = (
                r.creada_en.date().isoformat()
                if hasattr(r.creada_en, "date")
                else str(r.creada_en)[:10]
            )
            dia_agg[fecha] = dia_agg.get(fecha, 0) + 1
        # por decisión de revisión — solo sesiones en cola de riesgo (score >= umbral)
        if score_por_sesion[r.id] >= umbral:
            clave = r.decision or "sin_revisar"
            dec_agg[clave] = dec_agg.get(clave, 0) + 1

    por_materia = [
        MateriaStat(materia_id=mid, nombre=v[0], sesiones=v[1], en_riesgo=v[2])
        for mid, v in materia_agg.items()
    ]
    por_materia.sort(key=lambda m: (-m.sesiones, m.nombre))

    por_comision = [
        ComisionStat(comision_id=cid, nombre=v[0], sesiones=v[1], en_riesgo=v[2])
        for cid, v in comision_agg.items()
    ]
    por_comision.sort(key=lambda c: (-c.sesiones, c.nombre))

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
        por_comision=por_comision,
        top_eventos=top_eventos,
        por_dia=por_dia,
        decisiones=dec_agg,
        elegibilidad=elegibilidad,
    )
