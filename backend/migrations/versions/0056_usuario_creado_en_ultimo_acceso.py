"""056 - Agrega creado_en y ultimo_acceso_en a la tabla usuario.

Revision ID: 0056
Revises: 0055
Create Date: 2026-08-04

PROPOSITO:
  Agrega dos columnas a `usuario`:
    - creado_en: timestamp de alta del usuario (DEFAULT NOW(), NOT NULL).
      Para filas pre-existentes se rellena con NOW() en la migración.
    - ultimo_acceso_en: timestamp del último login exitoso (nullable).

  Es ADITIVA: no modifica ni elimina columnas existentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "creado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "usuario",
        sa.Column(
            "ultimo_acceso_en",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "ultimo_acceso_en")
    op.drop_column("usuario", "creado_en")
