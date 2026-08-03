"""0042 - moodle_component por examen + en el estado de writeback (rama slim, C-73).

Revision ID: 0042
Revises: 0041 (branch slim)
Create Date: 2026-07-19

RAMA: slim
  down_revision = "0041"
  branch_labels = None
  depends_on    = None

PROPOSITO (C-73 — devolver la nota en cuestionarios, no solo tareas):
  Agrega `moodle_component VARCHAR(32) NULL` a:
  - examen_contenido: el modulo destino del write-back POR EXAMEN ('mod_assign' para
    tareas, 'mod_quiz' para cuestionarios). NULL = fallback global
    (config.moodle_component, default 'mod_assign').
  - moodle_writeback_estado: se persiste el component elegido al finalizar la sesion,
    para que el envio MANUAL del admin (ejecutar_writeback -> write_grade) lo use.

  Validado E2E en campustest: core_grades_update_grades escribe la nota tanto en
  mod_assign como en mod_quiz (0-100).

  ADITIVA: columna NULL, sin backfill destructivo. Los examenes previos quedan con
  NULL -> usan el component global (mod_assign), comportamiento identico al previo.

ROLLBACK:
  alembic downgrade slim@0041 -> DROP COLUMN moodle_component en ambas tablas.

VERIFICACION:
  alembic upgrade slim@head -> aplica hasta 0042.
  Espera examen_contenido.moodle_component y moodle_writeback_estado.moodle_component
  = NULL para las filas preexistentes.
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column("moodle_component", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "moodle_writeback_estado",
        sa.Column("moodle_component", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("moodle_writeback_estado", "moodle_component")
    op.drop_column("examen_contenido", "moodle_component")
