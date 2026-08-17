"""0045 - examen_contenido: politica_intentos (C-73).

Revision ID: 0045
Revises: 0044 (branch activeexam)
Create Date: 2026-07-25

RAMA: activeexam
  down_revision = "0044"

PROPOSITO:
  Agrega la columna `politica_intentos` VARCHAR(20) NOT NULL DEFAULT 'mas_alta'
  a examen_contenido. Controla qué nota se envía a Moodle cuando el alumno
  tiene múltiples sesiones completadas para el mismo examen:

    - mas_alta  → la nota más alta de todos los intentos
    - ultimo    → la nota del intento más reciente
    - primero   → la nota del primer intento
    - manual    → el admin elige qué sesión sincronizar (comportamiento previo)

  Aditiva y sin backfill: filas existentes quedan con el default 'mas_alta',
  que es el comportamiento más razonable y el que Moodle recomienda para quizzes.
"""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "politica_intentos",
            sa.String(20),
            nullable=False,
            server_default="mas_alta",
        ),
    )


def downgrade() -> None:
    op.drop_column("examen_contenido", "politica_intentos")
