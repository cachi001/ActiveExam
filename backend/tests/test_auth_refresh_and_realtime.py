"""Tests de refresh rotativo y auth de handshake WS/SSE (C-06).

- Rotacion (jwt-validation-refresh, D2): rotar emite uno nuevo e invalida el usado;
  reusar un refresh ya rotado -> RefreshTokenError (401 en el endpoint).
- Handshake (realtime-handshake-auth, D5): handshake sin token -> rechazado;
  conexion cortada cuando el token deja de ser valido en la revalidacion periodica.

Sin red ni libs externas (HS256 stdlib).
"""

from __future__ import annotations

import pytest

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.refresh_store import (
    InMemoryRefreshTokenStore,
    RefreshTokenError,
)
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.presentation.api.v1.auth.realtime import (
    RealtimeRevalidator,
    authenticate_handshake,
)

_SECRET = b"test-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


# --- Refresh rotativo --------------------------------------------------------


def test_refresh_rota_e_invalida_el_usado() -> None:
    store = InMemoryRefreshTokenStore()
    original = store.issue()
    nuevo = store.rotate(original)
    assert nuevo != original
    assert store.is_valid(nuevo) is True
    assert store.is_valid(original) is False  # el usado quedo invalidado


def test_refresh_ya_rotado_rechazado() -> None:
    store = InMemoryRefreshTokenStore()
    original = store.issue()
    store.rotate(original)
    with pytest.raises(RefreshTokenError):
        store.rotate(original)  # reuso del refresh ya rotado


# --- Handshake WS/SSE --------------------------------------------------------


def _clock():
    estado = {"t": 1000.0}
    return estado


def _validator(now_state) -> JwtValidator:
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuer=_ISSUER, audience=_AUD)
    verify = build_hs256_verify(_SECRET, time_fn=lambda: now_state["t"])
    return JwtValidator(jwks_cache=cache, policy=policy, verify_fn=verify)


def _token(exp: int) -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": "s",
            "preferred_username": "alu",
            "exp": exp,
            "realm_access": {"roles": ["estudiante"]},
        },
        _SECRET,
    )


def test_handshake_sin_token_rechazado() -> None:
    now = _clock()
    with pytest.raises(UnauthenticatedError):
        authenticate_handshake(_validator(now), token=None)


def test_handshake_con_token_valido_acepta() -> None:
    now = _clock()
    principal = authenticate_handshake(_validator(now), token=_token(exp=5000))
    assert principal.id_institucional == "alu"


def test_revalidacion_corta_conexion_si_token_expira() -> None:
    now = _clock()
    validator = _validator(now)
    token = _token(exp=1500)
    revalidador = RealtimeRevalidator(
        validator, periodo_seg=60, time_fn=lambda: now["t"]
    )
    # Primera revalidacion: token aun vigente.
    revalidador.revalidar(token)
    # Avanza el reloj mas alla del exp del token.
    now["t"] = 2000.0
    with pytest.raises(UnauthenticatedError):
        revalidador.revalidar(token)  # el canal debe cortarse
