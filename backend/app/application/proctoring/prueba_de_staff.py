"""Quién rinde de prueba y quién rinde de verdad.

Un examen en borrador existe para probarlo antes de soltarlo. Que la rendición
del docente NO cuente es una decisión del SERVIDOR a partir del rol: si viniera
del cliente, un alumno pediría que la suya tampoco cuente (regla dura #6).

El corte es `gestionar_academico` y no `crear_examenes` por decisión del dueño
(28/8/2026): el tutor no arma el examen, pero acompaña la comisión y necesita
ver qué se toma. La pertenencia al examen se verifica aparte, en el endpoint —
este módulo responde solo "¿este rol rinde de prueba?".
"""

from __future__ import annotations

from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad

_CAPACIDAD = "gestionar_academico"

#: Roles cuya rendición es siempre un ensayo. Sale del mapa de capacidades para
#: que sumar un rol académico no obligue a acordarse de esta lista.
ROLES_QUE_PUEDEN_PROBAR: frozenset[str] = frozenset(
    str(rol.value if hasattr(rol, "value") else rol)
    for rol in CAPABILITY_ROLES.get(_CAPACIDAD, frozenset())
)


def es_rendicion_de_prueba(roles: list[str], *, es_examen_propio: bool) -> bool:
    """True si es staff académico probando SU examen: la rendición es un ensayo.

    Las dos condiciones son necesarias, y `es_examen_propio` es obligatorio a
    propósito (kwarg sin default), porque las dos cosas que evita se cometen
    justamente cuando uno se olvida de pasarlo:

    - sobre un examen AJENO, saltear la inscripción dejaría a un docente abrir
      el parcial de otra cátedra y verle las preguntas antes de que se tome;
    - un profesor que además cursa otra materia tiene los dos roles: si el rol
      alcanzara, su parcial de verdad quedaría marcado como ensayo y sin nota.

    Un rol desconocido no habilita nada: ante la duda, la rendición cuenta.
    """
    if not es_examen_propio:
        return False
    return any(tiene_capacidad(rol, _CAPACIDAD) for rol in roles)
