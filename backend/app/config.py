"""Configuracion twelve-factor de la aplicacion.

Toda la config se carga DESDE EL ENTORNO (DD-11). Los secretos
(``DATABASE_URL``, ``STORAGE_SECRET_KEY``, ``VAULT_TOKEN``, ...) se inyectan en
runtime via Vault en tmpfs efimero y NUNCA se hardcodean en la imagen Docker
(`08` Gestion de secretos). No hay defaults para campos sensibles ni para los
requeridos: si falta uno, la app falla EXPLICITAMENTE al arrancar (sin default
inseguro), cumpliendo el principio twelve-factor.

La pieza de mensajeria (``messaging_backend``) por OMISION es ``postgres`` (A4),
pero es swappable segun el veredicto de C-03. No se asume Redis/RabbitMQ.

# Modelo multi-provider de auth (C-55)
# ------------------------------------
# ``auth_provider`` selecciona el mecanismo de autenticacion activo:
#
#   "jwt" (default MVP self-hosted):
#     Requiere: ``jwt_own_secret`` (sensible, via Vault), ``jwt_own_issuer``,
#               ``refresh_token_ttl_seconds``.
#     El backend emite y verifica sus propios JWT HS256. Keycloak no es necesario.
#
#   "keycloak":
#     Requiere: ``keycloak_issuer``, ``keycloak_jwks_url``, ``jwt_audience``,
#               ``keycloak_token_url`` (para refresh).
#     El validador multi-issuer acepta AMBOS (jwt propio + Keycloak) siempre
#     que esten configurados; el provider elegido solo determina el flujo de login.
#
# Para exponer un endpoint JWKS propio (RS256 a escala) -> change futuro (DD-17).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings de la app. Falla al arrancar si falta config requerida."""

    model_config = SettingsConfigDict(
        env_file=None,  # en runtime la config viene del entorno (no de archivos)
        case_sensitive=False,
        extra="forbid",  # rechaza variables no declaradas (regla dura de codigo)
    )

    # --- App ---
    app_name: str = "proctoring-api"
    environment: Literal["local", "ci", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"

    # --- Base de datos (sensible: via Vault/tmpfs) ---
    database_url: str = Field(..., description="DSN PostgreSQL/TimescaleDB (async).")

    # --- Object storage MinIO/S3 ---
    storage_endpoint: str = Field(..., description="Endpoint MinIO/S3.")
    storage_access_key: str = Field(..., description="Access key (sensible).")
    storage_secret_key: str = Field(..., description="Secret key (sensible).")
    storage_bucket_evidence: str = Field(..., description="Bucket WORM de evidencia.")

    # --- Identidad (Keycloak) ---
    keycloak_issuer: str = Field(..., description="Issuer/realm de Keycloak.")
    keycloak_jwks_url: str = Field(..., description="Endpoint de claves publicas.")
    jwt_audience: str = Field(..., description="Audience esperado del JWT.")

    # --- Auth/JWT (C-06) ---
    # Access tokens cortos (15-60 min, `08` §Seguridad). El valor concreto lo fija
    # Keycloak; aqui se declara para validacion/documentacion. TTL del cache JWKS
    # para validar localmente sin round-trip por request (D2).
    access_token_ttl_seconds: int = Field(
        default=900, ge=900, le=3600, description="Vida del access token (15-60 min)."
    )
    jwks_cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="TTL del cache JWKS (refresco perezoso)."
    )
    # Periodo de revalidacion del token en canales de larga vida (WS/SSE, D5).
    realtime_revalidation_seconds: int = Field(
        default=60, ge=10, description="Cada cuanto se revalida el JWT en WS/SSE."
    )
    # Endpoint del token de Keycloak (grant refresh_token); sensible-ish, va por env.
    keycloak_token_url: str | None = Field(
        default=None, description="Token endpoint de Keycloak (refresh grant)."
    )

    # --- Auth provider propio (C-55) ---
    # El issuer se recomienda como string fijo (no URI) para evitar dependencia del
    # dominio de hosting (aun no estable en staging). Valor sugerido: "activeexam-auth".
    auth_provider: Literal["jwt", "keycloak"] = "jwt"
    jwt_own_secret: str | None = Field(
        default=None,
        description=(
            "Secreto HS256 (256+ bits, sensible — via Vault/tmpfs). "
            "Obligatorio cuando auth_provider='jwt'. Si ausente con provider jwt, "
            "el endpoint de login falla con 500 explicito (sin default inseguro)."
        ),
    )
    jwt_own_issuer: str = Field(
        default="activeexam-auth",
        description="Claim 'iss' de los tokens propios (string fijo, no URI — C-55 D1).",
    )
    refresh_token_ttl_seconds: int = Field(
        default=604800,  # 7 dias (C-55 — resuelto por el dueno)
        ge=3600,
        description="TTL del refresh token en segundos (default 7 dias).",
    )

    # --- Observabilidad (OpenTelemetry) ---
    otel_exporter_otlp_endpoint: str = Field(
        ..., description="Colector OTLP (Tempo)."
    )
    otel_service_name: str = "proctoring-api"

    # --- Mensajeria (pieza decidida por C-03; default A4 = postgres) ---
    messaging_backend: Literal["postgres", "rabbitmq", "redis"] = "postgres"

    # --- Gestion de secretos (Vault) ---
    # Opcionales: en local la inyeccion puede no estar activa. En prod son
    # obligatorias operacionalmente, pero NO deben tener default inseguro de
    # valor: por eso solo se declara el contrato, sin secreto embebido.
    vault_addr: str | None = Field(default=None, description="Direccion de Vault.")
    vault_token: str | None = Field(
        default=None, description="Token de Vault (inyectado en arranque)."
    )


@lru_cache
def get_settings() -> Settings:
    """Devuelve el singleton de Settings (cargado una vez del entorno)."""
    return Settings()
