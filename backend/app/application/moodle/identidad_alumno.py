"""Con qué datos se busca al alumno en Moodle (c-78, decisión del dueño).

    "NO HAY LEGAJO, hay userid de moodle, username ES USERNAME"

El write-back buscaba por ``idnumber`` (el legajo). En este campus los alumnos no
lo tienen cargado: verificado contra el campus real el 26/8/2026, el usuario de
prueba tiene ``idnumber: None``. Buscar por ahí no encuentra a nadie, se come un
pedido al campus y devuelve cero.

Lo que sí existe siempre:

- el **userid de Moodle**: el propio Moodle nos lo manda en cada launch LTI (el
  claim ``sub``). Es la clave primaria del usuario del otro lado: exacto, estable
  y no se repite.
- el **email**.

EL ORDEN (decisión del dueño, 26/8/2026): **el email va primero**, porque es el
dato que siempre coincide entre el campus y ActiveExam. El userid de Moodle es
más exacto en teoría, pero solo lo tienen las cuentas que entraron por el link
del campus DESPUÉS de que se empezara a guardar; una cuenta creada a mano, o una
anterior, no lo tiene. Poner primero un dato que a veces falta obliga a que el
respaldo funcione siempre, y entonces el respaldo era el camino real.

El userid queda segundo, como desempate exacto.

**El username NO se usa** (decisión del dueño, 26/8/2026): el `username` que
guarda ActiveExam es el que la persona ELIGIÓ en esta plataforma, no el del
campus. No tienen por qué coincidir — de hecho en el caso real no coinciden
(`alumno.prueba2` acá contra `alumno_prueba2` allá). Buscar por ahí no solo no
encuentra: podría llegar a matchear a OTRA persona que en el campus se llame
igual, y escribirle la nota a quien no es.

Igual se busca SIEMPRE entre los matriculados del curso destino, así que un email
repetido fuera de ese curso no puede desviar una nota.
"""

from __future__ import annotations

from dataclasses import dataclass

# Prefijo del username sintético que genera el provisioning LTI (`lti:1:7`). No
# es un usuario del campus: mandarlo garantiza cero resultados y encima deja ese
# valor en los logs del campus como si fuera alguien real.
_PREFIJO_LTI = "lti:"


@dataclass(frozen=True)
class IdentidadAlumno:
    """Los datos con los que se puede reconocer al alumno del otro lado."""

    moodle_userid: int | str | None = None
    username: str | None = None
    email: str | None = None


def _userid_valido(crudo: int | str | None) -> str | None:
    """El userid de Moodle siempre es un entero. Otro Platform podría mandar un
    ``sub`` no numérico, y eso no sirve para buscar por id."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    return texto if texto.isdigit() else None


def candidatos_de_busqueda(ident: IdentidadAlumno) -> list[tuple[str, str]]:
    """Los ``(campo, valor)`` con los que buscar, en orden de preferencia.

    Devuelve lista vacía si no hay ningún dato usable: mejor no consultar que
    consultar con vacío, porque Moodle devolvería cualquier cosa o un error que
    después se lee como "el alumno no existe".
    """
    candidatos: list[tuple[str, str]] = []

    email = (ident.email or "").strip()
    if email:
        candidatos.append(("email", email))

    userid = _userid_valido(ident.moodle_userid)
    if userid:
        candidatos.append(("moodle_userid", userid))

    # El username NO entra: el de ActiveExam lo eligió la persona acá y no tiene
    # relación con el del campus. Ver el docstring del módulo.
    return candidatos
