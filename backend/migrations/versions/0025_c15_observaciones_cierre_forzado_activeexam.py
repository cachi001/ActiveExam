"""0025 - observaciones del proctor + cierre forzado de sesion (activeexam, C-15 tareas 3.2/3.3).

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-24

RAMA: activeexam
  down_revision = "0024"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Tarea 3.2 — tabla ``observacion_proctor``: observaciones libres del proctor sobre
  una sesion (multiples por sesion), insumo de la revision humana C-16.
  Tarea 3.3 — columnas de CIERRE FORZADO en ``proctoring_session``
  (``cierre_forzado_en``, ``cierre_forzado_por``, ``cierre_forzado_motivo``): el
  proctor cierra la sesion de forma operativa (NO disciplinaria). El cierre forzado
  ademas setea ``finalizada_en``; estas columnas son el audit trail persistente.

  Migracion ADITIVA y NULLABLE -> un solo paso. La regla de dos pasos del proyecto
  aplica a cambios DESTRUCTIVOS (drop/rename en uso), no a columnas/tablas nuevas.

  L2.5 (regla dura #5 y #6): ni la observacion ni el cierre forzado sancionan o
  eximen; son insumo/operacion para la decision HUMANA. El audit trail vive en la
  propia fila (el activeexam no tiene tabla audit_log persistente).

ROLLBACK:
  alembic downgrade activeexam@0024 -> dropea las 3 columnas y la tabla observacion_proctor
  (y sus datos). No destructivo para el resto del esquema.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 3.2 — observaciones del proctor (insumo C-16)
    op.create_table(
        "observacion_proctor",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proctor_actor", sa.String(255), nullable=True),
        sa.Column("texto", sa.String(2000), nullable=False),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3.3 — cierre forzado (audit-as-row en la propia sesion)
    op.add_column(
        "proctoring_session",
        sa.Column("cierre_forzado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("cierre_forzado_por", sa.String(255), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("cierre_forzado_motivo", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "cierre_forzado_motivo")
    op.drop_column("proctoring_session", "cierre_forzado_por")
    op.drop_column("proctoring_session", "cierre_forzado_en")
    op.drop_table("observacion_proctor")
