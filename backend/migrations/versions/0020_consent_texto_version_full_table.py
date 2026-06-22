"""020 - tabla consent_texto_version (rama FULL, espeja 0018 de slim).

Revision ID: 0020
Revises: 0017 (rama full)
Create Date: 2026-06-16

RAMA: full (principal, con TimescaleDB)
  down_revision = "0017"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Espeja en la rama FULL la tabla ``consent_texto_version`` creada en slim por
  0018. Mismo schema: version VARCHAR PK, bloques JSONB, hash_texto VARCHAR,
  created_at TIMESTAMPTZ, created_by VARCHAR nullable.

  El seed v1 viene en la siguiente migracion convergente (0021) que une 0018
  (slim, con tabla) + 0020 (full, con tabla) antes de sembrar datos.

ROLLBACK:
  alembic downgrade full@0017 -> dropea la tabla (destructivo, paso 2 separado).

VERIFICACION:
  alembic upgrade full@head -> aplica 0017 -> 0020 -> (seed convergente).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0020"
down_revision = "0017"
branch_labels = None
depends_on = None

TIMESTAMPTZ = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "consent_texto_version",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("bloques", JSONB, nullable=False),
        sa.Column("hash_texto", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("consent_texto_version")
