"""0051 - base_url per-docente en moodle_credencial_docente.

Revision ID: 0051
Revises: 0050 (branch slim)
Create Date: 2026-07-30

RAMA: slim

PROPOSITO:
  Agrega `base_url` a `moodle_credencial_docente` para que cada docente pueda
  registrar su propia URL del campus. Antes la URL se tomaba siempre de la
  credencial institucional (`moodle_credencial`).

  Con esta columna el docente completa: URL del campus + usuario + contraseña.
  La URL institucional sigue existiendo para `anular_nota` y resolución de
  identidad Path 2; pero el write-back del docente ya no la requiere.

  NULL = sin configurar todavía → el backend cae al institucional como fallback.
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moodle_credencial_docente",
        sa.Column("base_url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("moodle_credencial_docente", "base_url")
