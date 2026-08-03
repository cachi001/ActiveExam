"""Capa de capacidades config-driven (capacidad -> roles), c-71 slice 2 D8.

Reemplaza el `require_roles` hardcodeado por endpoint para la accion de la
Cola de Revision:

- ``revisar_sesion``: decision TERMINAL de la sesion, en un solo acto —
  aprobar o anular. NO hay una capacidad separada para "resolver" un caso
  abierto: el owner del proyecto rechazo explicitamente el modelo de dos
  fases ("no existe el caso abierto, nunca dije que era un estado y no lo
  va a ser"; confirmado: "si, un solo paso: quien revisa decide", sin
  segunda instancia). Quien tiene `revisar_sesion` puede aprobar Y anular.

Sin framework ni infraestructura (D1): dominio puro, testeable sin DB/red.
"""

from __future__ import annotations

from app.domain.auth.roles import Rol

# capacidad -> conjunto de roles que la poseen. Dato de config, no logica.
CAPABILITY_ROLES: dict[str, frozenset[Rol]] = {
    # --- Circuito de revision humana (L2.5) ---------------------------------
    "revisar_sesion": frozenset({Rol.REVISOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}),
    # --- Gestion academica ---------------------------------------------------
    # Alta/edicion de examenes, materias y comisiones. El DOCENTE vive aca: es su
    # trabajo. El revisor NO la tiene — quien juzga el fraude no edita el examen.
    "gestionar_academico": frozenset(
        {Rol.DOCENTE, Rol.ADMIN_EXAMENES, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # Ver las notas y sincronizarlas a Moodle: el docente necesita cerrar la nota
    # de su materia.
    "gestionar_notas": frozenset(
        {Rol.DOCENTE, Rol.ADMIN_EXAMENES, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # Asignar el docente a cargo de una comision (C-73 §9). Deliberadamente SIN
    # DOCENTE: quien queda a cargo decide quien devuelve la nota a Moodle y que
    # examenes puede tocar. Si el docente pudiera asignarse solo, la pertenencia
    # dejaria de ser un control (se auto-otorgaria el acceso que el control niega).
    "asignar_docente": frozenset(
        {Rol.ADMIN_EXAMENES, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
    # --- Administracion del sistema -----------------------------------------
    # Umbrales, detectores, retencion. Deliberadamente SIN docente: la
    # configuracion define como se detecta el fraude; quien dicta la materia no
    # debe poder aflojarla para su propio examen.
    "configurar_sistema": frozenset({Rol.ADMIN_SISTEMA}),
    # Alta/baja de usuarios y asignacion de roles: solo admin del sistema.
    "gestionar_usuarios": frozenset({Rol.ADMIN_SISTEMA}),
    # Registro inmutable: lo lee quien audita, no quien opera.
    "ver_auditoria": frozenset({Rol.AUDITOR, Rol.ADMIN_SISTEMA}),
    # --- Supervision en vivo -------------------------------------------------
    # Mirar sesiones en curso. Sin docente: es evidencia biometrica en vivo.
    "supervisar_vivo": frozenset(
        {Rol.PROCTOR, Rol.REVISOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    ),
}


def tiene_capacidad(rol: Rol, capacidad: str) -> bool:
    """``True`` si ``rol`` esta en el conjunto de roles de ``capacidad``.

    Una capacidad no declarada en el mapa deniega por defecto (fail-closed)."""
    return rol in CAPABILITY_ROLES.get(capacidad, frozenset())
