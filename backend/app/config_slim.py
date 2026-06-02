"""Configuracion slim para el modulo de proctoring deployable en Railway.

Solo requiere DATABASE_URL, FRONTEND_ORIGIN y PORT. Sin Keycloak, Vault,
MinIO, TimescaleDB ni OTLP. Doce-factor: todo por entorno.

PRODUCCION: este modulo slim es para demo/PoC. Para produccion real usar
``app.config.Settings`` con la pila completa (Keycloak, Vault, MinIO, etc.)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlimSettings(BaseSettings):
    """Settings minimas para el modulo slim. Falla si falta DATABASE_URL o FRONTEND_ORIGIN."""

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
