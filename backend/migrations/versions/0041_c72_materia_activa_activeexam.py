"""0041 - materia.activa (rama activeexam, C-72 seccion 17).

Revision ID: 0041
Revises: 0040 (branch activeexam)
Create Date: 2026-07-17

RAMA: activeexam
  down_revision = "0040"
  branch_labels = None
  depends_on    = None

PROPOSITO (C-72 seccion 17 — gestion de catalogo, activar/desactivar materia):
  Agrega la columna `activa BOOLEAN NOT NULL DEFAULT true` a `materia`. Es la
  fuente de verdad del "freeze": una materia desactivada (activa=false) corta
  inscripciones nuevas y bloquea iniciar/rendir sus examenes (server-side, regla
  dura #6). NO oculta la materia a los ya inscriptos.

  ADITIVA: el DEFAULT true backfillea las materias existentes -> todas quedan
  activas, sin cambio de comportamiento. Regla del stack (destructivas en dos
  pasos) NO aplica: esta migracion no dropea ni reescribe nada.

ROLLBACK:
  alembic downgrade activeexam@0040 -> DROP COLUMN activa.

VERIFICACION:
  alembic upgrade activeexam@head -> aplica hasta 0041.
  Espera materia.activa = true para toda materia preexistente.
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "materia",
        sa.Column(
            "activa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("materia", "activa")
