"""Read-model de resultados de un examen para el admin (C-69 admin-sync, tarea 2).

Deriva de proctoring_session (sesiones FINALIZADAS vinculadas al examen) + el estado
de write-back (moodle_writeback_estado, LEFT JOIN) + la nota calculada/persistida.

L2.5 / D3: NUNCA expone es_correcta ni las respuestas — solo identidad del alumno,
nota académica, estado del envío a Moodle y la marca de actualización.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.moodle.writeback_service import MoodleWritebackService
from app.application.proctoring.auto_finalizacion import auto_finalizar_si_vencida
from app.application.proctoring.scoring import (
    calcular_score,
    desactivados_de_snapshot,
    pesos_de_snapshot,
    umbral_de_snapshot,
)
from app.domain.exam_content.visibilidad import (
    nota_visible,
    nota_visible_para_alumno,
    revision_visible,
)
from app.domain.exam_content.estado_entrega import ESTADO_SIN_TOKEN, EstadoEntregaNota
from app.domain.exam_content.resultado_nota import (
    ResultadoNota,
    nota_efectiva,
    resultado_de,
)
from app.domain.review.decision import nota_esta_anulada
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)

# Re-exportados desde el dominio (`EstadoEntregaNota`), que es la fuente única. Se dejan
# con estos nombres porque los usan la query, los routers y varios tests.
ESTADO_PENDIENTE = EstadoEntregaNota.PENDIENTE.value
ESTADO_MANUAL = EstadoEntregaNota.MANUAL.value

#: Retenciones que traba una PERSONA (el veredicto de integridad), y no una
#: configuracion faltante. Separa los dos avisos de arriba de la tabla, que
#: mandan al docente a lugares distintos: uno a la cola de revision, el otro a
#: configurar el destino de la nota.
_MOTIVOS_DE_REVISION = frozenset({"en_riesgo", "anulada"})

# Umbral de cola de revision por defecto si el singleton de config no existe (mismo
# default que ConfiguracionSistemaModel.umbral_cola_revision y el mock del frontend).
UMBRAL_COLA_REVISION_DEFAULT = 70

# Estados de "entrega" (C-76 tarea 14). DERIVADO, NUNCA persistido — se calcula
# en la query a partir de finalizada_en/en_cola_revision/decision, para no
# duplicar la fuente de verdad. Distinto y ortogonal a `estado_moodle`
# (sync a Moodle), que no se toca.
ESTADO_ENTREGA_NO_FINALIZADA = "no_finalizada"
ESTADO_ENTREGA_EN_REVISION = "en_revision"
ESTADO_ENTREGA_REVISADA = "revisada"
ESTADO_ENTREGA_FINALIZADA = "finalizada"

ESTADOS_ENTREGA_VALIDOS = frozenset(
    {
        ESTADO_ENTREGA_NO_FINALIZADA,
        ESTADO_ENTREGA_EN_REVISION,
        ESTADO_ENTREGA_REVISADA,
        ESTADO_ENTREGA_FINALIZADA,
    }
)

# Filtro de archivado (c-78 D6). Era un `bool` en la query string, así que "incluir
# archivadas" era INEXPRESABLE: `false` = solo no archivadas, `true` = solo
# archivadas, y no había forma de pedir el conjunto completo — que es justo lo que
# necesita quien busca un intento que alguien archivó. El servicio ya soportaba
# `archivado=None` (sin filtro); el único bloqueo era el tipado del router.
ARCHIVADO_NO = "false"
ARCHIVADO_SI = "true"
ARCHIVADO_TODAS = "todas"

ARCHIVADO_VALIDOS = frozenset({ARCHIVADO_NO, ARCHIVADO_SI, ARCHIVADO_TODAS})


def archivado_filtro(valor: str) -> bool | None:
    """Traduce el parámetro tri-estado al filtro del servicio (función PURA).

    ``"false"`` → ``False`` (solo no archivadas, el default observable de antes),
    ``"true"`` → ``True`` (solo archivadas), ``"todas"`` → ``None`` (sin filtro).
    El caller valida contra ``ARCHIVADO_VALIDOS`` ANTES: acá un valor fuera del
    conjunto cae al default seguro y nunca abre el listado de más.
    """
    if valor == ARCHIVADO_TODAS:
        return None
    if valor == ARCHIVADO_SI:
        return True
    return False


def estado_entrega(
    *, finalizada_en: object | None, en_cola_revision: bool, decision: str | None
) -> str:
    """Deriva el estado de la ENTREGA (L2.5, C-76 tarea 14) — funcion PURA.

    - `no_finalizada`: el alumno no entrego/no termino (`finalizada_en` None).
    - `revisada`: ya hay veredicto humano registrado (`decision` no None) —
      SIEMPRE gana sobre `en_cola_revision`, sea cual sea el veredicto
      (aprobado/anulado): una vez que una persona decidio, la entrega dejo de
      estar "en revision" (regla dura #5: la decision es siempre humana).
    - `en_revision`: finalizada, el score supera el umbral (`en_cola_revision`)
      y todavia nadie decidio.
    - `finalizada`: caso base — finalizada, sin flag de revision, sin decision.
    """
    if finalizada_en is None:
        return ESTADO_ENTREGA_NO_FINALIZADA
    if decision is not None:
        return ESTADO_ENTREGA_REVISADA
    if en_cola_revision:
        return ESTADO_ENTREGA_EN_REVISION
    return ESTADO_ENTREGA_FINALIZADA


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
    # Por que la nota NO se va a sincronizar: en_riesgo | anulada.
    # None = nada la retiene. Es ortogonal a `estado_moodle`: una fila retenida
    # sigue estando 'pendiente' en la tabla, pero apretar "Sincronizar" no la manda.
    retenido_por: str | None = None
    #: TODOS los motivos que la retienen, del más importante al menos. La fila
    #: los muestra todos: al examen le falta el destino para TODOS los alumnos,
    #: y decírselo a la mitad se lee como un error de la pantalla.
    retenciones: list[str] = field(default_factory=list)
    # c-78: POR QUE fallo el envio a Moodle. Ya se guardaba en la tabla y no se
    # exponia: la pantalla decia "fallido" y el motivo habia que ir a buscarlo
    # reproduciendo el write-back a mano contra el campus.
    error_detalle: str | None = None
    # C-76 tarea 14: estado de la ENTREGA (derivado) + soft-hide administrativo.
    estado_entrega: str = ESTADO_ENTREGA_FINALIZADA
    archivado: bool = False
    # c-78 D14: quién afirmó que cargó la nota a mano en el campus, y cuándo.
    # None = nunca se marcó a mano (el estado viene del sistema, no de una persona).
    marcada_manual_por: str | None = None
    marcada_manual_en: object | None = None
    # El resultado ACADÉMICO, ya resuelto acá: aprobado | desaprobado | anulada |
    # sin_nota | sin_criterio (`ResultadoNota`). Se manda resuelto para que ni la
    # pantalla ni el export tengan que decidirlo — cuando cada uno lo decidía por
    # su cuenta, el archivo decía "Aprobado" sobre una nota anulada.
    resultado: str = ""
    # `aprobado` sigue saliendo por compatibilidad, pero el que manda es
    # `resultado`: contempla la anulación, que un booleano no puede expresar.
    aprobado: bool | None = None
    nota_aprobacion: float | None = None
    #: Sólo en las filas de ausentes (no tienen sesión): sirve para identificar
    #: al alumno cuando `session_id` viene vacío.
    usuario_id: str | None = None
    # La nota que VALE. Una anulación la deja en 0; `nota` conserva la calculada
    # para poder mostrar "la nota calculada era 78" sin perder el dato.
    nota_efectiva: float | None = None


#: Marca del que NO SE PRESENTÓ. No es un motivo de retención de la entrega: es
#: la explicación de un 0 que nadie sacó rindiendo. Va en la misma lista para
#: que la pantalla lo muestre igual que los otros, debajo del estado.
MOTIVO_NO_RINDIO = "no_rindio"


def fila_de_ausente(
    *, usuario_id: str, idnumber: str | None, email: str | None, nombre: str | None
) -> "ResultadoAlumno":
    """Fila del inscripto que NO rindió: 0 y desaprobado, diciendo por qué.

    Antes no aparecía: sin sesión de proctoring no había fila, así que de un
    curso de 40 el docente veía 30 y no tenía cómo saber quiénes faltaron.

    Va SIN `session_id` a propósito: no hay sesión, así que no hay nada que
    publicar, marcar ni archivar. La pantalla usa eso para no ofrecer acciones
    que no se pueden hacer.
    """
    return ResultadoAlumno(
        session_id="",
        alumno_idnumber=idnumber,
        alumno_email=email,
        alumno_nombre=nombre,
        nota=0.0,
        nota_efectiva=0.0,
        # Desaprobado, pero con el motivo: un 0 sin explicación se lee igual que
        # el de alguien que rindió y no supo nada, y se reclama distinto.
        resultado=ResultadoNota.DESAPROBADO.value,
        aprobado=False,
        estado_moodle=ESTADO_PENDIENTE,
        retenciones=[MOTIVO_NO_RINDIO],
        retenido_por=MOTIVO_NO_RINDIO,
        estado_entrega=ESTADO_ENTREGA_NO_FINALIZADA,
        actualizado_en=None,
        usuario_id=usuario_id,
    )


def _aprobado_de(nota, nota_aprobacion: float | None) -> bool | None:
    """True/False si se puede comparar; None si falta la nota o el criterio.

    None NO es False: "todavía no se sabe" y "no llegó" son cosas distintas, y
    el segundo se informa.
    """
    if nota is None or nota_aprobacion is None:
        return None
    return float(nota) >= nota_aprobacion


def estado_moodle_display(db_estado: str | None, *, moodle_configurado: bool) -> str:
    """Mapea el estado persistido al estado que ve el admin.

    Si Moodle no está configurado, una nota 'pendiente' se muestra como 'sin_token'
    (no se puede enviar todavía). 'enviado'/'fallido' se muestran tal cual.
    """
    estado = db_estado or ESTADO_PENDIENTE
    if not moodle_configurado and estado == ESTADO_PENDIENTE:
        return ESTADO_SIN_TOKEN
    # 'manual' NO se degrada a 'sin_token' aunque Moodle no esté configurado: es
    # justamente el caso en que alguien cargó la nota sin API. Decirle "sin
    # conexión al campus" a una nota que ya está cargada sería mentirle.
    return estado


def _base_stmt(examen_id: str):
    """Sesiones del examen + su estado de write-back (LEFT JOIN).

    C-76 tarea 14: YA NO exige `finalizada_en IS NOT NULL` — el estado
    `no_finalizada` (alumno que no entrego/no termino) tiene que poder listarse
    y filtrarse. El default sin filtros sigue mostrando lo mismo que antes en la
    practica (todas las sesiones del examen), pero ahora `estado_entrega`
    permite acotar. La identidad del alumno usa COALESCE: para una sesion sin
    write-back todavia (no finalizada) no hay fila en `moodle_writeback_estado`,
    asi que cae a la identidad persistida en la propia sesion (C-69 migration 0033).
    """
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    idnumber_expr = func.coalesce(
        MoodleWritebackEstadoModel.alumno_idnumber, ProctoringSessionModel.alumno_idnumber
    )
    email_expr = func.coalesce(
        MoodleWritebackEstadoModel.alumno_email, ProctoringSessionModel.alumno_email
    )

    return (
        select(
            ProctoringSessionModel.id.label("session_id"),
            ProctoringSessionModel.finalizada_en.label("finalizada_en"),
            ProctoringSessionModel.decision.label("decision"),
            ProctoringSessionModel.archivado.label("archivado"),
            idnumber_expr.label("alumno_idnumber"),
            email_expr.label("alumno_email"),
            MoodleWritebackEstadoModel.nota,
            MoodleWritebackEstadoModel.estado,
            MoodleWritebackEstadoModel.error_detalle,
            MoodleWritebackEstadoModel.updated_at,
            # c-78 D14: origen del estado. Sin esto la UI no puede distinguir
            # "confirmado por el campus" de "marcado por {persona} el {fecha}".
            MoodleWritebackEstadoModel.marcada_manual_por,
            MoodleWritebackEstadoModel.marcada_manual_en,
            # Nombre real de la persona. La tabla mostraba el legajo ("EST-001")
            # porque este campo se dejó en None como "enhancement futuro": quien
            # revisa notas trabaja con personas, no con identificadores internos.
            UsuarioModel.nombre.label("usuario_nombre"),
            UsuarioModel.apellido.label("usuario_apellido"),
        )
        .select_from(ProctoringSessionModel)
        .outerjoin(
            MoodleWritebackEstadoModel,
            MoodleWritebackEstadoModel.session_id == ProctoringSessionModel.id,
        )
        # OUTER: sin usuario en la tabla (o con la identidad solo en la sesión) la
        # fila igual tiene que salir — perder un resultado por no poder mostrar un
        # nombre sería peor que mostrar el legajo.
        .outerjoin(UsuarioModel, UsuarioModel.username == idnumber_expr)
        .where(
            ProctoringSessionModel.examen_contenido_id == examen_id,
            # migration 0102: la prueba del docente no es una rendición. Sin este
            # filtro figuraría en la tabla con nota propia y sería candidata a
            # publicarse en Moodle.
            ProctoringSessionModel.es_prueba.is_(False),
        )
    )


def _aplicar_filtros(
    stmt,
    *,
    q: str | None,
    estado: str | None,
    archivado: bool | None = False,
    fecha_desde: object | None = None,
    fecha_hasta: object | None = None,
):
    """Búsqueda por alumno, estado Moodle, archivado y rango de fecha — SIEMPRE en SQL."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    if q:
        patron = f"%{q.strip()}%"
        # El nombre entra en la búsqueda: ahora que la tabla muestra "Apellido,
        # Nombre", buscar por lo que se ve en pantalla tiene que funcionar — si no,
        # se escribe el apellido y no aparece nada.
        stmt = stmt.where(
            or_(
                MoodleWritebackEstadoModel.alumno_idnumber.ilike(patron),
                MoodleWritebackEstadoModel.alumno_email.ilike(patron),
                UsuarioModel.nombre.ilike(patron),
                UsuarioModel.apellido.ilike(patron),
            )
        )
    if estado:
        # 'sin_token' es un alias de display de 'pendiente' (mismo valor en DB).
        db_estado = ESTADO_PENDIENTE if estado == ESTADO_SIN_TOKEN else estado
        stmt = stmt.where(
            func.coalesce(MoodleWritebackEstadoModel.estado, ESTADO_PENDIENTE) == db_estado
        )
    if archivado is not None:
        stmt = stmt.where(ProctoringSessionModel.archivado.is_(archivado))
    if fecha_desde is not None:
        stmt = stmt.where(ProctoringSessionModel.finalizada_en >= fecha_desde)
    if fecha_hasta is not None:
        stmt = stmt.where(ProctoringSessionModel.finalizada_en <= fecha_hasta)
    return stmt


async def _flaggeadas_por_sesion(db: AsyncSession, session_ids: list[str]) -> dict[str, bool]:
    """``{session_id: True}`` para las sesiones cuyo score >= umbral de cola de revision.

    Reusa la MISMA fuente de pesos/umbral que `_motivos_retencion` y el detalle
    de sesion del proctor (`_pesos_vivos_por_tipo`/`_tipos_desactivados`/
    `_umbral_cola_revision`) — no duplica la formula de score, solo el glue de
    "recorrer session_ids"."""
    if not session_ids:
        return {}

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

    pesos_vivos = await _pesos_vivos_por_tipo(db)
    desactivados_vivos = await _tipos_desactivados(db)
    umbral_vivo = await _umbral_cola_revision(db)
    cfg = await _config_por_sesion(
        db, session_ids,
        pesos_vivos=pesos_vivos, desactivados_vivos=desactivados_vivos, umbral_vivo=umbral_vivo,
    )

    resultado: dict[str, bool] = {}
    for sid in session_ids:
        score, umbral_sid = cfg.score_de(sid, eventos_por_sesion.get(sid, []), umbral_vivo=umbral_vivo)
        resultado[sid] = score >= umbral_sid
    return resultado


async def _auto_finalizar_vencidas_del_examen(
    db: AsyncSession, examen_id: str, *, writeback_svc: MoodleWritebackService | None
) -> None:
    """Cierra LAZY las sesiones del examen que vencieron y siguen sin finalizar.

    Gap C-73: el lazy-finalize (`auto_finalizar_si_vencida`, C-72 §4) solo se
    disparaba desde el lado alumno (crear/reanudar sesión). Una sesión abandonada
    quedaba `finalizada_en = NULL` para siempre — invisible acá (que solo lista
    FINALIZADAS) pero seguía contando en "Sesiones iniciadas". Se detecta y cierra
    ACÁ, antes de armar la respuesta, para que el docente que mira Resultados
    nunca vea un examen eternamente "en curso". Reusa el MISMO camino de
    finalización + write-back que la finalización manual (mismo gate de revisión).
    Sin volumen de sesiones activas nunca (LAZY, no barrido — regla dura #4).
    """
    rows = await db.execute(
        select(ProctoringSessionModel).where(
            ProctoringSessionModel.examen_contenido_id == examen_id,
            ProctoringSessionModel.finalizada_en.is_(None),
            ProctoringSessionModel.es_prueba.is_(False),
        )
    )
    for sesion in rows.scalars().all():
        await auto_finalizar_si_vencida(db, sesion, writeback_svc=writeback_svc)


async def listar_resultados_examen(
    *,
    db: AsyncSession,
    examen_id: str,
    q: str | None = None,
    estado: str | None = None,
    estado_entrega_filtro: str | None = None,
    resultado_filtro: str | None = None,
    archivado: bool | None = False,
    fecha_desde: object | None = None,
    fecha_hasta: object | None = None,
    page: int = 1,
    page_size: int = 20,
    moodle_configurado: bool = True,
    writeback_svc: MoodleWritebackService | None = None,
    con_avisos: bool = False,
) -> tuple[list[ResultadoAlumno], int, dict[str, int] | None]:
    """Lista paginada de alumnos que rindieron el examen + total global filtrado.

    Orden estable: por finalizada_en descendente (más reciente primero), luego
    session_id para desempatar. Filtrado/orden SIEMPRE serverside (SQL) — salvo
    `estado_entrega_filtro`, que es DERIVADO (score vs umbral + decision, igual
    que `_motivos_retencion`) y no puede resolverse en un solo WHERE de SQL: en
    ese caso se traen todas las filas que matchean los demas filtros, se deriva
    el estado por fila, se filtra y se pagina en memoria (acotado al tamaño de
    un examen, no de la plataforma entera).
    """
    page = max(1, page)
    page_size = max(1, page_size)

    await _auto_finalizar_vencidas_del_examen(db, examen_id, writeback_svc=writeback_svc)

    base = _aplicar_filtros(
        _base_stmt(examen_id),
        q=q,
        estado=estado,
        archivado=archivado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    ).order_by(
        ProctoringSessionModel.finalizada_en.desc(),
        ProctoringSessionModel.id,
    )

    if estado_entrega_filtro:
        todas = (await db.execute(base)).all()
        flaggeadas = await _flaggeadas_por_sesion(db, [r.session_id for r in todas])
        todas = [
            r
            for r in todas
            if estado_entrega(
                finalizada_en=r.finalizada_en,
                en_cola_revision=flaggeadas.get(r.session_id, False),
                decision=r.decision,
            )
            == estado_entrega_filtro
        ]
        total = len(todas)
        inicio = (page - 1) * page_size
        rows = todas[inicio : inicio + page_size]
        # Las filas de la pagina ya tienen su flag de "en cola" resuelto arriba —
        # subset del dict, no hace falta recalcular.
        flaggeadas_pagina = {row.session_id: flaggeadas.get(row.session_id, False) for row in rows}
    else:
        total = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        page_stmt = base.offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(page_stmt)).all()
        # Sin filtro por estado_entrega, solo hace falta el flag para la PAGINA
        # visible (no para todo el examen) — igual que `_motivos_retencion`.
        flaggeadas_pagina = await _flaggeadas_por_sesion(db, [row.session_id for row in rows])

    # Motivo de RETENCION por fila. La nota de una sesion en riesgo NO se sincroniza
    # (gate D15, mismo `writeback_en_hold` que usa el envio), pero su estado seguia
    # mostrandose como "pendiente": indistinguible de una nota que solo falta mandar.
    # El admin apretaba "Sincronizar (2 pendientes)", se enviaba 1 y nada explicaba
    # por que. Se calcula aca para que la UI pueda marcarla.
    retenciones = await _motivos_retencion(db, [row.session_id for row in rows])

    # UNA consulta para todo el listado: las filas son de un solo examen, así que
    # la nota de aprobación es la misma para todas. Sin esto la pantalla no podía
    # decir si el alumno aprobó — el dato por el que se abre esta tabla.
    nota_aprobacion = (
        await db.execute(
            select(ExamenContenidoModel.nota_aprobacion).where(
                ExamenContenidoModel.id == examen_id
            )
        )
    ).scalar_one_or_none()
    nota_aprobacion = float(nota_aprobacion) if nota_aprobacion is not None else None

    filas = [
        ResultadoAlumno(
            session_id=row.session_id,
            alumno_idnumber=row.alumno_idnumber,
            alumno_email=row.alumno_email,
            alumno_nombre=_nombre_completo(
                getattr(row, "usuario_nombre", None),
                getattr(row, "usuario_apellido", None),
            ),
            nota=float(row.nota) if row.nota is not None else None,
            estado_moodle=estado_moodle_display(
                row.estado, moodle_configurado=moodle_configurado
            ),
            actualizado_en=row.updated_at or row.finalizada_en,
            retenido_por=(retenciones.get(row.session_id) or [None])[0],
            retenciones=retenciones.get(row.session_id, []),
            error_detalle=getattr(row, "error_detalle", None),
            estado_entrega=estado_entrega(
                finalizada_en=row.finalizada_en,
                en_cola_revision=flaggeadas_pagina.get(row.session_id, False),
                decision=row.decision,
            ),
            archivado=bool(row.archivado),
            marcada_manual_por=getattr(row, "marcada_manual_por", None),
            marcada_manual_en=getattr(row, "marcada_manual_en", None),
            # None (y no False) cuando falta la nota o el examen no tiene nota de
            # aprobación: "todavía no se sabe" no es "desaprobó".
            aprobado=_aprobado_de(row.nota, nota_aprobacion),
            nota_aprobacion=nota_aprobacion,
            resultado=resultado_de(
                aprobado=_aprobado_de(row.nota, nota_aprobacion),
                nota=float(row.nota) if row.nota is not None else None,
                retenido_por=(retenciones.get(row.session_id) or [None])[0],
            ).value,
            nota_efectiva=nota_efectiva(
                nota=float(row.nota) if row.nota is not None else None,
                retenido_por=(retenciones.get(row.session_id) or [None])[0],
            ),
        )
        for row in rows
    ]
    # Los INSCRIPTOS que no rindieron. Son parte del listado: de un curso de 40
    # el docente veía 30 filas y no tenía cómo saber quiénes faltaron. Se traen
    # sólo en la PRIMERA página y sin filtros activos, porque son filas
    # sintéticas (sin sesión) que no participan de la búsqueda ni del orden.
    if page == 1 and not q and not estado and not estado_entrega_filtro:
        ausentes = await _ausentes_del_examen(db, examen_id)
        filas = filas + ausentes
        total += len(ausentes)

    if resultado_filtro:
        # Se filtra acá y no en SQL porque el resultado no está en ninguna
        # columna: sale de comparar la nota contra la de aprobación del examen.
        filas = [f for f in filas if f.resultado == resultado_filtro]
        total = len(filas)
    items = filas

    # Los avisos de arriba de la tabla ("N notas retenidas por revisión") son
    # agregados del EXAMEN. Se calculaban en el cliente sobre los items de la
    # página, así que al pasar a la página 2 el número cambiaba o desaparecía —
    # y es el número con el que el docente decide a quién ir a destrabar.
    avisos = await _avisos_del_examen(db, examen_id) if con_avisos else None
    return items, int(total), avisos


