"""0030 - destino de write-back por examen: moodle_courseid/cmid (activeexam, C-69, D12).

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-28

RAMA: activeexam
  down_revision = "0029"
  branch_labels = None
  depends_on    = None

PROPÓSITO (D12 — parte B):
  Hace que el destino del write-back de nota a Moodle sea POR EXAMEN, no un
  único valor global de entorno. Cada examen importado guarda su propio
  moodle_courseid / moodle_cmid. Los valores globales de config_activeexam quedan
  SÓLO como fallback cuando el del examen es NULL (compat con exámenes ya
  importados antes de esta migración).

  Columnas nuevas (ambas NULLABLE, aditivas — no tocan filas existentes):
  - examen_contenido.moodle_courseid (Integer, NULL): curso destino en Moodle.
  - examen_contenido.moodle_cmid (Integer, NULL): id del course-module/actividad
    de calificación (misma semántica que usa write_grade hoy).

  No agrega mapeo de identidad por examen: la identidad sigue siendo global
  (por idnumber/email).

ROLLBACK:
  alembic downgrade activeexam@0029 → dropea ambas columnas. No toca ninguna otra
  tabla ni columna (aditivo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column("moodle_courseid", sa.Integer(), nullable=True),
    )
    op.add_column(
        "examen_contenido",
        sa.Column("moodle_cmid", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("examen_contenido", "moodle_cmid")
    op.drop_column("examen_contenido", "moodle_courseid")
