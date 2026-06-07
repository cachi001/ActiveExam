"""006 - C-55: auth provider JWT propio — paso 1 (no destructivo).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-06

Scope (C-55, auth-provider-jwt-propio). Migracion en DOS PASOS (regla dura del
proyecto: expand/contract sin downtime).

PASO 1 (esta migracion — no destructivo, deployable sin downtime):
  - ADD COLUMN password_hash TEXT (nullable) en tabla ``usuario``.
  - ADD COLUMN auth_provider TEXT DEFAULT 'keycloak' en tabla ``usuario``.
  - CREATE TABLE refresh_tokens (jwt propio, rotacion).
  - Indices en refresh_tokens para lookup y cleanup eficiente.

PASO 2 (no aplica en este change):
  No se agrega NOT NULL porque los usuarios federados via Keycloak
  legitimamente no tienen password local (password_hash IS NULL significa
  "no tiene credencial local — usa Keycloak/SAML"). No hay backfill requerido.
  Un change futuro podra agregar NOT NULL si se migra a provider-only local.

DOWNGRADE: revierte exactamente lo creado (DROP TABLE, DROP COLUMN) — es
  seguro porque las columnas son aditivas y la tabla es nueva.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str = "0004"
branch_labels = None
# c-55 (auth JWT propio) pertenece al backend FULL (main.py, con TimescaleDB), NO al
# slim de Railway (main_slim es "REST sin auth"). Por eso cuelga de la rama PRINCIPAL
# (0004), que ya trae la tabla usuario via 0002. Asi `alembic upgrade slim@head`
# (Railway, Postgres pelado) NO corre esta migracion y no arrastra 0001
# (CREATE EXTENSION timescaledb), que el Postgres de Railway rechaza.
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # PASO 1: columnas de autenticacion local en tabla usuario
    # -------------------------------------------------------------------------
    # password_hash nullable: NULL = usuario federado (Keycloak/SAML);
    # NOT NULL = usuario con credencial local. Ver doc paso 2 arriba.
    op.add_column(
        "usuario",
        sa.Column("password_hash", sa.Text(), nullable=True),
    )
    # auth_provider: indica el mecanismo de autenticacion del registro.
    # 'keycloak' = federado via OIDC/SAML; 'local' = credencial propia.
    op.add_column(
        "usuario",
        sa.Column(
            "auth_provider",
            sa.Text(),
            nullable=False,
            server_default="keycloak",
        ),
    )

    # -------------------------------------------------------------------------
    # PASO 1: tabla refresh_tokens (nueva, no destructiva)
    # -------------------------------------------------------------------------
    # jti: identificador opaco del token (secrets.token_urlsafe(32)).
    # usuario_id: FK CASCADE DELETE para limpiar al borrar el usuario.
    # expires_at: TIMESTAMPTZ para invalidacion por tiempo.
    # rotado_en: NULL = vigente; NOT NULL = ya rotado (reuso -> 401).
    # created_at: auditoria.
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("jti", sa.Text(), nullable=False),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("rotado_en", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # UNIQUE en jti: garantia de unicidad para lookup rapido y deteccion de reuso.
    op.create_index("uq_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)

    # Indices adicionales para queries frecuentes:
    # - por usuario: revocar todos los tokens de un usuario (logout global).
    # - por expires_at: cleanup periodico de expirados (job pg-boss o cron).
    op.create_index("ix_refresh_tokens_usuario_id", "refresh_tokens", ["usuario_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    # Revierte en orden inverso (primero tabla, luego columnas).
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_usuario_id", table_name="refresh_tokens")
    op.drop_index("uq_refresh_tokens_jti", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("usuario", "auth_provider")
    op.drop_column("usuario", "password_hash")