def motivos_de_una_fila(
    *, en_hold: bool, anulada: bool, sin_destino: bool, sin_credencial: bool
) -> list[str]:
    """TODOS los motivos que retienen una nota, del más importante al menos.

    Antes se devolvía UNO solo, y el de la sesión (anulada/en riesgo) hacía que
    ni se mirara el destino: sobre el mismo examen, tres filas decían "Falta el
    destino" y las otras tres no. Al examen le falta para todas por igual, así
    que la pantalla tiene que decirlo en todas.

    Primero lo de ESTA persona y después lo del examen: uno lo resuelve un
    revisor y el otro el administrador, y son trámites distintos.
    """
    motivos: list[str] = []
    if en_hold:
        motivos.append("anulada" if anulada else "en_riesgo")
    if sin_destino:
        motivos.append("sin_destino")
    if sin_credencial:
        motivos.append("sin_credencial_docente")
    return motivos


async def _motivos_retencion(
    db: AsyncSession, session_ids: list[str]
) -> dict[str, list[str]]:
    """``{session_id: motivo}`` para las sesiones cuya nota esta retenida.

    Motivos, en castellano llano porque salen tal cual a la pantalla:
      - "en_riesgo"      : supero el umbral y todavia nadie la reviso.
      - "anulada"        : anulada por fraude — la nota no se sincroniza.
      - "sin_destino"    : el examen no tiene curso/actividad en el campus.
      - "sin_credencial_docente": la comision no tiene docente a cargo, o el docente
        no conecto su cuenta del campus (o su token se cayo). La nota NO se manda con
        la cuenta institucional a proposito: llegaria a la libreta sin responsable
        identificable, y en silencio. Se destraba sola cuando el docente conecta.
    Una sesion sin retencion no aparece en el dict.

    "sin_destino" existe porque el destino dejo de tener fallback global: antes, un
    examen sin destino propio mandaba la nota al curso global (la libreta equivocada)
    y la fila se veia como enviada. Ahora se retiene y se dice por que.
    """
    if not session_ids:
        return {}

    from app.domain.review.decision import DecisionSesion, writeback_en_hold

    rows = (
        await db.execute(
            select(
                ProctoringSessionModel.id,
                ProctoringSessionModel.decision,
            ).where(ProctoringSessionModel.id.in_(session_ids))
        )
    ).all()

    # Sesiones cuyo examen no tiene destino en el campus: la nota no puede salir.
    # C-73 §10.4: sesiones cuyo docente a cargo no tiene credencial usable. La nota
    # SIEMPRE debe salir con la identidad del docente que la devuelve; sin ella se
    # retiene en vez de firmarla con la cuenta de servicio.
    from app.infrastructure.persistence.models.comision_tutor import ComisionTutorModel
    from app.infrastructure.persistence.models.exam_content import ComisionModel
    from app.infrastructure.persistence.models.transactional import (
        MoodleCredencialDocenteModel,
    )

    # c-78 (deuda c-79): los tutores salen de la tabla puente, NO de
    # `comision.docente_id` — esa columna quedó congelada en la migración 0086 y
    # ningún endpoint la escribe, así que joinear por ella marcaba TODAS las
    # sesiones como "sin credencial".
    #
    # La pertenencia es SIMÉTRICA: alcanza con que UN tutor de la comisión tenga
    # credencial activa para que la nota pueda salir. Por eso se calcula primero el
    # conjunto de las que SÍ pueden, y `sin_credencial` es el complemento — una
    # sesión con tres tutores, dos sin conectar y uno conectado, puede sincronizar.
    con_credencial = {
        sid
        for (sid,) in (
            await db.execute(
                select(ProctoringSessionModel.id)
                .join(
                    ExamenContenidoModel,
                    ExamenContenidoModel.id
                    == ProctoringSessionModel.examen_contenido_id,
                )
                .join(
                    ComisionModel, ComisionModel.id == ExamenContenidoModel.comision_id
                )
                .join(
                    ComisionTutorModel,
                    ComisionTutorModel.comision_id == ComisionModel.id,
                )
                .join(
                    MoodleCredencialDocenteModel,
                    MoodleCredencialDocenteModel.usuario_id
                    == ComisionTutorModel.tutor_id,
                )
                .where(
                    ProctoringSessionModel.id.in_(session_ids),
                    MoodleCredencialDocenteModel.token_cifrado.is_not(None),
                    MoodleCredencialDocenteModel.estado == "activa",
                )
                .distinct()
            )
        ).all()
    }
    sin_credencial = set(session_ids) - con_credencial

    sin_destino = {
        sid
        for sid, courseid, cmid in (
            await db.execute(
                select(
                    ProctoringSessionModel.id,
                    ExamenContenidoModel.moodle_courseid,
                    ExamenContenidoModel.moodle_cmid,
                )
                .outerjoin(
                    ExamenContenidoModel,
                    ExamenContenidoModel.id == ProctoringSessionModel.examen_contenido_id,
                )
                .where(ProctoringSessionModel.id.in_(session_ids))
            )
        ).all()
        if not courseid or not cmid
    }

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

    pesos_vivos = await _pesos_vivos_por_tipo(db)
    desactivados_vivos = await _tipos_desactivados(db)
    umbral_vivo = await _umbral_cola_revision(db)
    cfg = await _config_por_sesion(
        db, session_ids,
        pesos_vivos=pesos_vivos, desactivados_vivos=desactivados_vivos, umbral_vivo=umbral_vivo,
    )

    motivos: dict[str, list[str]] = {}
    for row in rows:
        score, umbral = cfg.score_de(
            row.id, eventos_por_sesion.get(row.id, []), umbral_vivo=umbral_vivo
        )
        flaggeada = score >= umbral
        decision = _parse_decision_val(row.decision)
        de_la_fila = motivos_de_una_fila(
            en_hold=writeback_en_hold(flaggeada=flaggeada, decision=decision),
            anulada=decision is DecisionSesion.ANULADO,
            sin_destino=row.id in sin_destino,
            sin_credencial=row.id in sin_credencial,
        )
        if de_la_fila:
            motivos[row.id] = de_la_fila
    return motivos


