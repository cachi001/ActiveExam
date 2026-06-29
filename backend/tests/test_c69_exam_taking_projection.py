"""3.1 RED -> 3.2 GREEN -> 3.5 TRIANGULATE: tests de proyección de rendición (D3).

Tests unitarios (sin DB): verifican que la proyección excluye es_correcta (D3)
y que el orden es determinístico.
"""

from __future__ import annotations

from app.application.exam_content.taking_service import (
    ExamenRendicion,
    OpcionRendicion,
    PreguntaRendicion,
    proyectar_examen,
)
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta


def _examen_multichoice_truefalse() -> ExamenContenido:
    """Examen de prueba con multichoice y truefalse."""
    return ExamenContenido(
        id="exam-001",
        titulo="Parcial Álgebra",
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="¿Capital de Francia?",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(id="o1", texto="París", es_correcta=True, orden=0),
                    OpcionRespuesta(id="o2", texto="Madrid", es_correcta=False, orden=1),
                    OpcionRespuesta(id="o3", texto="Roma", es_correcta=False, orden=2),
                ),
            ),
            Pregunta(
                id="p2",
                enunciado="El Sol es una estrella.",
                tipo="truefalse",
                orden=1,
                opciones=(
                    OpcionRespuesta(id="o4", texto="Verdadero", es_correcta=True, orden=0),
                    OpcionRespuesta(id="o5", texto="Falso", es_correcta=False, orden=1),
                ),
            ),
        ),
        comision_id=None,
    )


# ---------------------------------------------------------------------------
# 3.1 RED: la proyección NO incluye es_correcta
# ---------------------------------------------------------------------------


def test_proyeccion_no_incluye_es_correcta():
    """D3: ninguna OpcionRendicion tiene el atributo es_correcta."""
    examen = _examen_multichoice_truefalse()
    rendicion = proyectar_examen(examen)

    for pregunta in rendicion.preguntas:
        for opcion in pregunta.opciones:
            assert not hasattr(opcion, "es_correcta"), (
                f"OpcionRendicion no debe tener es_correcta. Opción: {opcion}"
            )


def test_proyeccion_opcion_es_instancia_de_opcion_rendicion():
    """Cada opción proyectada es OpcionRendicion (tipo correcto, sin es_correcta)."""
    examen = _examen_multichoice_truefalse()
    rendicion = proyectar_examen(examen)
    for pregunta in rendicion.preguntas:
        for opcion in pregunta.opciones:
            assert isinstance(opcion, OpcionRendicion)


def test_proyeccion_preserva_texto_y_orden_de_opciones():
    """Los campos texto y orden se preservan correctamente en la proyección."""
    examen = _examen_multichoice_truefalse()
    rendicion = proyectar_examen(examen)
    mc = rendicion.preguntas[0]
    assert mc.opciones[0].texto == "París"
    assert mc.opciones[0].orden == 0
    assert mc.opciones[1].texto == "Madrid"
    assert mc.opciones[1].orden == 1


def test_proyeccion_contiene_id_y_titulo_del_examen():
    """La proyección preserva id y titulo del examen."""
    examen = _examen_multichoice_truefalse()
    rendicion = proyectar_examen(examen)
    assert isinstance(rendicion, ExamenRendicion)
    assert rendicion.id == "exam-001"
    assert rendicion.titulo == "Parcial Álgebra"
    assert len(rendicion.preguntas) == 2


def test_proyeccion_pregunta_es_tipo_correcto():
    """Cada pregunta proyectada es PreguntaRendicion."""
    examen = _examen_multichoice_truefalse()
    rendicion = proyectar_examen(examen)
    for p in rendicion.preguntas:
        assert isinstance(p, PreguntaRendicion)


# ---------------------------------------------------------------------------
# 3.5 TRIANGULATE: orden determinístico y aislamiento
# ---------------------------------------------------------------------------


