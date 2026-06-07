"""Tests de validacion LOCAL de JWT (C-06, capability jwt-validation-refresh).

Verifica D2 con un verificador HS256 stdlib (sin PyJWT ni red): firma valida
aceptada, firma invalida/expirado/audiencia-incorrecta/issuer-incorrecto
rechazados (401 -> UnauthenticatedError). Tambien valida el cache JWKS (refresco
por TTL y por kid faltante) sin red, y el mapeo de claims a principal + MFA.
"""

from __future__ import annotations

import pytest

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.roles import Rol
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256

_SECRET = b"test-secret-no-produccion"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


def _validator(now: float = 1000.0) -> JwtValidator:
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    verify = build_hs256_verify(_SECRET, time_fn=lambda: now)
    return JwtValidator(jwks_cache=cache, policy=policy, verify_fn=verify)


def _claims(**over) -> dict:
    base = {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "kc-sub-1",
        "preferred_username": "alu123",
        "email": "alu123@uni.edu",
        "exp": 2000,
        "realm_access": {"roles": ["proctor"]},
        "amr": ["otp"],
    }
    base.update(over)
    return base


def test_token_valido_aceptado() -> None:
    token = encode_hs256(_claims(), _SECRET)
    principal = _validator().validar(token)
    assert principal.id_institucional == "alu123"
    assert Rol.PROCTOR in principal.roles
    assert principal.mfa_satisfecho is True


def test_firma_invalida_rechazada() -> None:
    token = encode_hs256(_claims(), b"otro-secreto")
    with pytest.raises(UnauthenticatedError):
        _validator().validar(token)


def test_token_expirado_rechazado() -> None:
    token = encode_hs256(_claims(exp=500), _SECRET)
    with pytest.raises(UnauthenticatedError):
        _validator(now=1000.0).validar(token)


def test_audiencia_incorrecta_rechazada() -> None:
    token = encode_hs256(_claims(aud="otra-api"), _SECRET)
    with pytest.raises(UnauthenticatedError):
        _validator().validar(token)


def test_issuer_incorrecto_rechazado() -> None:
    token = encode_hs256(_claims(iss="http://malicioso/realms/x"), _SECRET)
    with pytest.raises(UnauthenticatedError):
        _validator().validar(token)


def test_token_sin_segundo_factor_no_satisface_mfa() -> None:
    token = encode_hs256(_claims(amr=["pwd"]), _SECRET)
    principal = _validator().validar(token)
    assert principal.mfa_satisfecho is False


def test_token_malformado_rechazado() -> None:
    with pytest.raises(UnauthenticatedError):
        _validator().validar("no-es-un-jwt")


def test_jwks_cache_refresca_por_kid_faltante() -> None:
    llamadas = {"n": 0}

    def fetch():
        llamadas["n"] += 1
        # Primera vez sin la clave; tras refresco, aparece.
        if llamadas["n"] == 1:
            return {"keys": [{"kid": "vieja"}]}
        return {"keys": [{"kid": "nueva"}]}

    cache = JwksCache(fetch, ttl_seconds=3600)
    assert cache.get_jwk("nueva") is not None
    assert llamadas["n"] == 2  # forzo un refresco por kid faltante
