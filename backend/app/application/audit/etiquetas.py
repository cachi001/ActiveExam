"""Cómo se nombra a una persona o una comisión en el registro de auditoría.

El registro existe para responder quién hizo qué. Escribía los UUID crudos:

    Inscribió al alumno da108d8a-4986-4271-bf38-dd63b49c2755
    en la comisión df8dc98b-49e3-4144-ac2f-76b12d4f31fb

Así no responde nada: hay que salir a buscar dos ids en la base para entender una
línea. Importa más que en otras pantallas porque este registro es el que se usa
si una sanción se discute.

El id se conserva como respaldo: es preferible un UUID a una línea que no
identifica a nadie.
"""

from __future__ import annotations


def _limpio(valor: object) -> str:
    return str(valor).strip() if valor else ""


def etiqueta_alumno(usuario: object | None, usuario_id: str) -> str:
    """'Apellido, Nombre (correo)', lo que haya, o el id.

    Se usa el CORREO y no el username porque es el dato con el que se cruza
    contra Moodle. El username además puede ser sintético: los usuarios que crea
    el ingreso por LTI se llaman "lti:1:7", que no identifica a nadie ni sirve
    para buscar en el campus.
    """
    if usuario is None:
        return usuario_id
    nombre = _limpio(getattr(usuario, "nombre", None))
    apellido = _limpio(getattr(usuario, "apellido", None))
    email = _limpio(getattr(usuario, "email", None))

    if apellido and nombre:
        persona = f"{apellido}, {nombre}"
    else:
        persona = apellido or nombre

    if persona and email:
        return f"{persona} ({email})"
    # Un correo identifica y cruza con el campus; un UUID no hace ninguna de las dos.
    return persona or email or usuario_id


def etiqueta_comision(comision: object | None, comision_id: str) -> str:
    """'CÓDIGO - Nombre', lo que haya, o el id."""
    if comision is None:
        return comision_id
    codigo = _limpio(getattr(comision, "codigo", None))
    nombre = _limpio(getattr(comision, "nombre", None))
    if codigo and nombre:
        return f"{codigo} - {nombre}"
    return codigo or nombre or comision_id
