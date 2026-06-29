"""0031 - pool de preguntas: pregunta_examen.seleccionada (slim, C-69, opción B).

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-29

RAMA: slim
  down_revision = "0030"
  branch_labels = None
  depends_on    = None

PROPÓSITO (opción B — el examen importado es un POOL de preguntas):
  El docente elige CUÁLES preguntas del pool forman el examen. Esta columna marca
  esa selección. La rendición del alumno y el cálculo de nota respetan SOLO las
  preguntas con seleccionada=true.

  Columna nueva (aditiva — no rompe filas existentes):
  - pregunta_examen.seleccionada (Boolean, NOT NULL, server_default true).
    DEFAULT true por compat: los exámenes importados antes de esta migración
    quedan con TODAS las preguntas seleccionadas (mismo comportamiento previo).

ROLLBACK:
  alembic downgrade slim@0030 → dropea la columna. No toca ninguna otra tabla ni
  columna (aditivo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pregunta_examen",
        sa.Column(
            "seleccionada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pregunta_examen", "seleccionada")
