"""Tests unitarios: ActiveExamSettings extendida (c-57, task 2.3).

Verifica que ActiveExamSettings falla con ValidationError si faltan
jwt_own_secret o embedding_encryption_key.

Sin DB, sin red — unitarios puros.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_activeexam_settings_sin_jwt_own_secret_lanza_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2.3: ActiveExamSettings sin JWT_OWN_SECRET lanza ValidationError.

    Limpia explicitamente JWT_OWN_SECRET del entorno para que pydantic-settings
    no lo lea aunque este definido en el shell del stack de tests.
    """
    import app.config_activeexam as config_activeexam_module  # noqa: PLC0415

    config_activeexam_module.get_activeexam_settings.cache_clear()

    # Asegurar que JWT_OWN_SECRET NO esta en el entorno para este test.
    monkeypatch.delenv("JWT_OWN_SECRET", raising=False)

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app@localhost:5432/test")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", "dGVzdC1rZXktZmVybmV0LWtleS0zMi1ieXRlcw==")
    # NO seteamos JWT_OWN_SECRET — debe fallar con ValidationError.

    from app.config_activeexam import ActiveExamSettings

    with pytest.raises(ValidationError, match="jwt_own_secret"):
        ActiveExamSettings(
            database_url="postgresql+asyncpg://app@localhost:5432/test",
            frontend_origin="http://localhost:5173",
            embedding_encryption_key="dGVzdC1rZXktZmVybmV0LWtleS0zMi1ieXRlcw==",
        )


def test_activeexam_settings_sin_embedding_encryption_key_lanza_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2.3: ActiveExamSettings sin EMBEDDING_ENCRYPTION_KEY lanza ValidationError.

    Limpia explicitamente EMBEDDING_ENCRYPTION_KEY del entorno para que
    pydantic-settings no lo lea aunque este definido en el shell del stack.
    """
    import app.config_activeexam as config_activeexam_module  # noqa: PLC0415

    config_activeexam_module.get_activeexam_settings.cache_clear()

    # Asegurar que EMBEDDING_ENCRYPTION_KEY NO esta en el entorno para este test.
    monkeypatch.delenv("EMBEDDING_ENCRYPTION_KEY", raising=False)

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app@localhost:5432/test")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("JWT_OWN_SECRET", "super-secret-at-least-32-bytes-long-string")
    # NO seteamos EMBEDDING_ENCRYPTION_KEY — debe fallar con ValidationError.

    from app.config_activeexam import ActiveExamSettings

    with pytest.raises(ValidationError, match="embedding_encryption_key"):
        ActiveExamSettings(
            database_url="postgresql+asyncpg://app@localhost:5432/test",
            frontend_origin="http://localhost:5173",
            jwt_own_secret="super-secret-at-least-32-bytes-long-string",
        )


def test_activeexam_settings_con_campos_obligatorios_no_lanza() -> None:
    """2.2: ActiveExamSettings valida correctamente con todas las vars requeridas."""
    from cryptography.fernet import Fernet

    from app.config_activeexam import ActiveExamSettings

    clave = Fernet.generate_key().decode()
    settings = ActiveExamSettings(
        database_url="postgresql+asyncpg://app@localhost:5432/test",
        frontend_origin="http://localhost:5173",
        jwt_own_secret="super-secret-at-least-32-bytes-long-string",
        embedding_encryption_key=clave,
    )
    assert settings.auth_provider == "jwt"
    assert settings.jwt_own_issuer == "activeexam-auth"
    assert settings.jwt_audience == "activeexam"
    assert settings.access_token_ttl_seconds == 900
    assert settings.refresh_token_ttl_seconds == 604800


def test_activeexam_settings_extra_field_rechazado() -> None:
    """2.2: extra='forbid' rechaza campos no declarados (regla dura de codigo)."""
    from cryptography.fernet import Fernet

    from app.config_activeexam import ActiveExamSettings

    clave = Fernet.generate_key().decode()
    with pytest.raises(ValidationError):
        ActiveExamSettings(
            database_url="postgresql+asyncpg://app@localhost:5432/test",
            frontend_origin="http://localhost:5173",
            jwt_own_secret="super-secret-at-least-32-bytes-long-string",
            embedding_encryption_key=clave,
            campo_no_declarado="valor",  # type: ignore[call-arg]
        )
