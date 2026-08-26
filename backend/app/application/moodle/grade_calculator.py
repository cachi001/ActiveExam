"""Servicio de cálculo de nota académica (C-69, tarea 7.1-7.2; C-74, tarea 6.1-6.3).

L2.5: la nota deriva SÓLO de respuestas correctas server-side.
El score/flags de proctoring NO entran en este cálculo (regla dura #5).

D3: es_correcta vive en la DB server-side, NUNCA viaja al cliente.

C-74 §6 (cloze): una pregunta cloze tiene N blanks; su contribución es
(blanks_correctos / blanks_totales) × (1 slot de pregunta). Si respuesta_cloze
está vacío o no tiene clave para un blank, ese blank cuenta como incorrecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import (
    ExamenContenidoModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)

# Escala por defecto si el examen no existe o no tiene nota_maxima configurada
# (migración 0061: escala 0-100, no "sobre 10").
_NOTA_MAXIMA_DEFAULT = 100.0


@dataclass(frozen=True, slots=True)
class RespuestaAlumno:
    """Respuesta del alumno para una pregunta.

    Para preguntas multichoice/truefalse: ``opcion_elegida_id`` contiene el id
    de la opción elegida; ``respuesta_cloze`` es None.

    Para preguntas cloze (C-74 §6): ``respuesta_cloze`` es un dict
    ``{blank_id: opcion_elegida_id}``; ``opcion_elegida_id`` se ignora.
    Un blank ausente del dict o con valor vacío cuenta como incorrecto.
    """

    pregunta_id: str
    opcion_elegida_id: str = ""
    respuesta_cloze: dict[str, str] | None = field(default=None)


async def _preguntas_que_cuentan(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    session_id: str | None,
) -> list[str]:
    """Las preguntas sobre las que se califica este intento.

    c-78 E-07: con sorteo por intento, el set vive en ``pregunta_sesion``. Si el
    intento tiene uno, ESE manda. Si no, se cae a ``seleccionada`` — que cubre los
    exámenes en modo 'fijo', los importados de XML y los intentos anteriores al
    cambio.
    """
    if session_id is not None:
        from app.infrastructure.persistence.models.exam_content import (
            PreguntaSesionModel,
        )

        del_intento = await db.execute(
            select(PreguntaSesionModel.pregunta_id)
            .where(PreguntaSesionModel.session_id == session_id)
            .order_by(PreguntaSesionModel.orden)
        )
        ids = [str(r[0]) for r in del_intento.all()]
        if ids:
            return ids

    seleccionadas = await db.execute(
        select(PreguntaExamenModel.id).where(
            PreguntaExamenModel.examen_id == examen_contenido_id,
            PreguntaExamenModel.seleccionada.is_(True),
        )
    )
    return [str(r) for r in seleccionadas.scalars().all()]


def nota_desde_correctas(
    correctas: float, total_preguntas: int, nota_maxima: float
) -> float:
    """La nota en la escala del examen: (correctas / total) * nota_maxima.

    Funcion PURA, extraida para poder verificarla sin base de datos (c-78, pedido
    del dueno: comprobar que 100/60 y 10/6 dan el mismo veredicto — son la misma
    exigencia en dos escalas).

    DOS decimales, alineado con Moodle: su libreta formatea con 2 decimales, asi
    que redondear a entero de este lado desalineaba las escalas — 15/20 sobre 10
    es 7,5 y se convertia en 8, medio punto regalado que Moodle nunca pidio.

    ROUND_HALF_UP y Decimal a proposito: el round() de Python usa banker's
    rounding (round(0.5) = 0), que en notas se lee como un error.

    Sin preguntas devuelve 0: pasa de verdad (examen en borrador o mal armado) y
    no puede reventar en medio de la entrega del alumno.
    """
    if not total_preguntas:
        return 0.0
    nota = (
        Decimal(str(correctas)) / Decimal(total_preguntas) * Decimal(str(nota_maxima))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(nota)


async def calcular_nota_academica(
    *,
    db: AsyncSession,
    examen_contenido_id: str,
    respuestas: list[RespuestaAlumno],
    session_id: str | None = None,
) -> float:
    """Calcula la nota académica (0..nota_maxima) de un alumno dado su examen.

    Fórmula (idéntica a Moodle): nota = (respuestas_correctas / total_preguntas) *
    nota_maxima, **con dos decimales** y ROUND_HALF_UP (0.5→1,
    6.5→7) — el mismo redondeo que Moodle aplica con "Posiciones decimales = 0".
    NO se redondea a entero: la nota se ESCALA después al `grademax` real del ítem
    destino en Moodle (ver `write_grade`), y redondear antes de escalar perdería
    precisión — un 3 sobre 10 llegaría como 30 sobre 100 en vez de 33,33. El
    aprobado/desaprobado se decide sobre ESTA nota (resultados_query:
    nota >= nota_aprobacion), como en Moodle.

    ``nota_maxima`` se lee server-side desde la config POR EXAMEN
    (examen_contenido.nota_maxima, migración 0032); default 10 si el examen no
    existe. Si el examen no existe, no tiene preguntas, o las respuestas están
    vacías → 0.

    Opción B (pool de preguntas): SOLO cuentan las preguntas seleccionadas por el
    docente (``seleccionada=True``) — tanto el total como las correctas. Una
    respuesta a una pregunta deseleccionada no suma ni al numerador ni al
    denominador.

    c-78 E-07: con ``session_id``, el conjunto que cuenta es el que le tocó a ESE
    intento (``pregunta_sesion``), no el pool del examen. Con sorteo por intento
    cada alumno rinde preguntas distintas, así que usar el pool como denominador
    le daría 10/30 a quien contestó bien sus 10. Si el intento no tiene set
    registrado (examen en modo 'fijo', o un intento anterior al cambio) cae a
    ``seleccionada``, que es el comportamiento de siempre.

    No recibe ni usa score/flags de proctoring — L2.5: el proctoring no altera
    la nota académica de forma automática.
    """
    pregunta_ids = await _preguntas_que_cuentan(
        db, examen_contenido_id=examen_contenido_id, session_id=session_id
    )
    total_preguntas = len(pregunta_ids)

    if total_preguntas == 0 or not respuestas:
        return 0.0

    # Para cada respuesta del alumno, verificar server-side si es_correcta
    # C-74 §6: preguntas cloze contribuyen (blanks_correctos/blanks_totales) × 1 slot.
    correctas: float = 0.0
    # Set y no lista: con sorteo por intento esto se recorre por cada respuesta y
    # el pool puede ser de cientos.
    ids_que_cuentan = set(pregunta_ids)
    for resp in respuestas:
        # Solo verificar respuestas que correspondan a preguntas de ESTE intento.
        # El cliente es un sensor no confiable (regla dura #6): mandar respuestas
        # de preguntas que no le tocaron no puede inflar la nota.
        if str(resp.pregunta_id) not in ids_que_cuentan:
            continue

        if resp.respuesta_cloze is not None:
            # Rama cloze: scoring parcial por blanks
            fraccion = await _calcular_fraccion_cloze(
                db=db,
                pregunta_id=resp.pregunta_id,
                respuesta_cloze=resp.respuesta_cloze,
            )
            correctas += fraccion
        else:
            result = await db.execute(
                select(OpcionRespuestaModel.es_correcta).where(
                    OpcionRespuestaModel.id == resp.opcion_elegida_id,
                    OpcionRespuestaModel.pregunta_id == resp.pregunta_id,
                )
            )
            es_correcta = result.scalar_one_or_none()
            if es_correcta is True:
                correctas += 1.0

    # nota_maxima server-side por examen (default 10 si el examen no existe).
    nota_maxima_row = await db.execute(
        select(ExamenContenidoModel.nota_maxima).where(
            ExamenContenidoModel.id == examen_contenido_id
        )
    )
    nota_maxima = nota_maxima_row.scalar_one_or_none()
    escala = Decimal(str(nota_maxima)) if nota_maxima is not None else Decimal(str(_NOTA_MAXIMA_DEFAULT))

    # DOS decimales, alineado con Moodle: la libreta formatea las notas con 2
    # decimales, asi que redondear a entero de este lado desalineaba las escalas —
    # 15/20 sobre 10 es 7,5 y se convertia en 8, medio punto regalado que Moodle
    # nunca pidio. La conversion a la escala del item destino la hace el cliente
    # (write_grade) leyendo el grademax real.
    #
    # ROUND_HALF_UP y Decimal a proposito: el round() de Python usa banker's
    # rounding (round(0.5) = 0), que en notas se lee como un error.
    return nota_desde_correctas(correctas, total_preguntas, float(escala))


async def _calcular_fraccion_cloze(
    *,
    db: AsyncSession,
    pregunta_id: str,
    respuesta_cloze: dict[str, str],
) -> float:
    """Fracción [0.0, 1.0] de blanks correctos para una pregunta cloze (C-74 §6).

    Cada blank correcto suma 1/N donde N = total de blanks de la pregunta.
    Un blank sin respuesta (clave ausente o valor vacío) cuenta como incorrecto.
    Si la pregunta no tiene blanks registrados en DB → fracción 0 (no suma nada).
    """
    # Leer todos los blanks de la pregunta
    blanks_result = await db.execute(
        select(PreguntaClozeBlankModel.id, PreguntaClozeBlankModel.tipo).where(
            PreguntaClozeBlankModel.pregunta_id == pregunta_id
        )
    )
    blanks = blanks_result.all()
    total_blanks = len(blanks)
    if total_blanks == 0:
        return 0.0

    blancos_correctos = 0
    for blank_id, tipo in blanks:
        respuesta = respuesta_cloze.get(blank_id, "")
        if not respuesta:
            # Blank sin respuesta → incorrecto
            continue
        if await _blank_acertado(
            db=db, blank_id=blank_id, tipo=tipo, respuesta=respuesta
        ):
            blancos_correctos += 1

    return blancos_correctos / total_blanks


# En un blank MULTICHOICE el alumno elige de una lista y manda el id de la opción.
# En SHORTANSWER/NUMERICAL escribe libre y manda TEXTO: ahí las opciones de la DB
# son las respuestas ACEPTADAS y hay que comparar contra su texto, no contra su id.
# "matching" (C-78, emparejamiento) también elige de una lista (el pool de
# respuestas de la pregunta) — mismo criterio que multichoice, por id.
_BLANK_ELIGE_OPCION = ("multichoice", "multichoice_nocase", "multiresponse", "matching")


async def _blank_acertado(
    *, db: AsyncSession, blank_id: str, tipo: str, respuesta: str
) -> bool:
    """Si la respuesta del alumno acierta ese blank."""
    if (tipo or "").lower() in _BLANK_ELIGE_OPCION:
        correcta_result = await db.execute(
            select(OpcionClozeBlancoModel.es_correcta).where(
                OpcionClozeBlancoModel.id == respuesta,
                OpcionClozeBlancoModel.blank_id == blank_id,
            )
        )
        return correcta_result.scalar_one_or_none() is True

    # Texto libre: como Moodle, se ignoran mayúsculas y espacios de los bordes.
    aceptadas_result = await db.execute(
        select(OpcionClozeBlancoModel.texto).where(
            OpcionClozeBlancoModel.blank_id == blank_id,
            OpcionClozeBlancoModel.es_correcta.is_(True),
        )
    )
    aceptadas = {(t or "").strip().casefold() for t in aceptadas_result.scalars().all()}
    return respuesta.strip().casefold() in aceptadas