async def _avisos_del_examen(db: AsyncSession, examen_id: str) -> dict[str, int]:
    """Cuántas notas del examen están trabadas, y por qué.

    Recorre TODAS las rendiciones reales del examen (no la página) y usa las
    mismas retenciones que la tabla, así el aviso y las filas no pueden decir
    cosas distintas.
    """
    filas = (
        await db.execute(
            select(
                ProctoringSessionModel.id,
                ProctoringSessionModel.decision,
                MoodleWritebackEstadoModel.estado,
            )
            .join(
                MoodleWritebackEstadoModel,
                MoodleWritebackEstadoModel.session_id == ProctoringSessionModel.id,
            )
            .where(
                ProctoringSessionModel.examen_contenido_id == examen_id,
                ProctoringSessionModel.es_prueba.is_(False),
            )
        )
    ).all()

    session_ids = [str(f[0]) for f in filas]
    retenciones = await _motivos_retencion(db, session_ids)

    por_revision = 0
    por_configuracion = 0
    for sid, _decision, estado in filas:
        motivos = retenciones.get(str(sid)) or []
        if not motivos:
            continue
        if any(m in _MOTIVOS_DE_REVISION for m in motivos):
            por_revision += 1
        elif estado != ESTADO_MANUAL:
            # Una nota ya cargada a mano no espera que se configure nada: el
            # número ya está en la libreta.
            por_configuracion += 1

    return {
        "retenidas_por_revision": por_revision,
        "sin_sincronizar_config": por_configuracion,
    }


