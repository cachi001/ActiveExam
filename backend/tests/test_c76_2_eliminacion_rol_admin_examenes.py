"""Tests RBAC de la eliminacion del rol ADMIN_EXAMENES (c-76-2 — CRITICO).

El rol ``admin_examenes`` fue ELIMINADO del dominio: el dueno del producto
decidio que solo debe existir un rol "Admin" (ADMIN_SISTEMA). La gestion
academica que tenia admin_examenes (examenes/materias/comisiones sin poder de
supervision) pasa a ser exclusiva de ADMIN_SISTEMA.

Garantias que este modulo bloquea (dominio puro — sin DB ni red):

1. ``Rol`` ya no expone ``ADMIN_EXAMENES``; ``parse_rol("admin_examenes")`` -> ``None``.
2. Las capacidades que tenia (``gestionar_academico``, ``gestionar_estructura``,
   ``gestionar_notas``, ``asignar_docente``) quedan sin ``admin_examenes``, pero
   ``ADMIN_SISTEMA`` las sigue teniendo todas (superset, no perdio nada).
3. Un claim de token con rol ``"admin_examenes"`` NO mapea a ningun ``Rol`` de
   dominio: se descarta en silencio, mismo precedente que "proctor"/"revisor".
"""

from __future__ import annotations

import pytest

from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad
from app.domain.auth.roles import Rol, parse_rol
from app.domain.auth.token import TokenPolicy

_ISSUER = "activeexam-auth"
_AUD = "proctoring-api"


def _policy() -> TokenPolicy:
    return TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)


def _claims(roles: list[str]) -> dict:
    return {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "sub-1",
        "preferred_username": "u1",
        "email": "u1@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }


# ---------------------------------------------------------------------------
# 1. El enum ya no tiene ADMIN_EXAMENES
# ---------------------------------------------------------------------------


def test_rol_no_expone_admin_examenes() -> None:
    """``Rol.ADMIN_EXAMENES`` fue eliminado: acceder a el es AttributeError."""
    assert not hasattr(Rol, "ADMIN_EXAMENES")


def test_valores_del_enum_no_incluyen_admin_examenes() -> None:
    """El literal 'admin_examenes' no es un valor valido del enum ``Rol``."""
    assert "admin_examenes" not in {r.value for r in Rol}


@pytest.mark.parametrize("desconocido", ["admin_examenes", "supervisor", "rol-inexistente"])
def test_parse_rol_descarta_admin_examenes_y_desconocidos(desconocido: str) -> None:
    """``parse_rol`` devuelve None para 'admin_examenes' y cualquier rol desconocido."""
    assert parse_rol(desconocido) is None


def test_parse_rol_sigue_mapeando_roles_vivos() -> None:
    """Triangulacion: los roles vivos siguen mapeando (no rompimos parse_rol)."""
    assert parse_rol("admin_sistema") is Rol.ADMIN_SISTEMA
    assert parse_rol("tutor") is Rol.TUTOR


# ---------------------------------------------------------------------------
# 2. Las capacidades academicas quedan sin admin_examenes, ADMIN_SISTEMA no
#    pierde nada (superset)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "capacidad",
    ["gestionar_academico", "gestionar_estructura", "gestionar_notas", "asignar_docente"],
)
def test_admin_sistema_conserva_todas_las_capacidades_academicas(capacidad: str) -> None:
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, capacidad) is True


def test_gestionar_estructura_queda_coordinador_y_admin_sin_admin_examenes() -> None:
    """`gestionar_estructura` (crear materias/comisiones): sin admin_examenes."""
    assert CAPABILITY_ROLES["gestionar_estructura"] == frozenset(
        {Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


def test_gestionar_academico_conserva_tutor_coordinador_admin() -> None:
    """Triangulacion: `gestionar_academico` conserva TUTOR/COORDINADOR/ADMIN_SISTEMA
    y NO tiene 'admin_examenes'.

    Pertenencia, no set exacto: c-78 sumo PROFESOR a esta capacidad, que es un
    cambio legitimo y ajeno a lo que este archivo verifica.
    """
    roles = CAPABILITY_ROLES["gestionar_academico"]
    assert {Rol.TUTOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA} <= set(roles)
    assert not any(getattr(r, "value", r) == "admin_examenes" for r in roles)


# ---------------------------------------------------------------------------
# 3. Claim colgante 'admin_examenes' en el token -> ningun Rol de dominio
# ---------------------------------------------------------------------------


def test_claim_admin_examenes_no_mapea_a_ningun_rol() -> None:
    """Un token con rol 'admin_examenes' produce un principal SIN roles de dominio."""
    principal = _policy().principal_desde_claims(_claims(["admin_examenes"]))
    assert principal.roles == ()


def test_claim_admin_examenes_junto_a_tutor_solo_conserva_tutor() -> None:
    """Triangulacion: 'admin_examenes' se descarta pero los roles vivos del claim quedan."""
    principal = _policy().principal_desde_claims(_claims(["admin_examenes", "tutor"]))
    assert Rol.TUTOR in principal.roles
    assert principal.roles == (Rol.TUTOR,)
