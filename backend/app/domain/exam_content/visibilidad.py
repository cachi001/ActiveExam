"""Visibilidad de resultados por examen (C-69, gate estilo Moodle "Review options").

Funciones PURAS que deciden, dado el momento actual, si el alumno puede ver la nota
y/o la revisión (corrección) de un examen:

- ``nota_visible``: 'nunca' → jamás (c-78 D9, el default: hay que publicar a mano);
  'inmediata' → siempre; 'al_cerrar' → recién cuando pasó el cierre.
- ``revision_visible``: requiere que la revisión esté habilitada Y que la nota ya sea
  visible (la corrección NUNCA se muestra antes que la nota — evita filtrar respuestas
  mientras otros rinden).

La nota y las respuestas SIEMPRE se calculan y guardan server-side; esto solo decide
CUÁNDO se muestran (la capa HTTP no envía el dato si no corresponde).
"""

from __future__ import annotations

from datetime import datetime

MOSTRAR_NOTA_INMEDIATA = "inmediata"
MOSTRAR_NOTA_AL_CERRAR = "al_cerrar"
# c-78 D9: la nota NO se muestra hasta que alguien lo decide explícitamente. Es el
# DEFAULT de todo examen nuevo: refleja el flujo real (primero se revisa, después
# se publica) en vez de publicar sola al vencer el cierre.
MOSTRAR_NOTA_NUNCA = "nunca"

# Orden de visibilidad CRECIENTE. La posición en esta tupla es el "cuánto se ve":
# `nunca` < `al_cerrar` < `inmediata`. Es el dato del que sale la regla de que la
# visibilidad no retrocede — no una lista de strings suelta.
ORDEN_VISIBILIDAD: tuple[str, ...] = (
    MOSTRAR_NOTA_NUNCA,
    MOSTRAR_NOTA_AL_CERRAR,
    MOSTRAR_NOTA_INMEDIATA,
)

MOSTRAR_NOTA_VALIDOS = frozenset(ORDEN_VISIBILIDAD)


def nivel_visibilidad(mostrar_nota: str) -> int:
    """Posición de un valor en ``ORDEN_VISIBILIDAD``.

    Un valor desconocido se trata como el MÁS restrictivo (0): ante un dato que
    no entendemos, no se muestra la nota.
    """
    try:
        return ORDEN_VISIBILIDAD.index(mostrar_nota)
    except ValueError:
        return 0


def transicion_visibilidad_permitida(actual: str, nuevo: str) -> bool:
    """True si ``actual`` puede pasar a ``nuevo`` (función PURA, c-78 D9).

    Publicar es camino de ida: el orden permitido es
    ``nunca`` → ``al_cerrar`` → ``inmediata``, SIEMPRE hacia adelante. Volver
    atrás no tiene efecto útil —el alumno que ya vio la nota, la vio— y sí
    genera reclamos, así que se bloquea en vez de dejarlo disponible "por las
    dudas". Quedarse en el mismo valor está permitido (un PATCH que reenvía la
    config completa sin tocar la visibilidad no puede fallar por eso).
    """
    return nivel_visibilidad(nuevo) >= nivel_visibilidad(actual)


def nota_visible(
    *,
    mostrar_nota: str,
    cierre: datetime | None,
    ahora: datetime,
) -> bool:
    """True si la nota del examen puede mostrarse al alumno en ``ahora``.

    FAIL-CLOSED: un valor que no esté en ``ORDEN_VISIBILIDAD`` se trata como
    ``nunca``. Antes, cualquier string desconocido caía en la rama de
    'al_cerrar' y la nota se publicaba sola al pasar el cierre — publicar de más
    por un dato corrupto es el error que no se puede deshacer.
    """
    if mostrar_nota == MOSTRAR_NOTA_INMEDIATA:
        return True
    if mostrar_nota == MOSTRAR_NOTA_AL_CERRAR:
        return cierre is not None and ahora >= cierre
    # 'nunca' y cualquier valor desconocido: oculta, sin importar el cierre.
    return False


def revision_visible(
    *,
    revision_habilitada: bool,
    mostrar_nota: str,
    cierre: datetime | None,
    ahora: datetime,
) -> bool:
    """True si la corrección (respuestas correctas) puede mostrarse al alumno.

    Requiere que la revisión esté habilitada en el examen Y que la nota ya sea
    visible (nunca antes que la nota)."""
    if not revision_habilitada:
        return False
    return nota_visible(mostrar_nota=mostrar_nota, cierre=cierre, ahora=ahora)
