"""Revisión post-examen del alumno (C-69, student-facing).

Devuelve, para el intento YA FINALIZADO del alumno, cada pregunta con TODAS sus
opciones marcando cuál es la correcta y cuál eligió el alumno, más los contadores
(correctas/incorrectas/sin responder) y la nota persistida.

EXCEPCIÓN a D3 (documentada): ``es_correcta`` normalmente NUNCA viaja al cliente
(el cliente es sensor no confiable durante la rendición). Acá SÍ se expone, pero
SOLO:
  - al DUEÑO del intento (la query filtra por alumno_idnumber/email del JWT), y
  - con el intento YA FINALIZADO (finalizada_en no nulo).
Es el mismo criterio que las "Review options" de Moodle: terminado el examen, el
alumno puede ver la corrección. No hay riesgo de copia porque el intento ya cerró.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exam_content.resultado_nota import resultado_de
from app.domain.exam_content.visibilidad import nota_visible, revision_visible
from app.infrastructure.persistence.models.exam_content import (
    ExamenContenidoModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
    RespuestaAlumnoClozeModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


@dataclass(frozen=True, slots=True)
class RevisionOpcion:
    """Una opción en la revisión: si es la correcta y si el alumno la eligió."""

    id: str
    texto: str
    orden: int
    es_correcta: bool
    elegida: bool


@dataclass(frozen=True, slots=True)
class RevisionBlank:
    """Un blank (hueco) de una pregunta cloze en la revisión."""

    blank_id: str
    orden: int
    tipo: str
    texto_antes: str | None
    texto_despues: str | None
    respuesta_alumno: str | None  # texto de lo que respondió (texto de opción o texto libre)
    es_correcta: bool


@dataclass(frozen=True, slots=True)
class RevisionPregunta:
    """Una pregunta en la revisión con su corrección."""

    id: str
    enunciado: str
    orden: int
    opciones: tuple[RevisionOpcion, ...]
    respondida: bool
    acertada: bool
    tipo: str = "multichoice"
    blanks_revisados: tuple["RevisionBlank", ...] = ()


@dataclass(frozen=True, slots=True)
class RevisionExamen:
    """Revisión completa del intento finalizado del alumno."""

    examen_id: str
    titulo: str
    nota: float | None
    nota_maxima: float | None
    aprobado: bool
    total_preguntas: int
    correctas: int
    incorrectas: int
    sin_responder: int
    finalizada_en: object | None  # datetime tz-aware (lo serializa Pydantic)
    preguntas: tuple[RevisionPregunta, ...]
    # Visibilidad (C-69, dos niveles):
    #  - disponible: si la NOTA es visible → se muestran los contadores.
    #  - revision_disponible: si la CORRECCIÓN (preguntas + es_correcta) es visible.
    # Si disponible=False, todo viene en cero/vacío. Si disponible=True pero
    # revision_disponible=False, van los contadores pero preguntas=() (sin filtrar).
    disponible: bool = True
    revision_disponible: bool = True
    cierre: object | None = None  # datetime tz-aware o None
    #: El resultado resuelto por el backend (`ResultadoNota`). La pantalla sólo
    #: lo muestra: con el texto escrito a mano allá, decía "Aprobado" sobre una
    #: nota que el docente ya veía como "Anulada".
    resultado: str = ""


async def obtener_revision(
    *,
    db: AsyncSession,
    examen_contenido_id: str,
    alumno_idnumber: str,
    alumno_email: str,
) -> RevisionExamen | None:
    """Revisión del intento FINALIZADO más reciente del alumno para el examen.

    Devuelve None si:
      - no hay identidad utilizable (sin idnumber ni email), o
      - el alumno no tiene ninguna sesión finalizada para ese examen (el propio
        filtro por dueño hace de guarda de ownership: un alumno solo ve lo suyo).
    """
    conds = []
    if alumno_idnumber:
        conds.append(ProctoringSessionModel.alumno_idnumber == alumno_idnumber)
    if alumno_email:
        conds.append(ProctoringSessionModel.alumno_email == alumno_email)
    if not conds:
        return None

    # Sesión finalizada más reciente del alumno para ESTE examen (ownership + finalizado).
    sesion = (
        await db.execute(
            select(ProctoringSessionModel.id, ProctoringSessionModel.finalizada_en)
            .where(
                ProctoringSessionModel.examen_contenido_id == examen_contenido_id,
                ProctoringSessionModel.finalizada_en.isnot(None),
                or_(*conds),
            )
            .order_by(
                ProctoringSessionModel.finalizada_en.desc(),
                ProctoringSessionModel.id,
            )
            .limit(1)
        )
    ).first()
    if sesion is None:
        return None
    session_id = sesion.id

    examen = (
        await db.execute(
            select(
                ExamenContenidoModel.titulo,
                ExamenContenidoModel.nota_maxima,
                ExamenContenidoModel.nota_aprobacion,
                ExamenContenidoModel.cierre,
                ExamenContenidoModel.mostrar_nota,
                ExamenContenidoModel.revision_habilitada,
            ).where(ExamenContenidoModel.id == examen_contenido_id)
        )
    ).first()
    if examen is None:
        return None

    # Gate de visibilidad (C-69), dos niveles:
    #  - nvis (nota visible): si false, nada de resultados (bloqueo total).
    #  - rvis (revisión visible): si false pero nvis true, van los contadores pero
    #    NO las preguntas (no se filtran las respuestas correctas).
    ahora = datetime.now(tz=timezone.utc)
    nvis = nota_visible(
        mostrar_nota=examen.mostrar_nota, cierre=examen.cierre, ahora=ahora
    )
    rvis = revision_visible(
        revision_habilitada=examen.revision_habilitada,
        mostrar_nota=examen.mostrar_nota,
        cierre=examen.cierre,
        ahora=ahora,
    )
    if not nvis:
        return RevisionExamen(
            examen_id=examen_contenido_id,
            titulo=examen.titulo or "",
            nota=None,
            nota_maxima=float(examen.nota_maxima) if examen.nota_maxima is not None else None,
            aprobado=False,
            resultado="",
            total_preguntas=0,
            correctas=0,
            incorrectas=0,
            sin_responder=0,
            finalizada_en=sesion.finalizada_en,
            preguntas=(),
            disponible=False,
            revision_disponible=False,
            cierre=examen.cierre,
        )

    # Preguntas SELECCIONADAS (opción B) en orden.
    preg_rows = list(
        (
            await db.execute(
                select(PreguntaExamenModel)
                .where(
                    PreguntaExamenModel.examen_id == examen_contenido_id,
                    PreguntaExamenModel.seleccionada.is_(True),
                )
                .order_by(PreguntaExamenModel.orden)
            )
        )
        .scalars()
        .all()
    )
    pregunta_ids = [p.id for p in preg_rows]

    opciones_por_pregunta: dict[str, list[OpcionRespuestaModel]] = {}
    if pregunta_ids:
        opt_rows = (
            (
                await db.execute(
                    select(OpcionRespuestaModel)
                    .where(OpcionRespuestaModel.pregunta_id.in_(pregunta_ids))
                    .order_by(OpcionRespuestaModel.orden)
                )
            )
            .scalars()
            .all()
        )
        for o in opt_rows:
            opciones_por_pregunta.setdefault(o.pregunta_id, []).append(o)

    # Respuestas del alumno en ESTA sesión.
    resp_rows = (
        await db.execute(
            select(
                RespuestaAlumnoModel.pregunta_id,
                RespuestaAlumnoModel.opcion_elegida_id,
            ).where(RespuestaAlumnoModel.session_id == session_id)
        )
    ).all()
    elegida_por_pregunta = {r.pregunta_id: r.opcion_elegida_id for r in resp_rows}

    # Respuestas cloze del alumno en ESTA sesión: viven en su propia tabla
    # (respuesta_alumno_cloze, una fila por blank), NO como JSON embebido en
    # respuesta_alumno.opcion_elegida_id — ese esquema quedó obsoleto cuando
    # se separó la tabla dedicada para cloze/ddwtos (ver RespuestaAlumnoClozeModel).
    resp_cloze_rows = (
        await db.execute(
            select(
                RespuestaAlumnoClozeModel.pregunta_id,
                RespuestaAlumnoClozeModel.blank_id,
                RespuestaAlumnoClozeModel.valor,
            ).where(RespuestaAlumnoClozeModel.session_id == session_id)
        )
    ).all()
    respuestas_cloze_por_pregunta: dict[str, dict[str, str]] = {}
    for r in resp_cloze_rows:
        respuestas_cloze_por_pregunta.setdefault(r.pregunta_id, {})[r.blank_id] = r.valor

    # Cargar blanks cloze para las preguntas de tipo 'cloze'.
    cloze_pregunta_ids = [p.id for p in preg_rows if p.tipo == "cloze"]
    blanks_por_pregunta: dict[str, list[PreguntaClozeBlankModel]] = {}
    opciones_cloze_por_blank: dict[str, list[OpcionClozeBlancoModel]] = {}
    if cloze_pregunta_ids:
        blank_rows = (
            await db.execute(
                select(PreguntaClozeBlankModel)
                .where(PreguntaClozeBlankModel.pregunta_id.in_(cloze_pregunta_ids))
                .order_by(PreguntaClozeBlankModel.orden)
            )
        ).scalars().all()
        for b in blank_rows:
            blanks_por_pregunta.setdefault(b.pregunta_id, []).append(b)
        blank_ids_all = [b.id for b in blank_rows]
        if blank_ids_all:
            opt_cloze_rows = (
                await db.execute(
                    select(OpcionClozeBlancoModel)
                    .where(OpcionClozeBlancoModel.blank_id.in_(blank_ids_all))
                )
            ).scalars().all()
            for oc in opt_cloze_rows:
                opciones_cloze_por_blank.setdefault(oc.blank_id, []).append(oc)

    preguntas: list[RevisionPregunta] = []
    correctas = 0
    sin_responder = 0
    for p in preg_rows:
        elegida_id = elegida_por_pregunta.get(p.id)

        if p.tipo == "cloze":
            respuesta_cloze = respuestas_cloze_por_pregunta.get(p.id, {})

            blanks_revisados: list[RevisionBlank] = []
            todos_correctos = True
            alguno_respondido = False
            for blank in blanks_por_pregunta.get(p.id, []):
                valor = respuesta_cloze.get(blank.id, "")
                if valor:
                    alguno_respondido = True
                respuesta_alumno_texto: str | None = None
                blank_correcto = False
                if blank.tipo in ("multichoice", "matching"):
                    # valor = UUID de la OpcionClozeBlancoModel elegida. "matching"
                    # (C-78) resuelve por id igual que multichoice — ver
                    # grade_calculator._BLANK_ELIGE_OPCION (misma decisión, dos
                    # lugares: esta query re-implementa el cálculo para mostrarlo).
                    opciones_blank = opciones_cloze_por_blank.get(blank.id, [])
                    elegida_opcion = next((oc for oc in opciones_blank if oc.id == valor), None)
                    if elegida_opcion is not None:
                        respuesta_alumno_texto = elegida_opcion.texto
                        blank_correcto = bool(elegida_opcion.es_correcta)
                    else:
                        todos_correctos = False
                else:
                    # shortanswer: comparar texto case-insensitive contra correctas
                    respuesta_alumno_texto = valor if valor else None
                    opciones_blank = opciones_cloze_por_blank.get(blank.id, [])
                    correctas_blank = [oc.texto for oc in opciones_blank if oc.es_correcta]
                    if valor and any(valor.strip().lower() == c.strip().lower() for c in correctas_blank):
                        blank_correcto = True
                    elif valor:
                        todos_correctos = False
                    else:
                        todos_correctos = False
                if not valor:
                    todos_correctos = False
                blanks_revisados.append(
                    RevisionBlank(
                        blank_id=blank.id,
                        orden=blank.orden,
                        tipo=blank.tipo,
                        texto_antes=blank.texto_antes,
                        texto_despues=blank.texto_despues,
                        respuesta_alumno=respuesta_alumno_texto,
                        es_correcta=blank_correcto,
                    )
                )

            respondida = alguno_respondido
            acertada = bool(blanks_revisados) and todos_correctos
            if not respondida:
                sin_responder += 1
            if acertada:
                correctas += 1
            preguntas.append(
                RevisionPregunta(
                    id=p.id or "",
                    enunciado=p.enunciado,
                    orden=p.orden,
                    opciones=(),
                    respondida=respondida,
                    acertada=acertada,
                    tipo="cloze",
                    blanks_revisados=tuple(blanks_revisados),
                )
            )
        else:
            opciones: list[RevisionOpcion] = []
            acertada = False
            for o in opciones_por_pregunta.get(p.id, []):
                elegida = o.id == elegida_id
                if elegida and o.es_correcta:
                    acertada = True
                opciones.append(
                    RevisionOpcion(
                        id=o.id or "",
                        texto=o.texto,
                        orden=o.orden,
                        es_correcta=bool(o.es_correcta),
                        elegida=elegida,
                    )
                )
            respondida = elegida_id is not None
            if not respondida:
                sin_responder += 1
            if acertada:
                correctas += 1
            preguntas.append(
                RevisionPregunta(
                    id=p.id or "",
                    enunciado=p.enunciado,
                    orden=p.orden,
                    opciones=tuple(opciones),
                    respondida=respondida,
                    acertada=acertada,
                    tipo=p.tipo,
                )
            )

    total = len(preg_rows)
    incorrectas = total - correctas - sin_responder

    # Nota persistida (la MISMA que ve el alumno en "Mis notas"/cierre). Si no hay
    # write-back todavía, nota=None (no re-calculamos acá para no divergir).
    nota_val = (
        await db.execute(
            select(MoodleWritebackEstadoModel.nota).where(
                MoodleWritebackEstadoModel.session_id == session_id
            )
        )
    ).scalar_one_or_none()
    nota = float(nota_val) if nota_val is not None else None
    nota_aprobacion = (
        float(examen.nota_aprobacion) if examen.nota_aprobacion is not None else None
    )
    aprobado = nota is not None and nota_aprobacion is not None and nota >= nota_aprobacion

    # La NOTA es visible acá (nvis). El detalle pregunta-por-pregunta (con es_correcta)
    # solo va si la revisión está habilitada y visible (rvis); si no, contadores sí,
    # preguntas no (no se filtran las respuestas correctas).
    return RevisionExamen(
        examen_id=examen_contenido_id,
        titulo=examen.titulo or "",
        nota=nota,
        nota_maxima=float(examen.nota_maxima) if examen.nota_maxima is not None else None,
        aprobado=aprobado,
        resultado=resultado_de(
            aprobado=aprobado, nota=nota, retenido_por=None
        ).value,
        total_preguntas=total,
        correctas=correctas,
        incorrectas=incorrectas,
        sin_responder=sin_responder,
        finalizada_en=sesion.finalizada_en,
        preguntas=tuple(preguntas) if rvis else (),
        disponible=True,
        revision_disponible=rvis,
        cierre=examen.cierre,
    )
