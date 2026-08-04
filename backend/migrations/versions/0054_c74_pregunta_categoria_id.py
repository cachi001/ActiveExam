"""054 - C-74: columna categoria_id en pregunta_examen + moodle_question_id.

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-03

RAMA: slim
  down_revision = "0053"

PROPOSITO:
  Dos columnas aditivas en `pregunta_examen`:

  1. categoria_id (UUID nullable, FK categoria_pregunta.id ON DELETE SET NULL):
     La categoria del banco de preguntas. NULL = "Sin clasificar".
     Preguntas existentes quedan con NULL (aditiva, no destructiva).

  2. moodle_question_id (int nullable):
     ID de la pregunta en el banco de Moodle. Permite sync idempotente
     (D8): una re-sync no duplica si ya existe (materia_id, moodle_question_id).
     Indice unico por examen: (examen_id, moodle_question_id).

ROLLBACK:
  Dropea ambas columnas. Inocuo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pregunta_examen",
        sa.Column(
            "categoria_id",
            UUID(as_uuid=False),
            sa.ForeignKey("categoria_pregunta.id", ondelete="SET NULL"),
            nullable=True,
            comment="C-74: categoria del banco. NULL = Sin clasificar.",
        ),
    )
    op.add_column(
        "pregunta_examen",
        sa.Column(
            "moodle_question_id",
            sa.Integer(),
            nullable=True,
            comment="C-74 D8: ID en Moodle para sync idempotente.",
        ),
    )
    op.create_index(
        "ix_pregunta_examen_categoria_id",
        "pregunta_examen",
        ["categoria_id"],
    )
    # Unicidad por examen para evitar duplicados en re-syncs desde Moodle.
    op.create_index(
        "uq_pregunta_examen_moodle_question",
        "pregunta_examen",
        ["examen_id", "moodle_question_id"],
        unique=True,
        postgresql_where=sa.text("moodle_question_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_pregunta_examen_moodle_question", table_name="pregunta_examen")
    op.drop_index("ix_pregunta_examen_categoria_id", table_name="pregunta_examen")
    op.drop_column("pregunta_examen", "moodle_question_id")
    op.drop_column("pregunta_examen", "categoria_id")
