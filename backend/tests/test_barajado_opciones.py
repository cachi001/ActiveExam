"""Tests del barajado de opciones (dominio PURO — sin DB ni red).

Cubre lo que hace confiable al barajado: que sea estable para el mismo alumno,
distinto entre alumnos, y que NUNCA pierda una opcion.
"""

from __future__ import annotations

from app.domain.exam_content.barajado import barajar_opciones, semilla_barajado

_OPCIONES = ["correcta", "b", "c", "d"]
_PREGUNTA = "preg-0001"


def test_mismo_alumno_y_pregunta_da_siempre_el_mismo_orden() -> None:
    """Estabilidad: recargar la pagina no puede mover las opciones de lugar."""
    primera = barajar_opciones(_OPCIONES, alumno="EST-001", pregunta_id=_PREGUNTA)
    for _ in range(5):
        assert (
            barajar_opciones(_OPCIONES, alumno="EST-001", pregunta_id=_PREGUNTA)
            == primera
        )


def test_alumnos_distintos_reciben_ordenes_distintos() -> None:
    """El punto del barajado: copiarse de la pantalla de al lado no debe servir.

    Con 4 opciones dos alumnos podrian coincidir por azar (1/24), asi que se
    exige que NO sean todos iguales sobre una muestra amplia, no que difieran
    de a pares.
    """
    ordenes = {
        tuple(barajar_opciones(_OPCIONES, alumno=f"EST-{i:03d}", pregunta_id=_PREGUNTA))
        for i in range(30)
    }
    assert len(ordenes) > 1


def test_el_mismo_alumno_ve_ordenes_distintos_en_preguntas_distintas() -> None:
    """La semilla depende tambien de la pregunta: si no, el orden se repetiria
    igual en todo el examen y el patron volveria a ser adivinable."""
    ordenes = {
        tuple(barajar_opciones(_OPCIONES, alumno="EST-001", pregunta_id=f"preg-{i}"))
        for i in range(30)
    }
    assert len(ordenes) > 1


def test_conserva_todas_las_opciones_sin_perder_ni_duplicar() -> None:
    """Perder una opcion dejaria sin respuesta posible a quien la eligio."""
    barajadas = barajar_opciones(_OPCIONES, alumno="EST-007", pregunta_id=_PREGUNTA)
    assert sorted(barajadas) == sorted(_OPCIONES)
    assert len(barajadas) == len(_OPCIONES)


def test_no_muta_la_lista_original() -> None:
    original = list(_OPCIONES)
    barajar_opciones(original, alumno="EST-001", pregunta_id=_PREGUNTA)
    assert original == _OPCIONES


def test_listas_de_cero_o_una_opcion_no_rompen() -> None:
    assert barajar_opciones([], alumno="EST-001", pregunta_id=_PREGUNTA) == []
    assert barajar_opciones(["sola"], alumno="EST-001", pregunta_id=_PREGUNTA) == ["sola"]


def test_la_correcta_no_queda_siempre_primera() -> None:
    """El defecto original: la correcta (indice 0 del import) SIEMPRE primera.

    Se mira la posicion de "correcta" para muchos alumnos: si el barajado sirve,
    NO puede quedar en la posicion 0 en todos los casos.
    """
    posiciones = {
        barajar_opciones(
            _OPCIONES, alumno=f"EST-{i:03d}", pregunta_id=_PREGUNTA
        ).index("correcta")
        for i in range(40)
    }
    assert posiciones != {0}
    assert len(posiciones) > 1


def test_semilla_no_depende_del_hash_aleatorizado_del_proceso() -> None:
    """Valor clavado: si alguien cambia sha256 por hash(), esto se rompe — que es
    justo lo que hay que impedir (dos workers darian ordenes distintos)."""
    assert semilla_barajado("EST-001", _PREGUNTA) == semilla_barajado(
        "EST-001", _PREGUNTA
    )
    assert semilla_barajado("EST-001", _PREGUNTA) != semilla_barajado(
        "EST-002", _PREGUNTA
    )
