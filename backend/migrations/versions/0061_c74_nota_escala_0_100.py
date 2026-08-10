"""061 - examen_contenido.nota_maxima/nota_aprobacion: default 100/60, no 10/6.

Revision ID: 0061
Revises: 0060
Create Date: 2026-08-10

PROPOSITO:
  El flujo `crear-desde-banco` (C-74) crea el examen sin pasar nota_maxima ni
  nota_aprobacion, así que caía silenciosamente en el server_default histórico
  (10/6 — escala Moodle "sobre 10"). El docente termina con exámenes calificados
  del 1 al 10 sin haberlo elegido. Cambia el default de la COLUMNA a 100/60
  (escala 0-100, aprobación 60%) — el docente sigue pudiendo elegir otra escala
  vía PATCH /config, pero el default deja de ser "sobre 10".

  Solo cambia el DEFAULT para filas NUEVAS. No toca exámenes ya creados —
  reescribir retroactivamente la escala de un examen ya rendido alteraría notas
  ya calculadas (ver CONGELADO_DURO en domain/exam_content/config.py).
"""

from __future__ import annotations

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE examen_contenido ALTER COLUMN nota_maxima SET DEFAULT 100")
    op.execute("ALTER TABLE examen_contenido ALTER COLUMN nota_aprobacion SET DEFAULT 60")


def downgrade() -> None:
    op.execute("ALTER TABLE examen_contenido ALTER COLUMN nota_maxima SET DEFAULT 10")
    op.execute("ALTER TABLE examen_contenido ALTER COLUMN nota_aprobacion SET DEFAULT 6")
