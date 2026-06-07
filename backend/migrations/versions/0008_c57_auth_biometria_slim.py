"""008 - auth, usuarios y biometria para el modulo slim (Railway / Postgres estandar).

Revision ID: 0008
Revises: 0005 (branch slim - NO depende de 0001..0007 de la rama principal)
Create Date: 2026-06-07

RAMA: slim
  down_revision = "0005"   <- solo la rama slim, no la principal
  branch_labels = None     <- ya esta en la rama slim por herencia de 0005
  depends_on    = None     <- cero dependencia de la rama principal

PROPOSITO:
  Crea las 4 tablas que el slim necesita para auth JWT propia + enrollment
  biometrico, usando UNICAMENTE tipos Postgres estandar. SIN TimescaleDB,
  SIN hypertables, SIN extensiones propietarias.

  NOTA DE DISENO (c-57 D2): la tabla ``usuario`` tambien existe en la historia
  de la rama principal (0002). Son INDEPENDIENTES por rama Alembic. En Railway
  solo existe la rama slim; en produccion full solo existe la rama principal.
  El ORM mapea al mismo nombre de tabla fisico (``usuario``); en cada entorno
  hay exactamente una. Esto es intencional y documentado.

PASOS:
  Paso 1 (esta migracion): CREATE TABLE - sin bloqueos sobre datos existentes
  (idempotente respecto a las tablas de proctoring creadas en 0005).
  Paso 2 (futuro): migraciones adicionales para agregar indices/columnas si
  la carga lo requiere (expand/contract).

ROLLBACK:
  alembic downgrade slim@0005  -> elimina las 4 tablas en orden inverso.
  Las tablas de proctoring (0005) permanecen intactas.

VERIFICACION:
  alembic upgrade slim@head   -> aplica 0005 + 0008 contra postgres:16-alpine
  alembic history             -> debe mostrar 0005 -> 0008 en la rama slim
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "0008"
down_revision = "0005"   # rama slim - NO la rama principal
branch_labels = None     # ya hereda el label "slim" de 0005
depends_on = None        # SIN dependencia de migraciones de la rama principal

# Tipo TIMESTAMPTZ para columnas de tiempo (Postgres nativo)
TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    """Crea las 4 tablas de auth y biometria en Postgres estandar (slim).

    Orden de creacion (respetar FK):
      1. usuario         <- independiente
      2. refresh_tokens  <- FK a usuario
      3. foto_referencia <- FK a usuario
      4. embedding_referencia <- FK a usuario
    """

    # ------------------------------------------------------------------
    # 1. usuario
    # ------------------------------------------------------------------
    op.create_table(
        "usuario",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "id_institucional",
            sa.String(255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "email",
            sa.String(320),
            nullable=False,
        ),
        sa.Column(
            "roles",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "attrs_federados",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "password_hash",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "auth_provider",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'jwt'"),
        ),
    )

    # Indice unico sobre id_institucional (busqueda en login)
    op.create_index(
        "ix_usuario_id_institucional",
        "usuario",
        ["id_institucional"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 2. refresh_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "jti",
            sa.Text,
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            TIMESTAMPTZ,
            nullable=False,
        ),
        sa.Column(
            "rotado_en",
            TIMESTAMPTZ,
            nullable=True,
        ),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indices de rendimiento para refresh_tokens
    # (el UNIQUE sobre jti ya crea un indice implicito; lo declaramos explicitamente
    # para que alembic lo gestione en el downgrade)
    op.create_index(
        "ix_refresh_tokens_usuario_id",
        "refresh_tokens",
        ["usuario_id"],
    )
    op.create_index(
        "ix_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
    )

    # ------------------------------------------------------------------
    # 3. foto_referencia (slim: BYTEA en DB, sin MinIO)
    # ------------------------------------------------------------------
    op.create_table(
        "foto_referencia",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "foto_bytes",
            sa.LargeBinary,
            nullable=False,
        ),
        sa.Column(
            "hash_sha256",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "vigente",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_foto_referencia_usuario_id",
        "foto_referencia",
        ["usuario_id"],
    )
    op.create_index(
        "ix_foto_referencia_vigente",
        "foto_referencia",
        ["vigente"],
    )

    # ------------------------------------------------------------------
    # 4. embedding_referencia
    # ------------------------------------------------------------------
    op.create_table(
        "embedding_referencia",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "embedding_cifrado",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "algoritmo",
            sa.Text,
            nullable=False,
            server_default=sa.text("'face-api-128d'"),
        ),
        sa.Column(
            "fecha_captura",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "fecha_expiracion",
            TIMESTAMPTZ,
            nullable=True,
        ),
        sa.Column(
            "vigente",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "eliminado_en",
            TIMESTAMPTZ,
            nullable=True,
        ),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_embedding_referencia_usuario_id",
        "embedding_referencia",
        ["usuario_id"],
    )
    op.create_index(
        "ix_embedding_referencia_vigente",
        "embedding_referencia",
        ["vigente"],
    )


def downgrade() -> None:
    """Elimina las 4 tablas en orden inverso (respetar FK constraints).

    Las tablas de proctoring (0005) permanecen intactas.
    """
    # Primero los que tienen FK hacia usuario
    op.drop_index("ix_embedding_referencia_vigente", table_name="embedding_referencia")
    op.drop_index("ix_embedding_referencia_usuario_id", table_name="embedding_referencia")
    op.drop_table("embedding_referencia")

    op.drop_index("ix_foto_referencia_vigente", table_name="foto_referencia")
    op.drop_index("ix_foto_referencia_usuario_id", table_name="foto_referencia")
    op.drop_table("foto_referencia")

    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_usuario_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # Finalmente usuario (referenciado por los otros)
    op.drop_index("ix_usuario_id_institucional", table_name="usuario")
    op.drop_table("usuario")
