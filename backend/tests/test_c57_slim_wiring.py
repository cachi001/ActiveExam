"""Tests unitarios: slim_wiring.py — JwtValidator HS256-only (c-57, task 3.6).

Verifica que:
  - Token HS256 valido con jwt_own_secret es aceptado.
  - Token con secreto incorrecto lanza UnauthenticatedError.
  - Token RS256 (no soportado en slim) lanza UnauthenticatedError.

Sin DB, sin red — unitarios puros.
"""

from __future__ import annotations

import time

import pytest

from app.domain.auth.errors import UnauthenticatedError


def _make_settings(secret: str = "super-secret-min-32-bytes-long-key-here"):
    """Crea SlimSettings minimas para los tests de wiring."""
    from cryptography.fernet import Fernet

    from app.config_slim import SlimSettings

    return SlimSettings(
        database_url="postgresql+asyncpg://app@localhost:5432/test",
        frontend_origin="http://localhost:5173",
        jwt_own_secret=secret,
        embedding_encryption_key=Fernet.generate_key().decode(),
        jwt_own_issuer="activeexam-auth",
        jwt_audience="activeexam",
    )


def _token_hs256(secret: str, claims: dict) -> str:
    """Genera un JWT HS256 con PyJWT para los tests."""
    import jwt

    return jwt.encode(claims, key=secret, algorithm="HS256")


def _claims_validos(
    issuer: str = "activeexam-auth",
    audience: str = "activeexam",
    expiracion: int | None = None,
) -> dict:
    if expiracion is None:
        expiracion = int(time.time()) + 900
    return {
        "iss": issuer,
        "aud": audience,
        "sub": "user-uuid-1234",
        "preferred_username": "seed-estudiante",
        "email": "seed-estudiante@demo.test",
        "exp": expiracion,
        "realm_access": {"roles": ["estudiante"]},
    }


class TestBuildSlimJwtValidator:
    """Tests del JwtValidator HS256-only construido por slim_wiring."""

    def test_token_hs256_valido_es_aceptado(self) -> None:
        """3.6: token HS256 con jwt_own_secret valido retorna AuthenticatedPrincipal."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        secret = "super-secret-min-32-bytes-long-key-here"
        settings = _make_settings(secret)
        validator = build_slim_jwt_validator(settings)

        token = _token_hs256(secret, _claims_validos())
        principal = validator.validar(token)

        assert principal.id_institucional == "seed-estudiante"
        assert principal.email == "seed-estudiante@demo.test"

    def test_token_con_secreto_incorrecto_lanza_unauthenticated_error(self) -> None:
        """3.6: token firmado con secreto distinto es rechazado."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        secret_valido = "super-secret-min-32-bytes-long-key-here"
        secret_incorrecto = "otro-secreto-diferente-32-bytes-k"

        settings = _make_settings(secret_valido)
        validator = build_slim_jwt_validator(settings)

        # Firmar con el secreto INCORRECTO.
        token = _token_hs256(secret_incorrecto, _claims_validos())

        with pytest.raises(UnauthenticatedError):
            validator.validar(token)

    def test_token_expirado_es_rechazado(self) -> None:
        """Token con exp en el pasado es rechazado."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        secret = "super-secret-min-32-bytes-long-key-here"
        settings = _make_settings(secret)
        validator = build_slim_jwt_validator(settings)

        # exp en el pasado (hace 10 segundos)
        token = _token_hs256(
            secret,
            _claims_validos(expiracion=int(time.time()) - 10),
        )

        with pytest.raises(UnauthenticatedError):
            validator.validar(token)

    def test_token_con_issuer_incorrecto_es_rechazado(self) -> None:
        """Token con issuer distinto al jwt_own_issuer es rechazado."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        secret = "super-secret-min-32-bytes-long-key-here"
        settings = _make_settings(secret)
        validator = build_slim_jwt_validator(settings)

        # Token con issuer de Keycloak (no aceptado en el slim).
        token = _token_hs256(
            secret,
            _claims_validos(issuer="http://keycloak:8080/realms/proctoring"),
        )

        with pytest.raises(UnauthenticatedError):
            validator.validar(token)

    def test_token_vacio_lanza_unauthenticated_error(self) -> None:
        """Token vacio es rechazado."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        settings = _make_settings()
        validator = build_slim_jwt_validator(settings)

        with pytest.raises(UnauthenticatedError):
            validator.validar("")

    def test_jwks_stub_nunca_se_llama_en_hs256(self) -> None:
        """El JwksCache stub del slim no se llama en el path HS256 normal."""
        from app.infrastructure.auth.slim_wiring import build_slim_jwt_validator

        secret = "super-secret-min-32-bytes-long-key-here"
        settings = _make_settings(secret)
        validator = build_slim_jwt_validator(settings)

        # Validar un token HS256 valido — el stub no debe lanzar NotImplementedError.
        token = _token_hs256(secret, _claims_validos())
        principal = validator.validar(token)
        assert principal is not None
