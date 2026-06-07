"""Composicion del subsistema de auth (infraestructura, C-06 / C-55).

Arma el ``JwtValidator`` multi-issuer (JWKS cache + politica multi-issuer +
verificadores RS256 y HS256) a partir de la config. Es el unico lugar que
conoce los verificadores concretos de produccion; el resto del codigo depende
de las abstracciones.

Modo multi-issuer (C-55 — default MVP):
  - HS256 (JWT propio): verifica con ``JWT_OWN_SECRET`` (secreto simetrico).
  - RS256 (Keycloak): verifica con JWKS cacheado (comportamiento C-06).
  La seleccion es por ``iss`` + ``alg`` del token, sin exponer los issuers
  configurados en el error (defensa en profundidad).

Modo legacy (C-06):
  Si ``jwt_own_secret`` no esta configurado, el validador solo acepta RS256
  de Keycloak (comportamiento identico al original — retrocompatibilidad).

La descarga del JWKS usa ``urllib`` de la stdlib (perezosa, sin httpx).
"""

from __future__ import annotations

import json
import urllib.request

from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache, JwksDoc
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify_production, build_rs256_verify


def _http_fetch_jwks(jwks_url: str) -> JwksDoc:
    """GET del documento JWKS de Keycloak (stdlib, perezoso)."""
    with urllib.request.urlopen(jwks_url, timeout=5) as resp:  # noqa: S310 - URL de config (Keycloak/TLS)
        return json.loads(resp.read().decode("utf-8"))


def build_jwt_validator(settings: Settings) -> JwtValidator:
    """Construye el ``JwtValidator`` multi-issuer de produccion desde la config.

    Si ``jwt_own_secret`` esta configurado: modo multi-issuer (HS256 propio +
    RS256 Keycloak). Si no: modo legacy C-06 (solo RS256 Keycloak).
    """
    cache = JwksCache(
        lambda: _http_fetch_jwks(settings.keycloak_jwks_url),
        ttl_seconds=settings.jwks_cache_ttl_seconds,
    )

    # Construir el set de issuers aceptados segun la config.
    issuers: set[str] = {settings.keycloak_issuer}
    if settings.jwt_own_secret:
        issuers.add(settings.jwt_own_issuer)

    policy = TokenPolicy(
        issuers_aceptados=frozenset(issuers),
        audience=settings.jwt_audience,
    )

    # Modo multi-issuer (C-55): si hay secreto propio, agregar el verify_fn HS256.
    verify_fn_hs256 = None
    if settings.jwt_own_secret:
        verify_fn_hs256 = build_hs256_verify_production(settings.jwt_own_secret)

    return JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=build_rs256_verify(),
        verify_fn_hs256=verify_fn_hs256,
        own_issuer=settings.jwt_own_issuer if settings.jwt_own_secret else None,
        keycloak_issuer=settings.keycloak_issuer,
    )
