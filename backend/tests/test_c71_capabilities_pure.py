"""Tests puros de la capa de capacidades config-driven (c-71 slice 2, D8;
modelo colapsado a UN SOLO PASO — no hay capacidad `resolver_caso` separada).

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


def test_estudiante_no_tiene_capacidad_revisar_sesion() -> None:
    assert tiene_capacidad(Rol.ESTUDIANTE, "revisar_sesion") is False


def test_revisar_sesion_cubre_todo_el_acto_incluida_la_anulacion() -> None:
    """No hay una capacidad separada para anular: quien revisa decide, en el
    mismo acto (aprobar o anular), sin segunda instancia (D8 colapsado)."""
    assert tiene_capacidad(Rol.REVISOR, "revisar_sesion") is True
    assert tiene_capacidad(Rol.COORDINADOR, "revisar_sesion") is True
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, "revisar_sesion") is True


def test_capacidad_desconocida_deniega_por_defecto() -> None:
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, "capacidad_inexistente") is False


def test_resolver_caso_ya_no_existe_como_capacidad_del_mapa() -> None:
    """El modelo de dos fases (con una capacidad de resolucion separada) fue
    rechazado explicitamente por el owner del proyecto."""
    assert "resolver_caso" not in CAPABILITY_ROLES


def test_tutor_no_puede_gestionar_estructura_academica() -> None:
    """El tutor NO crea materias/comisiones (estructura académica) — solo admin.
    Corrige el over-permiso: `gestionar_academico` incluía al tutor y protegía
    también el alta de materias/comisiones."""
    assert tiene_capacidad(Rol.TUTOR, "gestionar_estructura") is False


def test_admins_pueden_gestionar_estructura_academica() -> None:
    """Alta/edición de materias y comisiones: roles de alcance institucional."""
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, "gestionar_estructura") is True
    assert tiene_capacidad(Rol.ADMIN_EXAMENES, "gestionar_estructura") is True
    assert tiene_capacidad(Rol.COORDINADOR, "gestionar_estructura") is True


def test_tutor_conserva_gestionar_academico() -> None:
    """El tutor SIGUE pudiendo inscribir y crear exámenes (no se le saca eso)."""
    assert tiene_capacidad(Rol.TUTOR, "gestionar_academico") is True


def test_reasignar_capacidad_en_el_mapa_cambia_el_gating_sin_tocar_endpoint(
    monkeypatch,
) -> None:
    """Remapear `revisar_sesion` a otro rol es un cambio de config del mapa,
    no requiere tocar `tiene_capacidad` ni los endpoints que la invocan."""
    nuevo_mapa = dict(CAPABILITY_ROLES)
    nuevo_mapa["revisar_sesion"] = frozenset({Rol.COORDINADOR})
    monkeypatch.setattr(
        "app.domain.auth.capabilities.CAPABILITY_ROLES", nuevo_mapa
    )

    assert tiene_capacidad(Rol.COORDINADOR, "revisar_sesion") is True
    assert tiene_capacidad(Rol.REVISOR, "revisar_sesion") is False
