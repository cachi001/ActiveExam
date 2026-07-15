"""Tests puros de la capa de capacidades config-driven (c-71 slice 2, D8).

`tiene_capacidad(rol, capacidad)` resuelve desde el mapa `CAPABILITY_ROLES`
(capacidad -> conjunto de roles), sin infra ni FastAPI. Verifica que la
reasignacion de una capacidad a otro rol en el mapa cambia el gating sin
tocar el endpoint (la funcion solo lee el mapa, nunca hardcodea el rol).
"""

from __future__ import annotations

from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad
from app.domain.auth.roles import Rol


def test_revisor_tiene_capacidad_revisar_sesion() -> None:
    assert tiene_capacidad(Rol.REVISOR, "revisar_sesion") is True


def test_estudiante_no_tiene_capacidad_resolver_caso() -> None:
    assert tiene_capacidad(Rol.ESTUDIANTE, "resolver_caso") is False


def test_revisor_tiene_capacidad_resolver_caso_hoy_concentrada() -> None:
    assert tiene_capacidad(Rol.REVISOR, "resolver_caso") is True


def test_coordinador_no_tiene_resolver_caso_hoy() -> None:
    """Hoy `resolver_caso` esta concentrada solo en revisor (D8)."""
    assert tiene_capacidad(Rol.COORDINADOR, "resolver_caso") is False


def test_capacidad_desconocida_deniega_por_defecto() -> None:
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, "capacidad_inexistente") is False


def test_reasignar_capacidad_en_el_mapa_cambia_el_gating_sin_tocar_endpoint(
    monkeypatch,
) -> None:
    """Remapear `resolver_caso` a otro rol es un cambio de config del mapa,
    no requiere tocar `tiene_capacidad` ni los endpoints que la invocan."""
    nuevo_mapa = dict(CAPABILITY_ROLES)
    nuevo_mapa["resolver_caso"] = frozenset({Rol.COORDINADOR})
    monkeypatch.setattr(
        "app.domain.auth.capabilities.CAPABILITY_ROLES", nuevo_mapa
    )

    assert tiene_capacidad(Rol.COORDINADOR, "resolver_caso") is True
    assert tiene_capacidad(Rol.REVISOR, "resolver_caso") is False
