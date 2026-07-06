"""Visibilidad de resultados por examen (C-69, gate estilo Moodle "Review options").

Funciones PURAS que deciden, dado el momento actual, si el alumno puede ver la nota
y/o la revisión (corrección) de un examen:

- ``nota_visible``: 'inmediata' → siempre; 'al_cerrar' → recién cuando pasó el cierre.
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


def nota_visible(
    *,
    mostrar_nota: str,
    cierre: datetime | None,
    ahora: datetime,
) -> bool:
    """True si la nota del examen puede mostrarse al alumno en ``ahora``."""
    if mostrar_nota == MOSTRAR_NOTA_INMEDIATA:
        return True
    # 'al_cerrar' (default): visible recién cuando pasó la fecha de cierre.
    return cierre is not None and ahora >= cierre


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
