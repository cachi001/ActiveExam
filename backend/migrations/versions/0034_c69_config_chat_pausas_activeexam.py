"""0034 - flags chat_habilitado / pausas_habilitadas en configuracion_sistema (activeexam, C-69).

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-29

RAMA: activeexam
  down_revision = "0033"
  branch_labels = None
  depends_on    = None

PROPOSITO (toggles globales de la rendición):
  La configuración del SISTEMA debe poder activar/desactivar dos funciones de la
  rendición supervisada, de forma global (singleton 'global'):

  - chat_habilitado    (Boolean, NOT NULL, def true) → habilita el chat
    proctor↔alumno durante la rendición.
  - pausas_habilitadas (Boolean, NOT NULL, def true) → habilita que el alumno
    solicite pausas autorizadas.

  Columnas ADITIVAS sobre configuracion_sistema con server_default true: la fila
  singleton preexistente ('global') queda con ambas funciones HABILITADAS (mismo
  comportamiento que antes del toggle, compat). Sin DROP/ALTER destructivo.

ROLLBACK:
  alembic downgrade activeexam@0033 → dropea las 2 columnas. No toca ninguna otra tabla
  ni columna (aditivo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_sistema",
        sa.Column(
            "chat_habilitado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "configuracion_sistema",
        sa.Column(
            "pausas_habilitadas",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion_sistema", "pausas_habilitadas")
    op.drop_column("configuracion_sistema", "chat_habilitado")
