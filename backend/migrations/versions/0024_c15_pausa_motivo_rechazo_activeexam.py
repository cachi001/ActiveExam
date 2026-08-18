"""0024 - pausa_autorizada.motivo_rechazo (activeexam, C-15).

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-24

RAMA: activeexam
  down_revision = "0023"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Agrega la columna ``motivo_rechazo VARCHAR(500) NULL`` a ``pausa_autorizada``.
  Es el motivo que el PROCTOR da al RECHAZAR una solicitud de pausa; el alumno lo
  ve en pantalla. NULL cuando la pausa se aprobo (no aplica).

  Migracion ADITIVA y NULLABLE -> un solo paso. La regla de dos pasos del proyecto
  aplica a cambios DESTRUCTIVOS (drop/rename de columnas en uso), no a una columna
  nueva opcional como esta.

  L2.5 (regla dura #5 y #6): el motivo de rechazo es parte del rastro de auditoria
  persistente de la pausa (junto con proctor_actor + resuelta_en). NO sanciona ni
  exime: solo informa al alumno por que el proctor no autorizo la pausa.

ROLLBACK:
  alembic downgrade activeexam@0023 -> dropea la columna motivo_rechazo (y sus datos).
  No destructivo para el resto del esquema.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pausa_autorizada",
        sa.Column("motivo_rechazo", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pausa_autorizada", "motivo_rechazo")