def test_proyeccion_orden_determinístico():
    """Dos proyecciones del mismo examen tienen el mismo orden de preguntas/opciones."""
    examen = _examen_multichoice_truefalse()
    r1 = proyectar_examen(examen)
    r2 = proyectar_examen(examen)
    assert [p.id for p in r1.preguntas] == [p.id for p in r2.preguntas]
    for p1, p2 in zip(r1.preguntas, r2.preguntas):
        assert [o.id for o in p1.opciones] == [o.id for o in p2.opciones]


# ---------------------------------------------------------------------------
# Opción B (pool de preguntas): la rendición proyecta SOLO las seleccionadas
# ---------------------------------------------------------------------------


def _examen_pool(seleccion: tuple[bool, bool, bool]) -> ExamenContenido:
    """Examen de 3 preguntas con la marca seleccionada según `seleccion`."""
    return ExamenContenido(
        id="exam-pool",
        titulo="Pool",
        preguntas=tuple(
            Pregunta(
                id=f"p{i}",
                enunciado=f"Pregunta {i}",
                tipo="multichoice",
                orden=i,
                seleccionada=sel,
                opciones=(
                    OpcionRespuesta(id=f"o{i}a", texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(id=f"o{i}b", texto="B", es_correcta=False, orden=1),
                ),
            )
            for i, sel in enumerate(seleccion)
        ),
        comision_id=None,
    )


def test_proyeccion_solo_incluye_preguntas_seleccionadas():
    """Opción B: una pregunta con seleccionada=False NO viaja a la rendición."""
    examen = _examen_pool((True, False, True))
    rendicion = proyectar_examen(examen)
    ids = [p.id for p in rendicion.preguntas]
    assert ids == ["p0", "p2"], "solo las seleccionadas se proyectan, en orden"


def test_proyeccion_todas_seleccionadas_devuelve_todas():
    """Triangulación: si todas están seleccionadas, se proyectan las 3."""
    examen = _examen_pool((True, True, True))
    rendicion = proyectar_examen(examen)
    assert [p.id for p in rendicion.preguntas] == ["p0", "p1", "p2"]


def test_proyeccion_ninguna_seleccionada_devuelve_vacio():
    """Triangulación borde: ninguna seleccionada → rendición sin preguntas."""
    examen = _examen_pool((False, False, False))
    rendicion = proyectar_examen(examen)
    assert rendicion.preguntas == ()


def test_proyeccion_aislamiento_examenes_distintos_no_se_mezclan():
    """Proyecciones de exámenes distintos son independientes."""
    examen_a = ExamenContenido(
        id="exam-A",
        titulo="Examen A",
        preguntas=(
            Pregunta(
                id="pA1",
                enunciado="¿Cuánto es 2+2?",
                tipo="multichoice",
                orden=0,
                opciones=(
                    OpcionRespuesta(id="oA1", texto="4", es_correcta=True, orden=0),
                    OpcionRespuesta(id="oA2", texto="3", es_correcta=False, orden=1),
                ),
            ),
        ),
    )
    examen_b = ExamenContenido(
        id="exam-B",
        titulo="Examen B",
        preguntas=(
            Pregunta(
                id="pB1",
                enunciado="¿El agua hierve a 100°C?",
                tipo="truefalse",
                orden=0,
                opciones=(
                    OpcionRespuesta(id="oB1", texto="Verdadero", es_correcta=True, orden=0),
                    OpcionRespuesta(id="oB2", texto="Falso", es_correcta=False, orden=1),
                ),
            ),
        ),
    )
    rA = proyectar_examen(examen_a)
    rB = proyectar_examen(examen_b)
    assert rA.id == "exam-A"
    assert rB.id == "exam-B"
    # Las opciones de A y B son disjuntas
    opciones_a = {o.id for p in rA.preguntas for o in p.opciones}
    opciones_b = {o.id for p in rB.preguntas for o in p.opciones}
    assert opciones_a.isdisjoint(opciones_b), (
        "Las proyecciones de exámenes distintos no deben compartir opciones."
    )
