"""064 - Tabla lti_nonce (C-75, anti-replay del flujo OIDC de LTI).

Revision ID: 0064
Revises: 0063
Create Date: 2026-08-10

PROPOSITO:
  El flujo OIDC de LTI exige validar que el `nonce`/`state` generados en
  `/lti/login` reaparezcan en el `id_token` de `/lti/launch`, y que NO se reusen
  (replay). Con múltiples workers/instancias, memoria de proceso no sirve: se
  persiste `nonce` + `state` + `iss` + expiración (TTL 5 min) en esta tabla, con
  índice para la limpieza por TTL (mismo patrón que `refresh_tokens`) — design D5.

  `consumido_en IS NULL` = todavía usable; NOT NULL = ya consumido en un launch,
  cualquier reuso se rechaza. `nonce` y `state` son UNIQUE.

  Es ADITIVA. No referencia usuario (el nonce vive ANTES de saber quién es).

ROLLBACK:
  alembic downgrade activeexam@0063 → dropea la tabla nueva. No toca nada existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

_IX_EXPIRA = "ix_lti_nonce_expira_en"


def upgrade() -> None:
    op.create_table(
        "lti_nonce",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nonce", sa.Text, nullable=False, unique=True),
        sa.Column("state", sa.Text, nullable=False, unique=True),
        sa.Column("iss", sa.Text, nullable=False),
        sa.Column("expira_en", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumido_en", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(_IX_EXPIRA, "lti_nonce", ["expira_en"])


def downgrade() -> None:
    op.drop_index(_IX_EXPIRA, table_name="lti_nonce")
    op.drop_table("lti_nonce")
