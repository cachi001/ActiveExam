"""007 - C-56: persistencia biometrica de referencia — paso 1 (no destructivo).

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06

Scope (C-56, persistencia-biometrica-referencia). Migracion en DOS PASOS (regla
dura del proyecto: expand/contract sin downtime).

PASO 1 (esta migracion — no destructivo, deployable sin downtime):
  - CREATE TABLE foto_referencia (FK a usuario.id ON DELETE CASCADE).
  - CREATE TABLE embedding_referencia (FK a usuario.id ON DELETE CASCADE).
  - Indices en usuario_id y vigente para ambas tablas.

Las dos tablas son NUEVAS: no se modifica ninguna tabla existente. No hay NOT NULL
sobre columnas existentes. No requiere backfill. Deployable sin downtime.

PASO 2: no aplica en este change. Las tablas son nuevas, no hay contrato
de columnas existentes que modificar. Si en el futuro se agrega una restriccion
NOT NULL sobre datos existentes, se haria en un segundo paso separado.

DOWNGRADE: revierte exactamente lo creado (DROP TABLE en orden inverso).
Es seguro porque las tablas son aditivas.

DEPENDENCIAS:
  - Revises 0006: ultima de la rama slim (C-55, auth JWT propio).
  - depends_on 0002: crea la tabla `usuario` (rama principal). Sin esto, el deploy
    slim falla porque foto_referencia y embedding_referencia hacen FK a usuario.
    Mismo patron que 0006. Ver bug documentado en engram.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str = "0006"
branch_labels = None
# 0007 (c-56 biometria) sigue a 0006 en la rama PRINCIPAL (full, con TimescaleDB).
# La tabla usuario ya existe via 0002 en esa cadena. NO cuelga de la rama slim: el
# slim de Railway (main_slim, "REST sin auth") no usa enrollment ni la tabla usuario,
# por eso `alembic upgrade slim@head` no debe correr esta migracion.
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # PASO 1: CREATE TABLE foto_referencia
    # -------------------------------------------------------------------------
    # Foto de perfil del alumno (mutable, renovable). Bucket no-WORM, separado
    # del bucket de evidencia WORM (D1 del design). Hash SHA-256 permite
    # verificar integridad sin Object Lock.
    op.create_table(
        "foto_referencia",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("uri_storage", sa.Text(), nullable=False),
        sa.Column("hash_sha256", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column(
            "vigente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indices para lookup por usuario y filtrando vigentes.
    op.create_index("ix_foto_referencia_usuario_id", "foto_referencia", ["usuario_id"])
    op.create_index("ix_foto_referencia_vigente", "foto_referencia", ["vigente"])

    # -------------------------------------------------------------------------
    # PASO 1: CREATE TABLE embedding_referencia
    # -------------------------------------------------------------------------
    # Embedding biometrico de referencia del alumno. Cifrado at-rest con Fernet
    # (AES-128-CBC + HMAC-SHA256) usando EMBEDDING_ENCRYPTION_KEY (D2).
    # eliminado_en: stub de retencion — NULL = no eliminado; NOT NULL = marcado
    # para eliminacion al egreso. La ejecucion real es C-19.
    op.create_table(
        "embedding_referencia",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("embedding_cifrado", sa.Text(), nullable=False),
        sa.Column(
            "algoritmo",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'face-api-128d'"),
        ),
        sa.Column(
            "fecha_captura",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("fecha_expiracion", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "vigente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("eliminado_en", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indices para lookup por usuario y filtrando vigentes.
    op.create_index(
        "ix_embedding_referencia_usuario_id", "embedding_referencia", ["usuario_id"]
    )
    op.create_index(
        "ix_embedding_referencia_vigente", "embedding_referencia", ["vigente"]
    )


def downgrade() -> None:
    # Revierte en orden inverso (primero la mas dependiente, luego la otra).
    op.drop_index("ix_embedding_referencia_vigente", table_name="embedding_referencia")
    op.drop_index(
        "ix_embedding_referencia_usuario_id", table_name="embedding_referencia"
    )
    op.drop_table("embedding_referencia")
    op.drop_index("ix_foto_referencia_vigente", table_name="foto_referencia")
    op.drop_index("ix_foto_referencia_usuario_id", table_name="foto_referencia")
    op.drop_table("foto_referencia")
