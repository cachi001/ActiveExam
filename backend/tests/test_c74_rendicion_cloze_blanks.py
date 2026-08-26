"""C-74 Bug C: los blanks cloze deben llegar a la rendición del alumno.

RED → GREEN → TRIANGULATE.

Contexto del bug: `PreguntaRendicion` no tenía campo `blanks`, así que una pregunta
cloze llegaba al front sin huecos y era irresponible (`PreguntaCloze.tsx` espera
`blanks?: BlankRendicion[]`).

D3 (regla dura #6): la respuesta correcta NUNCA viaja al cliente. Para un blank
MULTICHOICE eso significa opciones sin `es_correcta`; para un blank SHORTANSWER
significa NO mandar opciones (las opciones SON las respuestas correctas).
"""

from __future__ import annotations

from app.application.exam_content.taking_service import (
    BlankRendicion,
    OpcionRendicion,
    proyectar_examen,
)
from app.domain.exam_content.entities import (
    BlankCloze,
    ExamenContenido,
    OpcionBlankCloze,
    OpcionRespuesta,
    Pregunta,
)


def _examen_cloze() -> ExamenContenido:
    """Examen con una cloze de dos huecos: un MULTICHOICE y un SHORTANSWER."""
    return ExamenContenido(
        id="exam-cloze",
        titulo="Parcial con cloze",
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="La función {1} devuelve {2}.",
                tipo="cloze",
                orden=0,
                opciones=(),
                blanks=(
                    BlankCloze(
                        id="b1",
                        orden=0,
                        tipo="multichoice",
                        texto_antes="La función ",
                        texto_despues=" devuelve ",
                        opciones=(
                            OpcionBlankCloze(
                                id="ob1", texto="len", es_correcta=True, orden=0
                            ),
                            OpcionBlankCloze(
                                id="ob2", texto="sum", es_correcta=False, orden=1
                            ),
                        ),
                    ),
                    BlankCloze(
                        id="b2",
                        orden=1,
                        tipo="shortanswer",
                        texto_antes=" devuelve ",
                        texto_despues=".",
                        opciones=(
                            OpcionBlankCloze(
                                id="ob3", texto="un entero", es_correcta=True, orden=0
                            ),
                        ),
                    ),
                ),
            ),
        ),
        comision_id=None,
    )


# ---------------------------------------------------------------------------
# RED: los blanks llegan a la proyección
# ---------------------------------------------------------------------------


def test_proyeccion_cloze_incluye_blanks():
    """Bug C: una pregunta cloze proyecta sus huecos en orden."""
    rendicion = proyectar_examen(_examen_cloze())
    pregunta = rendicion.preguntas[0]
    assert len(pregunta.blanks) == 2
    assert [b.id for b in pregunta.blanks] == ["b1", "b2"]
    assert all(isinstance(b, BlankRendicion) for b in pregunta.blanks)


def test_proyeccion_blank_preserva_texto_alrededor():
    """El front arma el texto con texto_antes + control + texto_despues."""
    blank = proyectar_examen(_examen_cloze()).preguntas[0].blanks[0]
    assert blank.tipo == "multichoice"
    assert blank.texto_antes == "La función "
    assert blank.texto_despues == " devuelve "
    assert blank.orden == 0


def test_proyeccion_blank_multichoice_trae_opciones_sin_es_correcta():
    """D3: el blank MULTICHOICE necesita sus opciones, pero sin la correcta marcada."""
    blank = proyectar_examen(_examen_cloze()).preguntas[0].blanks[0]
    assert [o.id for o in blank.opciones] == ["ob1", "ob2"]
    assert all(isinstance(o, OpcionRendicion) for o in blank.opciones)
    for opcion in blank.opciones:
        assert not hasattr(opcion, "es_correcta")


def test_proyeccion_blank_shortanswer_no_expone_opciones():
    """D3: en un SHORTANSWER las opciones SON las respuestas — no viajan al cliente."""
    blank = proyectar_examen(_examen_cloze()).preguntas[0].blanks[1]
    assert blank.tipo == "shortanswer"
    assert blank.opciones == (), "las respuestas de un shortanswer no salen al cliente"


# ---------------------------------------------------------------------------
# TRIANGULATE: casos borde
# ---------------------------------------------------------------------------


def test_proyeccion_multichoice_normal_no_tiene_blanks():
    """Una pregunta multichoice común proyecta blanks vacío, no None."""
    examen = ExamenContenido(
        id="exam-mc",
        titulo="MC",
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="¿2+2?",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(id="o1", texto="4", es_correcta=True, orden=0),
                    OpcionRespuesta(id="o2", texto="3", es_correcta=False, orden=1),
                ),
            ),
        ),
    )
    assert proyectar_examen(examen).preguntas[0].blanks == ()


def test_proyeccion_blanks_ordenados_por_orden():
    """Los blanks se proyectan por `orden` ascendente aunque vengan desordenados."""
    examen = ExamenContenido(
        id="exam-cloze-2",
        titulo="Cloze desordenada",
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="A {1} B {2}",
                tipo="cloze",
                orden=0,
                opciones=(),
                blanks=(
                    BlankCloze(id="b2", orden=1, tipo="shortanswer"),
                    BlankCloze(id="b1", orden=0, tipo="shortanswer"),
                ),
            ),
        ),
    )
    assert [b.id for b in proyectar_examen(examen).preguntas[0].blanks] == ["b1", "b2"]


def test_proyeccion_blank_matching_trae_opciones_sin_es_correcta():
    """C-78: un blank "matching" (emparejamiento) TAMBIÉN elige de una lista
    (el pool de respuestas de la pregunta) — igual que multichoice. Bug real
    encontrado en esta misma tarea: _BLANK_CON_OPCIONES no incluía "matching",
    así que el <select> del alumno llegaba vacío y la pregunta era
    irresponible. D3: las opciones viajan, pero sin es_correcta."""
    examen = ExamenContenido(
        id="exam-matching",
        titulo="Parcial con matching",
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="Une cada lenguaje con su paradigma",
                tipo="cloze",
                orden=0,
                opciones=(),
                blanks=(
                    BlankCloze(
                        id="b1",
                        orden=0,
                        tipo="matching",
                        texto_antes="Python:  ",
                        texto_despues="",
                        opciones=(
                            OpcionBlankCloze(
                                id="ob1", texto="Multiparadigma", es_correcta=True, orden=0
                            ),
                            OpcionBlankCloze(
                                id="ob2", texto="Funcional", es_correcta=False, orden=1
                            ),
                        ),
                    ),
                ),
            ),
        ),
        comision_id=None,
    )

    blank = proyectar_examen(examen).preguntas[0].blanks[0]
    assert blank.tipo == "matching"
    assert [o.id for o in blank.opciones] == ["ob1", "ob2"]
    for opcion in blank.opciones:
        assert not hasattr(opcion, "es_correcta")


def test_proyeccion_cloze_no_seleccionada_no_viaja():
    """Opción B: una cloze del pool no seleccionada no llega a la rendición."""
    base = _examen_cloze()
    pregunta = base.preguntas[0]
    examen = ExamenContenido(
        id=base.id,
        titulo=base.titulo,
        preguntas=(
            Pregunta(
                id=pregunta.id,
                enunciado=pregunta.enunciado,
                tipo=pregunta.tipo,
                orden=pregunta.orden,
                opciones=pregunta.opciones,
                blanks=pregunta.blanks,
                seleccionada=False,
            ),
        ),
    )
    assert proyectar_examen(examen).preguntas == ()
