"""Quién puede estar en el padrón de una comisión.

El padrón es la lista de ALUMNOS que cursan. Ni el panel del docente ni la
autoinscripción por código miraban el rol, así que un docente podía quedar
adentro — y entonces aparecía en la tabla de notas de su propio examen como
ausente con 0 y desaprobado, y quedaba a un click de que le publicaran esa nota
en Moodle.

La regla es por ROL y no por "no ser docente": un profesor que además cursa otra
materia tiene los dos roles y se inscribe sin problema. Lo que no se puede es
meter en el padrón a alguien que no es alumno de nada.
"""

from __future__ import annotations

from app.domain.auth.roles import Rol


def puede_estar_en_el_padron(roles: list[str]) -> bool:
    """True si el usuario es alumno. Un rol desconocido no alcanza."""
    return any(rol == Rol.ESTUDIANTE.value for rol in roles)
