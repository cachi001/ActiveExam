"""059 - Agrega debe_cambiar_password a la tabla usuario (clave temporal).

Revision ID: 0059
Revises: 0058
Create Date: 2026-08-05

PROPOSITO:
  Agrega la columna `debe_cambiar_password` (BOOLEAN, NOT NULL, DEFAULT FALSE) a
  `usuario`. TRUE = el usuario fue creado por un admin con una contraseña temporal
  y debe definir su propia contraseña en el próximo login (RN-AU, primer acceso).
  Se limpia (FALSE) cuando el usuario cambia la contraseña con éxito.

  Es ADITIVA: no modifica ni elimina columnas existentes. Las filas pre-existentes
  quedan en FALSE (no se les fuerza el cambio).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "debe_cambiar_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "debe_cambiar_password")
