"""0081 - c-76-14 (rama activeexam): proctoring_session.archivado.

Revision ID: 0081
Revises: 0079
Create Date: 2026-08-17

PROPOSITO:
  Tarea 14 del change c-76-panel-supervision-en-vivo: el panel "Notas" necesita
  poder ocultar filas de la lista de resultados sin borrar nada (soft-hide
  administrativo, no disciplinario — no confundir con `decision` que es el
  veredicto humano sobre fraude). `archivado` es un flag propio, ortogonal al
  estado de sync a Moodle y al estado de entrega (que se DERIVA, no se
  persiste, de `finalizada_en`/`en_cola_revision`/`decision`).

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: columna nueva con `NOT NULL DEFAULT false` no reescribe filas
  existentes de forma insegura (Postgres materializa el default en el mismo
  ALTER TABLE de forma eficiente en versiones modernas) y no hay lectores
  existentes que se rompan por una columna adicional.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion relevante: el downgrade quita la
  columna (se pierde el flag de archivado, no la sesion ni su evidencia).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column(
            "archivado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "archivado")
