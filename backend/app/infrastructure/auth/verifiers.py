"""Fabricas de ``VerifyFn`` para ``JwtValidator`` (infraestructura, C-06 D2 / C-55).

Tres implementaciones de la verificacion criptografica:

- ``build_rs256_verify``: PRODUCCION Keycloak. Usa PyJWT + la JWK (RS256) del JWKS
  de Keycloak. Import perezoso: si PyJWT no esta instalado, falla EXPLICITO al
  construir el verificador, no al importar el modulo.
- ``build_hs256_verify_production``: PRODUCCION JWT propio (C-55). Usa PyJWT con
  HS256 + secreto del backend. Import perezoso identico al RS256.
- ``build_hs256_verify``: SOLO TEST. Verifica HMAC-SHA256 con stdlib (sin PyJWT,
  sin red). Para testear el flujo completo sin el stack.

Todas levantan ``UnauthenticatedError`` (-> 401) ante cualquier fallo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable

from app.domain.auth.errors import UnauthenticatedError
from app.infrastructure.auth.jwt_validator import VerifyFn, _b64url_decode


def build_rs256_verify() -> VerifyFn:
    """Verificador RS256 de PRODUCCION (PyJWT + JWK del JWKS). Import perezoso."""
    try:
        import jwt  # PyJWT
        from jwt.algorithms import RSAAlgorithm
    except ModuleNotFoundError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "PyJWT no esta instalado: agregue 'pyjwt[crypto]' a las dependencias "
            "para validar JWT RS256 en produccion (C-06)."
        ) from exc

    def verify(token: str, jwk: dict | None, audience: str, issuer: str) -> dict:
        if jwk is None:
            raise UnauthenticatedError("No hay JWK para el kid del token (firma no verificable).")
        try:
            public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))
            return jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "aud", "iss"]},
            )
        except UnauthenticatedError:
            raise
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de la lib -> 401
            raise UnauthenticatedError(f"JWT invalido: {exc}") from exc

    return verify


def build_hs256_verify_production(secret: str) -> VerifyFn:
    """Verificador HS256 de PRODUCCION para el provider JWT propio (C-55).

    Usa PyJWT con algoritmo HS256 y el secreto ``JWT_OWN_SECRET``. Import
    perezoso: si PyJWT no esta disponible, falla EXPLICITO al construir el
    verificador (no al importar el modulo).

    A diferencia de ``build_hs256_verify`` (stdlib, solo tests), esta version
    verifica correctamente el campo ``aud`` como PyJWT espera (string o lista).
    """
    try:
        import jwt  # PyJWT  # noqa: PLC0415
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyJWT no esta instalado: agregue 'pyjwt[crypto]' a las dependencias "
            "para verificar JWT HS256 en produccion (C-55)."
        ) from exc

    def verify(token: str, jwk: dict | None, audience: str, issuer: str) -> dict:
        # jwk no se usa en HS256 (el secreto es simetrico, no es JWK).
        try:
            return jwt.decode(
                token,
                key=secret,
                algorithms=["HS256"],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "aud", "iss"]},
            )
        except UnauthenticatedError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise UnauthenticatedError(f"JWT HS256 invalido: {exc}") from exc

    return verify


def build_hs256_verify(
    secret: bytes,
    *,
    time_fn: Callable[[], float] = time.time,
) -> VerifyFn:
    """Verificador HS256 para TEST (HMAC stdlib, sin PyJWT ni red).

    Verifica: estructura, firma HMAC-SHA256, ``exp`` (si presente). La audiencia y
    el issuer los re-chequea ``TokenPolicy`` en dominio; aqui se valida lo
    criptografico + expiracion, espejando lo que hace PyJWT en produccion."""

    def verify(token: str, jwk: dict | None, audience: str, issuer: str) -> dict:
        try:
            header_b64, payload_b64, sig_b64 = token.split(".")
        except ValueError as exc:
            raise UnauthenticatedError("JWT mal formado (no tiene 3 segmentos).") from exc

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        esperada = hmac.new(secret, signing_input, hashlib.sha256).digest()
        recibida = _b64url_decode(sig_b64)
        if not hmac.compare_digest(esperada, recibida):
            raise UnauthenticatedError("Firma HS256 invalida.")

        claims = json.loads(_b64url_decode(payload_b64))
        exp = claims.get("exp")
        if exp is not None and time_fn() >= float(exp):
            raise UnauthenticatedError("Token expirado.")
        return claims

    return verify


def encode_hs256(claims: dict, secret: bytes) -> str:
    """Codifica un JWT HS256 (SOLO para tests/fixtures, no produccion)."""

    def _seg(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = _seg({"alg": "HS256", "typ": "JWT", "kid": "test-key"})
    payload = _seg(claims)
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{header}.{payload}.{sig_b64}"