async def _ausentes_del_examen(
    db: AsyncSession, examen_id: str
) -> list[ResultadoAlumno]:
    """Inscriptos de la comisión del examen que no tienen sesión.

    "No rindió" es una respuesta que el listado tiene que poder dar: si no
    aparece, el docente no distingue entre un alumno que no está inscripto y uno
    que se ausentó.
    """
    from app.infrastructure.persistence.models.inscripcion import InscripcionModel
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    # Quién rindió se pregunta sobre TODAS las sesiones del examen, no sobre la
    # página que se está mostrando: mirando sólo la página, un alumno que rindió
    # y quedó en la página 2 aparecía ADEMÁS como ausente en la 1.
    rindieron = {
        fila[0]
        for fila in (
            await db.execute(
                # A PROPOSITO sin filtrar por es_prueba: acá se pregunta quién
                # NO tiene sesión, y el docente que probó su examen tiene una.
                # Filtrando, quedaba fuera de la lista de "rindieron" y aparecía
                # como ausente con 0 y desaprobado. Que la prueba no valga como
                # nota no la vuelve inexistente.
                select(ProctoringSessionModel.alumno_idnumber).where(
                    ProctoringSessionModel.examen_contenido_id == examen_id,
                )
            )
        ).all()
    }

    rows = (
        await db.execute(
            select(
                UsuarioModel.id,
                UsuarioModel.username,
                UsuarioModel.email,
                UsuarioModel.nombre,
                UsuarioModel.apellido,
            )
            .select_from(ExamenContenidoModel)
            .join(
                InscripcionModel,
                InscripcionModel.comision_id == ExamenContenidoModel.comision_id,
            )
            .join(UsuarioModel, UsuarioModel.id == InscripcionModel.usuario_id)
            .where(
                ExamenContenidoModel.id == examen_id,
                # Un alumno dado de baja no se cuenta como ausente: ya no cursa.
                UsuarioModel.eliminado_en.is_(None),
            )
        )
    ).all()

    return [
        fila_de_ausente(
            usuario_id=r.id,
            idnumber=r.username,
            email=r.email,
            nombre=_nombre_completo(r.nombre, r.apellido),
        )
        for r in rows
        if r.username not in rindieron
    ]


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
    *, db: AsyncSession, examen_id: str, session_ids: list[str] | None = None
) -> list[MoodleWritebackEstadoModel]:
    """Filas de write-back en estado 'pendiente'/'fallido' del examen (para sincronizar).

    Las 'enviado' se excluyen (idempotencia: no se re-mandan).

    C-71 slice 2 (D15), modelo colapsado a un solo paso: además se RETIENEN
    (hold) las sesiones flaggeadas y sin decidir, o decididas como `anulado`.
    El gate se evalúa aquí, ANTES del envío (este es el único punto donde el
    estado pasa a 'enviado', en el sync manual del admin), de modo que una sesión
    problemática nunca alcanza 'enviado'. Release si la decisión fue `aprobado`
    o si la sesión nunca se flaggeó.

    D12 (parte B): refresca el destino (moodle_courseid/cmid) de cada fila desde el
    valor ACTUAL del examen, para que un admin que fija el target DESPUÉS de finalizar
    sincronice al curso correcto. NULL en el examen → la fila queda NULL y el cliente
    cae al global. El refresco es en memoria sobre la misma sesión (mismo identity map);
    el commit del caller lo persiste.

    ``session_ids``: cuando se pasa, filtra a esas sesiones específicas (subida
    individual o lote sobre selección). Las retenciones D15 siguen aplicándose aunque
    la sesión esté en la lista (el gate nunca se bypasea). Sin este parámetro,
    comportamiento original: todas las pendientes/fallidas del examen.
    """
    conds = [
        ProctoringSessionModel.examen_contenido_id == examen_id,
        MoodleWritebackEstadoModel.estado.in_((ESTADO_PENDIENTE, "fallido")),
        ProctoringSessionModel.es_prueba.is_(False),
    ]
    if session_ids:
        conds.append(MoodleWritebackEstadoModel.session_id.in_(session_ids))

    stmt = (
        select(
            MoodleWritebackEstadoModel,
            ProctoringSessionModel.id.label("sid"),
            ProctoringSessionModel.decision,
            # c-78 D7: eje TEMPORAL real del intento. Sin esto, la política
            # ULTIMO/PRIMERO ordenaba por `session_id`, que es un UUID v4
            # (`gen_random_uuid()`) — o sea, orden ALEATORIO. Afectaba QUÉ NOTA se
            # escribe en Moodle, que es el daño más concreto de toda la auditoría.
            ProctoringSessionModel.creada_en.label("sesion_creada_en"),
        )
        .join(
            ProctoringSessionModel,
            ProctoringSessionModel.id == MoodleWritebackEstadoModel.session_id,
        )
        .where(*conds)
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
    pesos_vivos = await _pesos_vivos_por_tipo(db)
    desactivados_vivos = await _tipos_desactivados(db)
    umbral_vivo = await _umbral_cola_revision(db)
    cfg = await _config_por_sesion(
        db, session_ids,
        pesos_vivos=pesos_vivos, desactivados_vivos=desactivados_vivos, umbral_vivo=umbral_vivo,
    )

    from app.domain.review.decision import writeback_en_hold

    filas: list[MoodleWritebackEstadoModel] = []
    for r in rows:
        estado = r[0]
        score, umbral = cfg.score_de(
            r.sid, eventos_por_sesion.get(r.sid, []), umbral_vivo=umbral_vivo
        )
        flaggeada = score >= umbral
        decision = _parse_decision_val(r.decision)
        if writeback_en_hold(flaggeada=flaggeada, decision=decision):
            continue  # hold: no se envía (D15)
        # Proyección del eje temporal sobre la fila (atributo NO mapeado, vive solo
        # en memoria): es lo que consume `_aplicar_politica` para resolver
        # ULTIMO/PRIMERO por tiempo real en vez de por el UUID de la sesión.
        estado.sesion_creada_en = r.sesion_creada_en
        filas.append(estado)

    courseid, cmid, component = await obtener_target_examen(db=db, examen_id=examen_id)
    for fila in filas:
        fila.moodle_courseid = courseid
        fila.moodle_cmid = cmid
        fila.moodle_component = component

    return filas


def _parse_decision_val(value: str | None):
    """Convierte el string persistido en ``DecisionSesion`` (pendiente si falta)."""
    from app.domain.review.decision import DecisionSesion

    if value is None:
        return DecisionSesion.PENDIENTE
    try:
        return DecisionSesion(value)
    except ValueError:
        return DecisionSesion.PENDIENTE


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
    veredicto: str | None  # 'anulado' cuando la nota fue anulada; si no, None
    # Informe de devolución disponible SOLO cuando la nota fue anulada por fraude
    # (D12, minimización Ley 25.326). El resto de los casos: no se expone evidencia.
    informe_disponible: bool
    #: El resultado resuelto por el backend (`ResultadoNota`). Vacío mientras la
    #: nota no sea visible: ahí no hay nada que afirmar todavía.
    resultado: str = ""


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


async def _tipos_desactivados(db: AsyncSession) -> frozenset[str]:
    """Tipos con fila en evento_score_config pero ``activo=False``.

    Se consulta aparte de los pesos porque "apagado" y "desconocido" NO son lo
    mismo para el score: el apagado pesa 0 (el admin lo decidio), el desconocido
    degrada por severidad (RN-GLB-03). Sin esta lista, ambos se veian igual —
    ausentes del mapa de pesos— y desactivar un detector no lo desactivaba.

    Set vacio si la tabla no esta disponible (degradacion graceful: nada se apaga)."""
    from app.infrastructure.persistence.models.transactional import (
        EventoScoreConfigModel,
    )

    try:
        result = await db.execute(
            select(EventoScoreConfigModel.tipo_evento).where(
                EventoScoreConfigModel.activo.is_(False)
            )
        )
        return frozenset(result.scalars().all())
    except Exception:  # noqa: BLE001 — sin config, no se apaga nada
        return frozenset()


@dataclass(frozen=True, slots=True)
class _ConfigPorSesion:
    """Pesos/desactivados/umbral EFECTIVOS por sesion (migration 0083).

    Cada sesion puntua con la foto de config tomada al CREARLA
    (``config_snapshot``), no con la config viva — un cambio de umbral/pesos
    posterior no debe alterar retroactivamente el score/gate de una sesion que
    ya arranco. Sesiones sin foto (pre-migracion o degradacion al crear) caen
    a los valores vivos, pasados aca como fallback."""

    pesos: dict[str, dict[str, int] | None]
    desactivados: dict[str, frozenset[str]]
    umbral: dict[str, int]

    def score_de(self, session_id: str, eventos: list, *, umbral_vivo: int) -> tuple[int, int]:
        """``(score, umbral)`` efectivos de una sesion sobre su lista de eventos."""
        score = calcular_score(
            eventos,
            pesos_por_tipo=self.pesos.get(session_id),
            tipos_desactivados=self.desactivados.get(session_id, frozenset()),
        )
        return score, self.umbral.get(session_id, umbral_vivo)


async def _config_por_sesion(
    db: AsyncSession, session_ids: list[str], *, pesos_vivos, desactivados_vivos, umbral_vivo: int
) -> _ConfigPorSesion:
    """Resuelve pesos/desactivados/umbral por sesion desde su ``config_snapshot``,
    con los valores VIVOS (ya resueltos por el caller) como fallback."""
    if not session_ids:
        return _ConfigPorSesion(pesos={}, desactivados={}, umbral={})
    rows = await db.execute(
        select(ProctoringSessionModel.id, ProctoringSessionModel.config_snapshot).where(
            ProctoringSessionModel.id.in_(session_ids)
        )
    )
    pesos: dict[str, dict[str, int] | None] = {}
    desactivados: dict[str, frozenset[str]] = {}
    umbral: dict[str, int] = {}
    for sid, snapshot in rows.all():
        pesos[sid] = pesos_de_snapshot(snapshot, pesos_vivos=pesos_vivos)
        desactivados[sid] = desactivados_de_snapshot(snapshot, desactivados_vivos=desactivados_vivos)
        umbral[sid] = umbral_de_snapshot(snapshot, umbral_vivo=umbral_vivo)
    return _ConfigPorSesion(pesos=pesos, desactivados=desactivados, umbral=umbral)


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
            # `decision` viaja para saber si la revisión YA ocurrió (y con qué
            # veredicto): sin esto, "en cola de revisión" se calculaba solo por
            # score y quedaba pegado para siempre, aun con el caso ya decidido.
            ProctoringSessionModel.decision,
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

    pesos_vivos = await _pesos_vivos_por_tipo(db)
    desactivados_vivos = await _tipos_desactivados(db)
    umbral_vivo = await _umbral_cola_revision(db)
    cfg = await _config_por_sesion(
        db, session_ids,
        pesos_vivos=pesos_vivos, desactivados_vivos=desactivados_vivos, umbral_vivo=umbral_vivo,
    )
    restituidas = await _sesiones_con_restitucion(db, session_ids)
    # c-78: la retención de CADA sesión, para que publicar las notas del examen no
    # descubra la de un alumno cuya integridad todavía está en revisión. Una sola
    # consulta para todas (no N+1), reusando el mismo cálculo que usa el panel de
    # notas y el sincronizado — no un criterio propio.
    retenciones_alumno = await _motivos_retencion(db, session_ids)

    ahora = datetime.now(tz=timezone.utc)
    items: list[MiNota] = []
    for r in rows:
        evs = eventos_por_sesion.get(r.session_id, [])
        score, umbral = cfg.score_de(r.session_id, evs, umbral_vivo=umbral_vivo)
        nota_real = float(r.nota) if r.nota is not None else None
        nota_aprobacion = (
            float(r.nota_aprobacion) if r.nota_aprobacion is not None else None
        )
        # Gate de visibilidad (C-69): si la nota aún no es visible NO se filtra el
        # número al cliente (nota=None); la UI muestra "disponible al cerrar".
        #
        # c-78: además de la publicación del examen, pesa la RETENCIÓN de ESTA
        # sesión. Publicar no alcanza si la nota está retenida por integridad
        # (superó el umbral y nadie revisó, o fue anulada): mostrar un número que
        # puede anularse después es peor que no mostrar nada — el alumno lo lee
        # como su nota y el sistema termina sacándole algo que ya le dio.
        # Sin `error_detalle`: el motivo por el que la nota no llegó al campus es
        # para el DOCENTE (dice cosas como "User is not enrolled..."), no decide
        # si el alumno ve su nota — y la función nunca lo aceptó, así que pasarlo
        # tiraba TypeError y dejaba la pantalla entera en 500.
        visible = nota_visible_para_alumno(
            mostrar_nota=r.mostrar_nota,
            cierre=r.cierre,
            ahora=ahora,
            retenido_por=retenciones_alumno.get(r.session_id),
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
        # Veredicto de decisión (modelo de un solo paso): estado efectivo
        # DERIVADO del último acto (D10b). anulada = decision 'anulado' Y sin
        # acto compensatorio de restitución posterior (nota_restituida).
        decision_mi_nota = _parse_decision_val(r.decision)
        anulada = nota_esta_anulada(decision_mi_nota, r.session_id in restituidas)
        items.append(
            MiNota(
                examen_id=r.examen_contenido_id or "",
                examen_titulo=r.examen_titulo or "",
                nota=nota_out,
                nota_maxima=float(r.nota_maxima) if r.nota_maxima is not None else None,
                aprobado=aprobado,
                # El resultado RESUELTO, igual que en el listado del docente: el
                # alumno tiene que ver lo mismo que el docente sobre su nota. Con
                # la nota todavía no visible no se afirma nada.
                resultado=(
                    resultado_de(
                        aprobado=aprobado,
                        nota=nota_real,
                        retenido_por=(retenciones_alumno.get(r.session_id) or [None])[0],
                    ).value
                    if visible
                    else ""
                ),
                estado_moodle=estado_moodle_display(
                    r.estado, moodle_configurado=moodle_configurado
                ),
                # "En cola" = supera el umbral Y TODAVÍA NO tiene decisión humana.
                # Antes era solo `score >= umbral`, así que después de resolver el
                # caso el alumno seguía leyendo "un docente la revisará y confirmará
                # tu nota" al lado de "Nota anulada por fraude": dos mensajes que se
                # contradicen, justo cuando más claridad necesita.
                en_cola_revision=(
                    score >= umbral and _revision_pendiente(r.decision)
                ),
                score=float(score),
                umbral_revision=float(umbral),
                eventos=len(evs),
                finalizada_en=r.finalizada_en,
                nota_visible=visible,
                revision_disponible=rev_disp,
                cierre=r.cierre,
                session_id=r.session_id,
                nota_anulada=anulada,
                veredicto="anulado" if anulada else None,
                informe_disponible=anulada,
            )
        )
    return items, len(items)


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


def _revision_pendiente(decision_val: str | None) -> bool:
    """``True`` si la sesion TODAVIA no fue revisada por una persona.

    El import va adentro por la misma razon que en ``_parse_decision_val``: este
    modulo se importa desde varios routers y el enum vive en dominio.
    """
    from app.domain.review.decision import DecisionSesion

    return _parse_decision_val(decision_val) is DecisionSesion.PENDIENTE


def _nombre_completo(nombre: str | None, apellido: str | None) -> str | None:
    """``"Apellido, Nombre"`` para listados. None si no hay ninguno de los dos.

    Formato apellido-primero porque la tabla se lee y se ordena por apellido, que
    es como se busca a una persona en un listado academico. None deja que la UI
    caiga al legajo, que es mejor que una celda vacia.
    """
    nombre = (nombre or "").strip()
    apellido = (apellido or "").strip()
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido or nombre or None
