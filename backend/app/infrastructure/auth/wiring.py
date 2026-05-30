"""Composicion del subsistema de auth (infraestructura, C-06).

Arma el ``JwtValidator`` (JWKS cache + politica de claims + verificador RS256) a
partir de la config. Es el unico lugar que conoce el verificador concreto de
produccion (RS256/PyJWT); el resto del codigo depende de las abstracciones.

La descarga del JWKS usa ``urllib`` de la stdlib (sin httpx) para no exigir una
lib extra solo para un GET cacheado; en produccion corre detras de TLS hacia
Keycloak. Es perezosa: solo se descarga al primer uso / al expirar el cache.
"""

from __future__ import annotations

import json
import urllib.request

from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache, JwksDoc
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_rs256_verify


def _http_fetch_jwks(jwks_url: str) -> JwksDoc:
    """GET del documento JWKS de Keycloak (stdlib, perezoso)."""
    with urllib.request.urlopen(jwks_url, timeout=5) as resp:  # noqa: S310 - URL de config (Keycloak/TLS)
        return json.loads(resp.read().decode("utf-8"))


def build_jwt_validator(settings: Settings) -> JwtValidator:
    """Construye el ``JwtValidator`` de produccion desde la config."""
    cache = JwksCache(
        lambda: _http_fetch_jwks(settings.keycloak_jwks_url),
        ttl_seconds=settings.jwks_cache_ttl_seconds,
    )
    policy = TokenPolicy(issuer=settings.keycloak_issuer, audience=settings.jwt_audience)
    return JwtValidator(jwks_cache=cache, policy=policy, verify_fn=build_rs256_verify())
