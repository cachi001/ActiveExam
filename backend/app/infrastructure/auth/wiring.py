"""Composicion del subsistema de auth (infraestructura, C-06 / C-55).

Arma el ``JwtValidator`` a partir de la config. Es el unico lugar que conoce
los verificadores concretos de produccion; el resto del codigo depende de las
abstracciones.

JWT propio (HS256, unico mecanismo soportado): verifica con ``JWT_OWN_SECRET``
(secreto simetrico) y valida el issuer/audience configurados. Keycloak fue
ELIMINADO del dominio: el sistema autentica exclusivamente con JWT propio, no
hay wiring RS256/JWKS ni endpoint de terceros involucrado.
"""

from __future__ import annotations

from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify_production


def _jwks_fetch_no_soportado() -> dict:
    """JwksCache stub: este modulo es HS256-only, nunca deberia fetchear JWKS."""
    raise NotImplementedError(
        "El JwtValidator de app.main es HS256-only (JWT propio): no hay "
        "proveedor RS256/JWKS configurado."
    )


def build_jwt_validator(settings: Settings) -> JwtValidator:
    """Construye el ``JwtValidator`` HS256-only (JWT propio) desde la config."""
    policy = TokenPolicy(
        issuers_aceptados=frozenset({settings.jwt_own_issuer}),
        audience=settings.jwt_audience,
    )

    return JwtValidator(
        jwks_cache=JwksCache(fetch_jwks=_jwks_fetch_no_soportado, ttl_seconds=3600),
        policy=policy,
        verify_fn=build_hs256_verify_production(settings.jwt_own_secret),
        verify_fn_hs256=None,
        own_issuer=settings.jwt_own_issuer,
        rs256_issuer=None,
    )
