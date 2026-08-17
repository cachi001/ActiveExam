"""0033 - identidad del alumno en la sesion de proctoring (activeexam, C-69).

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-29

RAMA: activeexam
  down_revision = "0032"
  branch_labels = None
  depends_on    = None

PROPOSITO (enforcement server-side de ventana e intentos):
  Hasta ahora ``proctoring_session`` NO guardaba al alumno: la identidad se
  extraia del JWT recien en finalize (para el write-back). El enforcement de
  intentos por examen necesita poder CONTAR las sesiones finalizadas de un alumno
  para un examen, por eso la identidad debe persistirse al CREAR la sesion.

  Columnas aditivas (nullable, sin default) sobre proctoring_session:
    - alumno_idnumber (VARCHAR(255), NULL) -> id_institucional del alumno (legajo/
      padron). Mismo criterio que usa el write-back (alumno_idnumber).
    - alumno_email    (VARCHAR(255), NULL) -> email del alumno (fallback identidad).

  Las filas existentes quedan con NULL (sesiones creadas antes del enforcement);
  no se cuentan como intentos de ningun alumno (alumno_idnumber IS NULL).

ROLLBACK:
  alembic downgrade activeexam@0032 -> dropea las 2 columnas. Aditivo: no toca ninguna
  otra tabla ni columna.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column("alumno_idnumber", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("alumno_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "alumno_email")
    op.drop_column("proctoring_session", "alumno_idnumber")
