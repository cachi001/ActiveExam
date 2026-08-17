"""0032 - configuración del examen POR EXAMEN (activeexam, C-69).

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-29

RAMA: activeexam
  down_revision = "0031"
  branch_labels = None
  depends_on    = None

PROPÓSITO (configuración del examen que ActiveExam opera y el alumno rinde):
  ActiveExam administra la configuración POR EXAMEN. Estas columnas son aditivas
  sobre examen_contenido — no rompen filas existentes (todas con defaults):

  - tiempo_limite_min  (Integer, NULL)            → null = sin límite de tiempo.
  - intentos_permitidos(Integer, NOT NULL, def 1) → cantidad de intentos.
  - apertura           (TIMESTAMPTZ, NULL)        → inicio de la ventana de rendición.
  - cierre             (TIMESTAMPTZ, NULL)        → fin de la ventana de rendición.
  - nota_maxima        (Numeric(5,2), NOT NULL, def 10) → escala de la nota.
  - nota_aprobacion    (Numeric(5,2), NOT NULL, def 6)  → umbral de aprobación.
  - mezclar_preguntas  (Boolean, NOT NULL, def false)   → shuffle en la rendición.

  Los exámenes importados antes de esta migración quedan con la configuración por
  defecto (1 intento, nota sobre 10, aprueba con 6, sin ventana ni límite, sin
  mezclar) — mismo comportamiento que antes de la config por examen.

ROLLBACK:
  alembic downgrade activeexam@0031 → dropea las 7 columnas. No toca ninguna otra tabla
  ni columna (aditivo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column("tiempo_limite_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "intentos_permitidos",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column("apertura", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "examen_contenido",
        sa.Column("cierre", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "nota_maxima",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "nota_aprobacion",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="6",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "mezclar_preguntas",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("examen_contenido", "mezclar_preguntas")
    op.drop_column("examen_contenido", "nota_aprobacion")
    op.drop_column("examen_contenido", "nota_maxima")
    op.drop_column("examen_contenido", "cierre")
    op.drop_column("examen_contenido", "apertura")
    op.drop_column("examen_contenido", "intentos_permitidos")
    op.drop_column("examen_contenido", "tiempo_limite_min")
