"""Tests RBAC de la eliminacion del rol AUDITOR (c-76-2 — CRITICO).

El rol ``auditor`` fue ELIMINADO del dominio: el dueno del producto decidio
que solo debe existir un rol "Admin" (ADMIN_SISTEMA). La capacidad
``ver_auditoria`` (solo lectura del registro de auditoria) queda exclusiva de
ADMIN_SISTEMA — el endpoint real (``audit_router.py``) ya usaba
``require_roles(ADMIN_SISTEMA)`` hardcodeado, nunca conectado a la capacidad
config-driven, asi que esta eliminacion no le saca acceso real a nadie.

Garantias que este modulo bloquea (dominio puro — sin DB ni red):

1. ``Rol`` ya no expone ``AUDITOR``; ``parse_rol("auditor")`` -> ``None``.
2. ``ver_auditoria`` = {ADMIN_SISTEMA}, sin auditor.
3. ``puede_acceder_a_evidencia`` ya no acepta AUDITOR (COORDINADOR/ADMIN_SISTEMA
   siguen teniendo acceso).
4. Un claim de token con rol ``"auditor"`` NO mapea a ningun ``Rol`` de dominio:
   se descarta en silencio, mismo precedente que "proctor"/"revisor".
"""

from __future__ import annotations

import pytest

from app.domain.auth import authorization
from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad
from app.domain.auth.identity import AuthenticatedPrincipal
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
# 1. El enum ya no tiene AUDITOR
# ---------------------------------------------------------------------------


def test_rol_no_expone_auditor() -> None:
    """``Rol.AUDITOR`` fue eliminado: acceder a el es AttributeError."""
    assert not hasattr(Rol, "AUDITOR")


def test_valores_del_enum_no_incluyen_auditor() -> None:
    """El literal 'auditor' no es un valor valido del enum ``Rol``."""
    assert "auditor" not in {r.value for r in Rol}


@pytest.mark.parametrize("desconocido", ["auditor", "supervisor", "rol-inexistente"])
def test_parse_rol_descarta_auditor_y_desconocidos(desconocido: str) -> None:
    """``parse_rol`` devuelve None para 'auditor' y cualquier rol desconocido."""
    assert parse_rol(desconocido) is None


# ---------------------------------------------------------------------------
# 2. ver_auditoria remapeado (sin auditor)
# ---------------------------------------------------------------------------


def test_ver_auditoria_es_solo_admin_sistema() -> None:
    """``ver_auditoria`` = {ADMIN_SISTEMA}."""
    assert CAPABILITY_ROLES["ver_auditoria"] == frozenset({Rol.ADMIN_SISTEMA})


def test_admin_sistema_conserva_ver_auditoria() -> None:
    assert tiene_capacidad(Rol.ADMIN_SISTEMA, "ver_auditoria") is True


@pytest.mark.parametrize("rol", [Rol.ESTUDIANTE, Rol.TUTOR, Rol.COORDINADOR])
def test_roles_no_admin_no_tienen_ver_auditoria(rol: Rol) -> None:
    """Triangulacion: quien no es admin_sistema sigue sin la capacidad."""
    assert tiene_capacidad(rol, "ver_auditoria") is False


# ---------------------------------------------------------------------------
# 3. puede_acceder_a_evidencia ya no acepta AUDITOR
# ---------------------------------------------------------------------------


def _principal(roles: tuple[Rol, ...], mfa: bool = True) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        username="u-1",
        email="u1@uni.edu",
        roles=roles,
        mfa_satisfecho=mfa,
    )


def test_coordinador_conserva_acceso_a_evidencia() -> None:
    """Triangulacion: el acceso a evidencia no se le saca a quien lo tenia."""
    authorization.puede_acceder_a_evidencia(_principal((Rol.COORDINADOR,)))


def test_rol_sin_acceso_a_evidencia_rechazado() -> None:
    from app.domain.auth.errors import ForbiddenError

    with pytest.raises(ForbiddenError):
        authorization.puede_acceder_a_evidencia(_principal((Rol.TUTOR,)))


# ---------------------------------------------------------------------------
# 4. Claim colgante 'auditor' en el token -> ningun Rol de dominio
# ---------------------------------------------------------------------------


def test_claim_auditor_no_mapea_a_ningun_rol() -> None:
    """Un token con rol 'auditor' produce un principal SIN roles de dominio."""
    principal = _policy().principal_desde_claims(_claims(["auditor"]))
    assert principal.roles == ()


def test_claim_auditor_junto_a_admin_sistema_solo_conserva_admin_sistema() -> None:
    """Triangulacion: 'auditor' se descarta pero los roles vivos del claim quedan."""
    principal = _policy().principal_desde_claims(_claims(["auditor", "admin_sistema"]))
    assert Rol.ADMIN_SISTEMA in principal.roles
    assert principal.roles == (Rol.ADMIN_SISTEMA,)
