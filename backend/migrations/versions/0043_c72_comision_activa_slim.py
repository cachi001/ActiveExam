"""0043 - comision.activa (rama slim, C-72 seccion 17 a nivel comision).

Revision ID: 0043
Revises: 0042 (branch slim)
Create Date: 2026-07-22

RAMA: slim
  down_revision = "0042"
  branch_labels = None
  depends_on    = None

PROPOSITO (baja logica de comision):
  Agrega la columna `activa BOOLEAN NOT NULL DEFAULT true` a `comision`. Es el
  espejo de materia.activa (migracion 0041) un nivel mas abajo: una comision
  desactivada corta inscripciones nuevas por su codigo de matriculacion y
  bloquea iniciar la rendicion de SUS examenes (server-side, regla dura #6),
  sin tocar la materia ni las demas comisiones. NO desmatricula a nadie: los
  ya inscriptos conservan su acceso al historial.

  Es la salida cuando el DELETE esta bloqueado: solo se borra una comision
  100% vacia; con inscriptos o examenes, se desactiva.

  ADITIVA: el DEFAULT true backfillea las comisiones existentes -> todas quedan
  activas, sin cambio de comportamiento. Regla del stack (destructivas en dos
  pasos) NO aplica: esta migracion no dropea ni reescribe nada.

ROLLBACK:
  alembic downgrade slim@0042 -> DROP COLUMN activa.

VERIFICACION:
  alembic upgrade slim@head -> aplica hasta 0043.
  Espera comision.activa = true para toda comision preexistente.
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comision",
        sa.Column(
            "activa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("comision", "activa")
