"""Configuracion slim para el modulo de proctoring deployable en Railway.

Solo requiere DATABASE_URL, FRONTEND_ORIGIN, JWT_OWN_SECRET y
EMBEDDING_ENCRYPTION_KEY. Sin Keycloak, Vault, MinIO, TimescaleDB ni OTLP.
Doce-factor: todo por entorno. Falla EXPLICITO si faltan las vars obligatorias.

PRODUCCION: este modulo slim es para demo/PoC. Para produccion real usar
``app.config.Settings`` con la pila completa (Keycloak, Vault, MinIO, etc.)

Variables requeridas (Railway dashboard):
  DATABASE_URL            - postgresql://user:pass@host:5432/db
  FRONTEND_ORIGIN         - https://activeexam.vercel.app
  JWT_OWN_SECRET          - string aleatorio seguro (>= 32 bytes)
                            generarlo: python -c "import secrets; print(secrets.token_urlsafe(32))"
  EMBEDDING_ENCRYPTION_KEY - clave Fernet valida
                            generarla: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Variables opcionales (con defaults):
  JWT_OWN_ISSUER           - default: "activeexam-auth"
  JWT_AUDIENCE             - default: "activeexam"
  ACCESS_TOKEN_TTL_SECONDS - default: 900 (15 minutos)
  REFRESH_TOKEN_TTL_SECONDS- default: 604800 (7 dias)
  AUTH_PROVIDER            - default: "jwt"
  PORT                     - default: 8000 (Railway inyecta PORT automaticamente)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlimSettings(BaseSettings):
    """Settings del modulo slim. Falla con ValidationError si faltan vars obligatorias."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="forbid",  # Regla dura de codigo: rechaza variables no declaradas
    )

    # --- Base de datos ---
    database_url: str  # Requerida. Ej: postgresql+asyncpg://user:pass@host:5432/db

    # --- CORS ---
    frontend_origin: str  # Requerida. Ej: https://activeexam.vercel.app

    # --- Servidor ---
    port: int = 8000  # Railway inyecta PORT automaticamente

    # --- Auth JWT propia (c-57) ---
    auth_provider: str = "jwt"
    jwt_own_secret: str  # Obligatorio. Sin default: Railway lo inyecta.
    jwt_own_issuer: str = "activeexam-auth"
    jwt_audience: str = "activeexam"
    access_token_ttl_seconds: int = 900      # 15 minutos
    refresh_token_ttl_seconds: int = 604800  # 7 dias

    # --- Biometria (c-57) ---
    embedding_encryption_key: str  # Obligatorio. Clave Fernet. Sin default.

    @field_validator("database_url")
    @classmethod
    def _normalizar_a_asyncpg(cls, valor: str) -> str:
        """Normaliza la URL al driver async (asyncpg) que exige create_async_engine.

        Railway inyecta DATABASE_URL como ``postgresql://...`` (o el viejo
        ``postgres://...``), sin sufijo de driver. El engine async de SQLAlchemy
        REQUIERE un driver async; con ``postgresql://`` levanta psycopg2 (sync) y
        falla con "The asyncio extension requires an async driver". Aca lo forzamos
        a ``postgresql+asyncpg://``. Alembic corre aparte (migrations/env.py) y vuelve
        a derivar el driver sync, asi que esta normalizacion no le afecta.
        """
        if valor.startswith("postgres://"):
            valor = "postgresql://" + valor[len("postgres://"):]
        if valor.startswith("postgresql://"):
            valor = "postgresql+asyncpg://" + valor[len("postgresql://"):]
        return valor


@lru_cache
def get_slim_settings() -> SlimSettings:
    """Singleton de SlimSettings (cargado una vez del entorno)."""
    return SlimSettings()
