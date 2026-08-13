"""0067 - Agrega examen_iniciado_en a proctoring_session (ancla del timer de examen).

Revision ID: 0067
Revises: 0066
Create Date: 2026-08-12

PROPOSITO:
  Agrega la columna `examen_iniciado_en` (TIMESTAMPTZ, NULLABLE) a
  `proctoring_session`. Es el momento en que el alumno abre las preguntas por
  primera vez, seteado idempotente server-side en el primer fetch de rendicion.

  Fix de fairness: el timer del examen se anclaba a `creada_en`, que puede caer
  en el consentimiento/biometria ANTICIPADOS (la sesion se crea antes de rendir),
  descontandole esos minutos al tiempo de examen. Con este ancla el reloj arranca
  cuando el alumno realmente empieza, sin dejar de ser a prueba de F5 (server-side).

  Es ADITIVA: no toca columnas existentes. Filas pre-existentes quedan en NULL
  (el timer cae al fallback `creada_en`, comportamiento previo).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column("examen_iniciado_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "examen_iniciado_en")
