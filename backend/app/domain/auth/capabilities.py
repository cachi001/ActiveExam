"""Capa de capacidades config-driven (capacidad -> roles), c-71 slice 2 D8.

Reemplaza el `require_roles` hardcodeado por endpoint para las dos acciones
de la Cola de Revision:

- ``revisar_sesion``: revisar la sesion y derivarla (abrir el caso) o
  cerrarla sin hallazgos/aprobada.
- ``resolver_caso``: emitir el veredicto (anular por fraude / descartar el
  caso) sobre un caso ya abierto.

HOY ambas capacidades recaen (total o parcialmente) sobre el mismo rol
REVISOR -- decision de *deployment* (concentracion), no de *modelo*. Mover
``resolver_caso`` a otra autoridad manana es un cambio de ESTE mapa, sin
tocar routers ni logica (mismo espiritu que ``ROLES_CON_MFA`` en
``roles.py``).

Sin framework ni infraestructura (D1): dominio puro, testeable sin DB/red.
"""

from __future__ import annotations

from app.domain.auth.roles import Rol

# capacidad -> conjunto de roles que la poseen. Dato de config, no logica.
CAPABILITY_ROLES: dict[str, frozenset[Rol]] = {
    "revisar_sesion": frozenset({Rol.REVISOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}),
    # HOY: concentracion en revisor. Remapeable por config (D8), sin refactor.
    "resolver_caso": frozenset({Rol.REVISOR}),
}


def tiene_capacidad(rol: Rol, capacidad: str) -> bool:
    """``True`` si ``rol`` esta en el conjunto de roles de ``capacidad``.

    Una capacidad no declarada en el mapa deniega por defecto (fail-closed)."""
    return rol in CAPABILITY_ROLES.get(capacidad, frozenset())
