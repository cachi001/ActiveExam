"""1.1 RED → 1.2 GREEN: tests de dominio — ExamenContenido, Pregunta, OpcionRespuesta.

Corren SIN base de datos. Solo validan las reglas de dominio de las entidades.
"""

from __future__ import annotations

import pytest

from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.domain.exam_content.errors import PreguntaInvalidaError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opcion(texto: str, correcta: bool, orden: int = 0) -> OpcionRespuesta:
    return OpcionRespuesta(texto=texto, es_correcta=correcta, orden=orden)


def _mc_valida() -> Pregunta:
    return Pregunta(
        enunciado="¿Capital de Francia?",
        tipo="multichoice",
        opciones=(
            _opcion("París", True),
            _opcion("Madrid", False),
            _opcion("Roma", False),
        ),
    )


def _tf_valida() -> Pregunta:
    return Pregunta(
        enunciado="El Sol es una estrella.",
        tipo="truefalse",
        opciones=(
            _opcion("Verdadero", True),
            _opcion("Falso", False),
        ),
    )


# ---------------------------------------------------------------------------
# 1.1 RED — casos de error
# ---------------------------------------------------------------------------

def test_multichoice_sin_opcion_correcta_es_rechazada():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="multichoice",
            opciones=(_opcion("A", False), _opcion("B", False)),
        )


def test_multichoice_con_mas_de_una_correcta_es_rechazada():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="multichoice",
            opciones=(_opcion("A", True), _opcion("B", True)),
        )


def test_multichoice_menos_de_dos_opciones_es_rechazada():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="multichoice",
            opciones=(_opcion("A", True),),
        )


def test_truefalse_exige_exactamente_dos_opciones():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="truefalse",
            opciones=(_opcion("Verdadero", True),),
        )


def test_truefalse_con_tres_opciones_es_rechazada():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="truefalse",
            opciones=(
                _opcion("Verdadero", True),
                _opcion("Falso", False),
                _opcion("Tal vez", False),
            ),
        )


def test_truefalse_sin_correcta_es_rechazada():
    with pytest.raises(PreguntaInvalidaError):
        Pregunta(
            enunciado="Q",
            tipo="truefalse",
            opciones=(_opcion("Verdadero", False), _opcion("Falso", False)),
        )


# ---------------------------------------------------------------------------
# 1.1 RED — casos válidos
# ---------------------------------------------------------------------------

def test_pregunta_valida_multichoice_no_lanza():
    p = _mc_valida()
    assert len(p.opciones) == 3
    assert sum(1 for o in p.opciones if o.es_correcta) == 1


def test_pregunta_valida_truefalse_no_lanza():
    p = _tf_valida()
    assert len(p.opciones) == 2
    assert sum(1 for o in p.opciones if o.es_correcta) == 1


def test_examen_contenido_sin_comision_es_valido():
    """D11: comision_id NULLABLE, un examen sin comisión es válido."""
    examen = ExamenContenido(
        titulo="Parcial Algebra",
        preguntas=(_mc_valida(),),
        comision_id=None,
    )
    assert examen.comision_id is None
    assert examen.titulo == "Parcial Algebra"


def test_examen_contenido_id_opcional():
    """El id es None cuando aún no fue persistido."""
    examen = ExamenContenido(titulo="X", preguntas=(_mc_valida(),))
    assert examen.id is None


# ---------------------------------------------------------------------------
# TRIANGULATE — casos adicionales para asegurar la generalización
# ---------------------------------------------------------------------------

def test_multichoice_con_cuatro_opciones_exactamente_una_correcta():
    p = Pregunta(
        enunciado="¿Cuál?",
        tipo="multichoice",
        opciones=(
            _opcion("A", True, 0),
            _opcion("B", False, 1),
            _opcion("C", False, 2),
            _opcion("D", False, 3),
        ),
    )
    assert len(p.opciones) == 4


def test_opcion_respuesta_inmutable():
    """dataclass(frozen=True) — no se puede mutar."""
    o = _opcion("X", True)
    with pytest.raises((AttributeError, TypeError)):
        o.texto = "Y"  # type: ignore[misc]


def test_pregunta_inmutable():
    p = _mc_valida()
    with pytest.raises((AttributeError, TypeError)):
        p.enunciado = "otro"  # type: ignore[misc]
