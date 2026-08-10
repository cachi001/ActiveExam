"""053 - C-74: tabla categoria_pregunta (banco de preguntas por categorias).

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-03

RAMA: slim
  down_revision = "0052"

PROPOSITO:
  Introduce la jerarquia de categorias del banco de preguntas. Las preguntas
  existentes NO se tocan (quedan sin categoria = "Sin clasificar").

  Tabla nueva `categoria_pregunta`:
    - id             UUID PK
    - materia_id     UUID FK materia.id ON DELETE CASCADE (NOT NULL)
    - nombre         text NOT NULL
    - categoria_padre_id UUID nullable self-FK ON DELETE CASCADE
    - creada_en      timestamptz NOT NULL default now()
  Indice en (materia_id, categoria_padre_id).

ROLLBACK:
  Dropea la tabla completa. Inocuo si no hay datos.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categoria_pregunta",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "materia_id",
            UUID(as_uuid=False),
            sa.ForeignKey("materia.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column(
            "categoria_padre_id",
            UUID(as_uuid=False),
            sa.ForeignKey("categoria_pregunta.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_categoria_pregunta_materia_padre",
        "categoria_pregunta",
        ["materia_id", "categoria_padre_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_categoria_pregunta_materia_padre", table_name="categoria_pregunta")
    op.drop_table("categoria_pregunta")
