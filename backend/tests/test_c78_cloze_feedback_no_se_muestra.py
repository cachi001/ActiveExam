"""c-78 — El feedback de una opción cloze NO se le muestra al alumno.

Encontrado el 26/8/2026 rindiendo un examen real de punta a punta en producción,
con un banco de 30 preguntas de completar código que trajo el dueño.

En el formato cloze de Moodle, ``#`` separa la respuesta de su **feedback**:

    {1:MULTICHOICE_S:=int(texto)#Convierte a entero y lanza ValueError si no puede.
                    ~str(texto)#No convierte nada: nunca lanzaria ValueError.}

El parser no lo separaba, así que el feedback viajaba pegado al texto de la
opción y **el alumno lo veía**. Esto es lo que aparecía en pantalla:

    int(texto)#Convierte a entero y lanza ValueError si no puede.
    str(texto)#No convierte nada: nunca lanzaria ValueError.
    float(texto)#Aceptaria 25.7 como edad, y el enunciado pide entero.
    int(texto, 0)#El segundo argumento es la base y solo aplica a textos.

O sea: el feedback dice cuál está bien y por qué las otras están mal. **El examen
se resuelve leyendo.** En un parcial real eso lo invalida entero.

El feedback en sí no es basura — es material de repaso — así que se conserva
aparte en vez de tirarlo. Lo que no puede es estar en el texto de la opción.
"""

from __future__ import annotations

from app.application.exam_content.moodle_parser import parse_cloze_blanks

# Copiado literal del XML que trajo el dueño (Examen U1-U3, completar código).
_CLOZE_REAL = (
    "def leer_edad(texto):\n    try:\n        edad = "
    "{1:MULTICHOICE_S:=int(texto)#Convierte a entero y lanza ValueError si no puede."
    "~str(texto)#No convierte nada: nunca lanzaria ValueError."
    "~float(texto)#Aceptaria 25.7 como edad, y el enunciado pide entero."
    "~int(texto, 0)#El segundo argumento es la base y solo aplica a textos.}"
    "\n    except ValueError:\n        return None"
)


def _opciones(texto: str):
    return parse_cloze_blanks(texto)[0].opciones


def test_ninguna_opcion_le_muestra_el_feedback_al_alumno():
    """El caso que invalidaba el examen."""
    for o in _opciones(_CLOZE_REAL):
        assert "#" not in o.texto, (
            f"el alumno ve el feedback pegado a la opción: {o.texto!r}"
        )


def test_el_texto_de_la_opcion_queda_limpio():
    textos = [o.texto for o in _opciones(_CLOZE_REAL)]
    assert textos == ["int(texto)", "str(texto)", "float(texto)", "int(texto, 0)"]


def test_la_correcta_sigue_siendo_la_correcta():
    """Triangulación: separar el feedback no puede desarmar la corrección."""
    opciones = _opciones(_CLOZE_REAL)
    correctas = [o.texto for o in opciones if o.es_correcta]
    assert correctas == ["int(texto)"]


def test_el_feedback_se_conserva_aparte():
    """No se tira: es material de repaso, sirve para la devolución."""
    opciones = _opciones(_CLOZE_REAL)
    assert opciones[0].feedback == "Convierte a entero y lanza ValueError si no puede."
    assert opciones[1].feedback == "No convierte nada: nunca lanzaria ValueError."


def test_una_opcion_sin_feedback_sigue_funcionando():
    """La mayoría de los cloze no traen feedback: no se puede romper ese caso."""
    simple = "El resultado es {1:MULTICHOICE:=4~5~6} exactamente."
    opciones = _opciones(simple)

    assert [o.texto for o in opciones] == ["4", "5", "6"]
    assert opciones[0].es_correcta is True
    assert opciones[0].feedback == ""


def test_con_porcentaje_y_feedback_a_la_vez():
    """Moodle permite `%50%respuesta#feedback`: hay que separar los dos."""
    con_peso = "Vale {1:MULTICHOICE:%50%casi#Le falta el borde~=exacto#Bien.}"
    opciones = _opciones(con_peso)

    assert opciones[0].texto == "casi"
    assert opciones[0].peso == 50
    assert opciones[0].feedback == "Le falta el borde"
    assert opciones[1].texto == "exacto"
    assert opciones[1].es_correcta is True


def test_shortanswer_con_feedback_tambien_se_limpia():
    """El alumno escribe la respuesta: si el feedback quedara en el texto
    esperado, ninguna respuesta coincidiría nunca."""
    sa = "Escribí el comando: {1:SHORTANSWER:=commit#Guarda los cambios.}"
    opciones = _opciones(sa)

    assert opciones[0].texto == "commit"
    assert opciones[0].feedback == "Guarda los cambios."
