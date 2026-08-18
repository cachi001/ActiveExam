"""Tests RBAC de la eliminacion del rol PROCTOR (c-76, Tarea 7 — CRITICO).

El rol ``proctor`` fue ELIMINADO del dominio: el COORDINADOR absorbe la
supervision global en vivo + el veredicto, y el TUTOR gana la supervision en vivo
(acotada por comision en la capa de aplicacion, Tarea 8) SIN el veredicto.

Garantias que este modulo bloquea (dominio puro — sin DB ni red):

1. ``Rol`` ya no expone ``PROCTOR``; ``parse_rol("proctor")`` -> ``None``.
2. ``supervisar_vivo`` = {TUTOR, REVISOR, COORDINADOR, ADMIN_SISTEMA}, sin proctor.
3. El TUTOR tiene ``supervisar_vivo`` pero NO ``revisar_sesion`` (no juzga el fraude).
4. Un claim de token con rol ``"proctor"`` NO mapea a ningun ``Rol`` de dominio:
   se descarta en silencio (Q1 del design c-76: descarte silencioso, igual que
   cualquier rol desconocido del IdP).
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
# 1. El enum ya no tiene PROCTOR
# ---------------------------------------------------------------------------

def test_rol_no_expone_proctor() -> None:
    """``Rol.PROCTOR`` fue eliminado: acceder a el es AttributeError."""
    assert not hasattr(Rol, "PROCTOR")


def test_valores_del_enum_no_incluyen_proctor() -> None:
    """El literal 'proctor' no es un valor valido del enum ``Rol``."""
    assert "proctor" not in {r.value for r in Rol}


@pytest.mark.parametrize("desconocido", ["proctor", "supervisor", "rol-inexistente"])
def test_parse_rol_descarta_proctor_y_desconocidos(desconocido: str) -> None:
    """``parse_rol`` devuelve None para 'proctor' y cualquier rol desconocido."""
    assert parse_rol(desconocido) is None


def test_parse_rol_sigue_mapeando_roles_vivos() -> None:
    """Triangulacion: los roles vivos siguen mapeando (no rompimos parse_rol)."""
    assert parse_rol("coordinador") is Rol.COORDINADOR
    assert parse_rol("tutor") is Rol.TUTOR


# ---------------------------------------------------------------------------
# 2. supervisar_vivo remapeado (sin proctor, con tutor)
#
# NOTA (c-76, post-Tarea 7): el rol REVISOR tambien fue eliminado del dominio
# (decision separada, ver ``test_c76_eliminacion_rol_revisor.py``). Los sets
# esperados aca ya reflejan esa eliminacion para no romper este archivo.
# ---------------------------------------------------------------------------

def test_supervisar_vivo_es_tutor_coordinador_admin() -> None:
    """``supervisar_vivo`` = {TUTOR, COORDINADOR, ADMIN_SISTEMA}."""
    assert CAPABILITY_ROLES["supervisar_vivo"] == frozenset(
        {Rol.TUTOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


@pytest.mark.parametrize(
    "rol",
    [Rol.TUTOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA],
)
def test_roles_supervisores_tienen_supervisar_vivo(rol: Rol) -> None:
    assert tiene_capacidad(rol, "supervisar_vivo") is True


@pytest.mark.parametrize("rol", [Rol.ESTUDIANTE])
def test_roles_no_supervisores_no_tienen_supervisar_vivo(rol: Rol) -> None:
    """Triangulacion: quien NO supervisa en vivo sigue sin la capacidad."""
    assert tiene_capacidad(rol, "supervisar_vivo") is False


# ---------------------------------------------------------------------------
# 3. El TUTOR supervisa pero NO juzga (separacion de poderes L2.5)
# ---------------------------------------------------------------------------

def test_tutor_supervisa_pero_no_dicta_veredicto() -> None:
    """El TUTOR tiene ``supervisar_vivo`` pero NO ``revisar_sesion`` (veredicto)."""
    assert tiene_capacidad(Rol.TUTOR, "supervisar_vivo") is True
    assert tiene_capacidad(Rol.TUTOR, "revisar_sesion") is False


def test_revisar_sesion_no_incluye_tutor() -> None:
    """El veredicto sigue en {COORDINADOR, ADMIN_SISTEMA} — sin TUTOR (ni REVISOR,
    eliminado por separado — ver ``test_c76_eliminacion_rol_revisor.py``)."""
    assert Rol.TUTOR not in CAPABILITY_ROLES["revisar_sesion"]
    assert CAPABILITY_ROLES["revisar_sesion"] == frozenset(
        {Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


# ---------------------------------------------------------------------------
# 4. Claim colgante 'proctor' en el token -> ningun Rol de dominio
# ---------------------------------------------------------------------------

def test_claim_proctor_no_mapea_a_ningun_rol() -> None:
    """Un token con rol 'proctor' produce un principal SIN roles de dominio."""
    principal = _policy().principal_desde_claims(_claims(["proctor"]))
    assert principal.roles == ()


def test_claim_proctor_junto_a_coordinador_solo_conserva_coordinador() -> None:
    """Triangulacion: 'proctor' se descarta pero los roles vivos del claim quedan."""
    principal = _policy().principal_desde_claims(_claims(["proctor", "coordinador"]))
    assert Rol.COORDINADOR in principal.roles
    assert principal.roles == (Rol.COORDINADOR,)
