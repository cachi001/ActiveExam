"""Configuracion slim para el modulo de proctoring deployable en Railway.

Solo requiere DATABASE_URL, FRONTEND_ORIGIN y PORT. Sin Keycloak, Vault,
MinIO, TimescaleDB ni OTLP. Doce-factor: todo por entorno.

PRODUCCION: este modulo slim es para demo/PoC. Para produccion real usar
``app.config.Settings`` con la pila completa (Keycloak, Vault, MinIO, etc.)
"""

from __future__ import annotations

from functools import lru_cache

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


@lru_cache
def get_slim_settings() -> SlimSettings:
    """Singleton de SlimSettings (cargado una vez del entorno)."""
    return SlimSettings()
