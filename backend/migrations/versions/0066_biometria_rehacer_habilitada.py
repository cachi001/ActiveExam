"""066 - Agrega biometria_rehacer_habilitada a usuario (override admin de un solo uso).

Revision ID: 0066
Revises: 0065
Create Date: 2026-08-12

PROPOSITO:
  Agrega la columna `biometria_rehacer_habilitada` (BOOLEAN, NOT NULL, DEFAULT
  FALSE) a `usuario`. El alumno NO puede rehacer su captura biometrica de
  referencia mientras siga vigente (no vencida). Un admin puede habilitar UNA
  rehecha desde la edicion de usuario: pone este flag en TRUE; se CONSUME
  (vuelve a FALSE) apenas el alumno guarda una nueva referencia con exito.

  Es ADITIVA: no toca columnas existentes. Filas pre-existentes quedan en FALSE.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "biometria_rehacer_habilitada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "biometria_rehacer_habilitada")
