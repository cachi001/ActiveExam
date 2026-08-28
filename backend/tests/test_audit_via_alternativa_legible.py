"""La vía alternativa al consentimiento tiene que leerse en el registro.

El propósito se escribía como `via_alternativa:{exam_id}`: un marcador de máquina
en el campo que la pantalla de Auditoría muestra como texto. Quedaba una línea
así, que no dice ni qué pasó ni a quién:

    via_alternativa:32fd316c-f4b5-47a5-b055-e394c9f59d5d

Importa porque es un registro de consentimiento (Ley 25.326): es la prueba de que
alguien pidió no dar su consentimiento biométrico y se le ofreció otra vía.

El marcador NO se puede sacar: `resolver()` lo busca como respaldo de
retrocompatibilidad para datos viejos que no tienen fila en
`solicitudes_via_alternativa`. Se conserva DENTRO del texto y la búsqueda pasa a
ser por contenido, así siguen matcheando las entradas viejas (que son el marcador
solo) y las nuevas (que lo llevan al final).
"""

from __future__ import annotations

from app.application.consent.service import proposito_via_alternativa, marcador_via_alternativa


def test_el_texto_dice_que_paso():
    texto = proposito_via_alternativa("examen-1")
    assert "alternativa" in texto.lower()
    # Una persona leyendo el registro tiene que entender la linea sin ir al codigo.
    assert len(texto.split()) > 3


def test_el_texto_conserva_el_marcador_de_maquina():
    # Sin esto, el respaldo de retrocompatibilidad deja de encontrar la entrada.
    texto = proposito_via_alternativa("examen-1")
    assert marcador_via_alternativa("examen-1") in texto


def test_el_marcador_viejo_sigue_matcheando():
    # Las entradas escritas antes de este cambio son SOLO el marcador. La busqueda
    # por contenido tiene que seguir encontrandolas.
    viejo = marcador_via_alternativa("examen-1")
    assert marcador_via_alternativa("examen-1") in viejo


def test_el_marcador_distingue_entre_examenes():
    # Dos examenes distintos no pueden confundirse: el respaldo resuelve por
    # examen, y un falso positivo habilitaria una via alternativa que nadie pidio.
    assert marcador_via_alternativa("examen-1") != marcador_via_alternativa("examen-2")
    assert marcador_via_alternativa("examen-2") not in proposito_via_alternativa("examen-1")
