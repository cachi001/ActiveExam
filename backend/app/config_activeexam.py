"""Configuracion activeexam para el modulo de proctoring deployable en Railway.

Solo requiere DATABASE_URL, FRONTEND_ORIGIN, JWT_OWN_SECRET y
EMBEDDING_ENCRYPTION_KEY. Sin Keycloak, Vault, MinIO, TimescaleDB ni OTLP.
Doce-factor: todo por entorno. Falla EXPLICITO si faltan las vars obligatorias.

PRODUCCION: este modulo activeexam es para demo/PoC. Para produccion real usar
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


class ActiveExamSettings(BaseSettings):
    """Settings del modulo activeexam. Falla con ValidationError si faltan vars obligatorias."""

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

    # --- Integridad de rendición (C-72 §1.8) ---
    # Gracia del deadline efectivo: tolerancia a latencia de red y desfasaje de
    # reloj, NO tiempo de examen. Es tolerancia server-side invisible; NUNCA se
    # expone al cliente ni se lee de él (regla dura #6). La UI corta en el límite
    # nominal. Default conservador 60s (arrancar acá y medir — design Open Q).
    deadline_gracia_seg: int = 60

    # --- Biometria (c-57) ---
    embedding_encryption_key: str  # Obligatorio. Clave Fernet. Sin default.

    # --- Moodle Write-back (C-69, D7/D10) ---
    # Opcional: si moodle_base_url está vacío, el write-back de notas queda deshabilitado.
    # El token es un secreto — NUNCA embeber en código ni commitear. Se inyecta vía
    # variable de entorno o secret manager.
    moodle_base_url: str = ""         # Ej: https://moodle.miinstituto.edu.ar
    moodle_ws_token: str = ""         # Token de Web Services de Moodle (secreto)
    moodle_courseid: int = 0          # ID del curso destino en Moodle
    moodle_cmid: int = 0              # ID del ítem de calificación (cm) en Moodle
    moodle_component: str = "mod_assign"  # C-73: módulo destino global ('mod_assign'|'mod_quiz')

    # --- MinIO / bucket WORM de evidencia (c-77) ---
    # TODAS opcionales, default None: Render arranca HOY sin VPS/MinIO, y el
    # arranque de la app NUNCA depende de esto (create_activeexam_app() las lee
    # detrás de minio_configurado() y cae a app.state.worm_storage = None si
    # faltan). Cuando el dueño levante la VPS con MinIO, alcanza con setear las 4.
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket_evidencia: str | None = None
    minio_use_ssl: bool = True

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
def get_activeexam_settings() -> ActiveExamSettings:
    """Singleton de ActiveExamSettings (cargado una vez del entorno)."""
    return ActiveExamSettings()


def minio_configurado(settings: ActiveExamSettings) -> bool:
    """True solo si las 4 variables MinIO obligatorias estan TODAS presentes.

    Pura y testeable: evita que la app arranque con el bucket WORM "a medias"
    (ej. endpoint sin credenciales) — o estan las 4, o el sistema se comporta
    exactamente como hoy (evidencia solo en Postgres, sin MinIO).
    """
    return bool(
        settings.minio_endpoint
        and settings.minio_access_key
        and settings.minio_secret_key
        and settings.minio_bucket_evidencia
    )
