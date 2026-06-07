"""Composicion del JwtValidator HS256-only para el modulo slim (c-57, D3).

``build_slim_jwt_validator`` construye un ``JwtValidator`` que SOLO valida
tokens HS256 firmados con el secreto propio (``jwt_own_secret``). Sin Keycloak,
sin JWKS, sin red.

Diferencia con ``wiring.py`` (full):
  - wiring.py: importa ``Settings`` (requiere las 9+ vars del full), arma
    JWKS cache con URL de Keycloak, soporte RS256 + HS256.
  - slim_wiring.py: importa ``SlimSettings`` (solo las vars del slim), arma
    un JwksCache stub (no-op para RS256), soporte HS256-only.

OQ-1 (design.md): ``JwtValidator.__init__`` toma ``jwks_cache: JwksCache``
sin tipo ``Optional``. En modo HS256-only el validator nunca llama
``jwks_cache.get_jwk()`` (la rama RS256 solo se activa si ``verify_fn_hs256``
es None, lo que no ocurre en el slim). Para cumplir el contrato del tipo sin
modificar ``JwtValidator``, se inyecta un ``JwksCache`` stub cuyo ``fetch_jwks``
lanza ``NotImplementedError`` si fuera llamado (defensa de desarrollo).
"""

from __future__ import annotations

from app.config_slim import SlimSettings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify_production


def _stub_jwks_fetch() -> dict:
    """Fetch stub para el JwksCache del slim.

    En modo HS256-only el JwtValidator NUNCA llama a jwks_cache.get_jwk()
    (la rama RS256 esta inactiva porque verify_fn_hs256 es distinto de None).
    Este stub levanta NotImplementedError como defensa de desarrollo: si por
    algun bug de regresion el validador intentara resolver RS256 en el slim,
    falla de forma ruidosa y detectable (no silenciosa).
    """
    raise NotImplementedError(
        "El JwksCache del modulo slim no debe fetchear JWKS: "
        "el slim es HS256-only y no tiene Keycloak. "
        "Si ves este error, hay una regresion en el despacho de alg/iss."
    )


def build_slim_jwt_validator(settings: SlimSettings) -> JwtValidator:
    """Construye el JwtValidator HS256-only para el modulo slim.

    Args:
        settings: SlimSettings ya inicializado con jwt_own_secret,
                  jwt_own_issuer y jwt_audience.

    Returns:
        ``JwtValidator`` configurado para aceptar UNICAMENTE tokens HS256
        firmados con ``settings.jwt_own_secret`` e issuer
        ``settings.jwt_own_issuer``. Rechaza cualquier otro alg/iss.
    """
    # Stub de JwksCache (RS256 nunca se usa en el slim — ver OQ-1 en design.md).
    jwks_cache_stub = JwksCache(
        fetch_jwks=_stub_jwks_fetch,
        ttl_seconds=3600,
    )

    policy = TokenPolicy(
        issuers_aceptados=frozenset({settings.jwt_own_issuer}),
        audience=settings.jwt_audience,
    )

    verify_fn_hs256 = build_hs256_verify_production(settings.jwt_own_secret)

    # JwtValidator en modo HS256-only:
    # - verify_fn_hs256 != None  -> activa el despacho multi-issuer C-55.
    # - own_issuer = jwt_own_issuer -> el unico issuer aceptado.
    # - keycloak_issuer = None   -> ninguna combinacion RS256 es valida.
    # - verify_fn (RS256) = una funcion que levanta UnauthenticatedError:
    #   en modo multi-issuer solo se llama si alg==RS256 y
    #   iss==keycloak_issuer; como keycloak_issuer=None, eso NUNCA ocurre.
    #   Pasamos la funcion del stub por compatibilidad de tipo.
    return JwtValidator(
        jwks_cache=jwks_cache_stub,
        policy=policy,
        verify_fn=_rs256_desactivado,
        verify_fn_hs256=verify_fn_hs256,
        own_issuer=settings.jwt_own_issuer,
        keycloak_issuer=None,  # Keycloak no existe en el slim
    )


def _rs256_desactivado(token: str, jwk: dict | None, audience: str, issuer: str) -> dict:
    """VerifyFn RS256 desactivado para el slim.

    En modo multi-issuer con keycloak_issuer=None, esta funcion NUNCA se llama
    (el despacho en JwtValidator solo invoca verify_fn si alg==RS256 y
    iss==keycloak_issuer; keycloak_issuer=None nunca coincide con un iss real).
    Se incluye como guardia defensiva por si hay una regresion futura.
    """
    from app.domain.auth.errors import UnauthenticatedError

    raise UnauthenticatedError(
        "RS256 no esta soportado en el modulo slim (solo HS256). "
        "Verifica que el token es de tipo JWT propio (iss=activeexam-auth, alg=HS256)."
    )
