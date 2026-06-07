"""Tests de TokenPolicy con issuers_aceptados (C-55, dominio puro).

Verifica que la policy multi-issuer acepta el issuer propio Y el de Keycloak,
y rechaza cualquier issuer no configurado.

Sin red ni DB — dominio puro.
"""

from __future__ import annotations

import pytest

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.roles import Rol
from app.domain.auth.token import TokenPolicy

_ISSUER_PROPIO = "activeexam-auth"
_ISSUER_KEYCLOAK = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


def _policy_multi() -> TokenPolicy:
    return TokenPolicy(
        issuers_aceptados=frozenset({_ISSUER_PROPIO, _ISSUER_KEYCLOAK}),
        audience=_AUD,
    )


def _claims_base(iss: str) -> dict:
    return {
        "iss": iss,
        "aud": _AUD,
        "sub": "user-uuid-1",
        "preferred_username": "alu123",
        "email": "alu123@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": ["proctor"]},
    }


def test_issuer_propio_aceptado() -> None:
    policy = _policy_multi()
    principal = policy.principal_desde_claims(_claims_base(_ISSUER_PROPIO))
    assert principal.id_institucional == "alu123"
    assert Rol.PROCTOR in principal.roles


def test_issuer_keycloak_aceptado() -> None:
    policy = _policy_multi()
    principal = policy.principal_desde_claims(_claims_base(_ISSUER_KEYCLOAK))
    assert principal.id_institucional == "alu123"
    assert Rol.PROCTOR in principal.roles


def test_issuer_desconocido_rechazado() -> None:
    policy = _policy_multi()
    with pytest.raises(UnauthenticatedError):
        policy.principal_desde_claims(_claims_base("http://malicioso.io/auth"))


def test_issuer_vacio_rechazado() -> None:
    policy = _policy_multi()
    claims = _claims_base("")
    with pytest.raises(UnauthenticatedError):
        policy.principal_desde_claims(claims)


def test_audiencia_incorrecta_rechazada() -> None:
    policy = _policy_multi()
    claims = {**_claims_base(_ISSUER_PROPIO), "aud": "otra-api"}
    with pytest.raises(UnauthenticatedError):
        policy.principal_desde_claims(claims)


def test_from_single_issuer_retrocompatibilidad() -> None:
    """from_single_issuer() debe crear un frozenset de un solo elemento."""
    policy = TokenPolicy.from_single_issuer(_ISSUER_KEYCLOAK, _AUD)
    assert policy.issuers_aceptados == frozenset({_ISSUER_KEYCLOAK})
    principal = policy.principal_desde_claims(_claims_base(_ISSUER_KEYCLOAK))
    assert principal.id_institucional == "alu123"


def test_mfa_insatisfecho_para_token_propio_sin_amr() -> None:
    """El token propio no incluye amr -> mfa_satisfecho=False (deuda tecnica MFA)."""
    policy = _policy_multi()
    claims = _claims_base(_ISSUER_PROPIO)
    # Asegurar que no hay amr.
    claims.pop("amr", None)
    principal = policy.principal_desde_claims(claims)
    assert principal.mfa_satisfecho is False
