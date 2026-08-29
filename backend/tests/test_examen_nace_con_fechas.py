"""Un examen no puede nacer sin ventana de rendición.

## El defecto

`POST /exam-content/crear-desde-banco` es la única vía que crea un examen de
cero, y no aceptaba `apertura` ni `cierre`: el examen nacía con las dos en NULL.

El editor de configuración SÍ las exige ("La fecha de inicio y de cierre son
obligatorias", C-69), pero esa validación solo corre si alguien abre esa pantalla
y guarda. Un examen recién creado se publicaba sin fechas, y al alumno le
aparecía «Sin fecha de cierre» — un examen sin principio ni fin.

Verificado el 29/8/2026 en desarrollo: los 6 exámenes de la base tenían
`apertura` y `cierre` en NULL.

## La decisión

Decisión del dueño: son campos obligatorios, o con una fecha por defecto. Se
implementan las dos mitades, cada una donde corresponde:

- El **modal** las pide y las llega prellenadas, así completarlas es un clic.
- El **backend** las DEFAULTEA si el body no las trae (apertura = ahora,
  cierre = una semana después). Así ningún examen nace sin ventana, venga de
  donde venga la llamada, sin romper a los clientes que hoy no las mandan.

Distinto de `moodle_courseid`/`moodle_cmid`, que siguen siendo opcionales a
propósito: un examen puede cargarse a mano y no sincronizarse nunca con el campus.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.presentation.api.v1.exam_content.schemas import CrearDesdebancoRequest

_BASE = {
    "titulo": "Parcial",
    "materia_id": "m-1",
    "sorteo": [{"categoria_id": None, "cantidad": 1}],
}


def _req(**extra) -> CrearDesdebancoRequest:
    return CrearDesdebancoRequest(**{**_BASE, **extra})


def test_sin_fechas_el_examen_igual_nace_con_ventana():
    """El default evita que exista un examen sin principio ni fin."""
    req = _req()
    assert req.apertura is not None
    assert req.cierre is not None


def test_la_apertura_por_defecto_es_ahora():
    ahora = datetime.now(timezone.utc)
    req = _req()
    assert abs((req.apertura - ahora).total_seconds()) < 60


def test_el_cierre_por_defecto_deja_una_semana():
    req = _req()
    assert timedelta(days=6) < (req.cierre - req.apertura) < timedelta(days=8)


def test_respeta_las_fechas_que_manda_quien_crea():
    """El default es una red, no una imposición: si vienen, mandan las del body."""
    apertura = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    cierre = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
    req = _req(apertura=apertura, cierre=cierre)
    assert req.apertura == apertura
    assert req.cierre == cierre


def test_rechaza_un_cierre_anterior_a_la_apertura():
    """Una ventana invertida deja el examen imposible de rendir desde el minuto
    cero, y el error recién aparecería cuando un alumno intenta entrar."""
    with pytest.raises(ValueError, match="apertura"):
        _req(
            apertura=datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc),
            cierre=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
        )


def test_rechaza_apertura_y_cierre_iguales():
    """Ventana de duración cero: nadie llega a rendir."""
    momento = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="apertura"):
        _req(apertura=momento, cierre=momento)


def test_solo_una_de_las_dos_no_deja_media_ventana():
    """Con apertura y sin cierre, la otra se completa igual: media ventana es
    justo el estado que este cambio viene a eliminar."""
    apertura = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    req = _req(apertura=apertura)
    assert req.cierre is not None
    assert req.cierre > apertura


def test_el_destino_de_moodle_sigue_siendo_opcional():
    """Un examen puede cargarse a mano y no sincronizarse nunca con el campus.

    Está acá a propósito: es el contraste que fija la decisión del dueño — las
    fechas son obligatorias, el destino de Moodle no.
    """
    from app.presentation.api.v1.exam_content.schemas import MoodleTargetRequest

    vacio = MoodleTargetRequest()
    assert vacio.moodle_courseid is None
    assert vacio.moodle_cmid is None


# ---------------------------------------------------------------------------
# Tiempo límite: un examen tampoco puede nacer sin reloj
# ---------------------------------------------------------------------------
#
# `deadline_efectivo` resuelve un examen SIN `tiempo_limite_min` haciendo que
# venza recién en el `cierre` de la ventana. Con la ventana por defecto de una
# semana, eso deja una sesión de proctoring abierta siete días: cámara prendida,
# capturas acumulándose y la sesión sin auto-finalizar.
#
# Decisión del dueño (29/8/2026): por defecto, 60 minutos. Seguir eligiendo "sin
# límite" a propósito es posible (mandando null explícito, que es lo que hace el
# editor de configuración con su casilla), pero deja de ser lo que pasa por
# omisión.


def test_sin_pedirlo_el_examen_nace_con_una_hora():
    assert _req().tiempo_limite_min == 60


def test_respeta_el_tiempo_que_manda_quien_crea():
    assert _req(tiempo_limite_min=90).tiempo_limite_min == 90


def test_un_null_explicito_sigue_siendo_sin_limite():
    """El default es para la omisión, no una prohibición: el editor de config
    tiene una casilla "sin límite" y tiene que poder ejercerla."""
    assert _req(tiempo_limite_min=None).tiempo_limite_min is None


def test_rechaza_un_tiempo_de_cero_o_negativo():
    """Cero minutos vence el examen antes de que el alumno lea la primera
    pregunta, y el error aparecería recién al rendir."""
    for invalido in (0, -30):
        with pytest.raises(ValueError):
            _req(tiempo_limite_min=invalido)
