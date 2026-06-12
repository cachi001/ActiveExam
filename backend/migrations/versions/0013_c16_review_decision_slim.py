"""013 - persistencia de la decision del revisor en proctoring_session (slim, c-16).

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-11

RAMA: slim
  down_revision = "0012"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  c-16 backend slim: hoy las decisiones del revisor (descartar/escalar/derivar/
  pendiente) viven SOLO en el store del frontend (decisionesRevisor en zustand).
  Esto significa que al refrescar la pagina se pierden y no hay audit trail.

  Esta migracion agrega 4 columnas NULLABLE a proctoring_session para
  persistir la decision con su trazabilidad minima:

    decision               text  NULL  -- 'pendiente' | 'descartada' | 'escalada' | 'derivada'
    decision_actor         text  NULL  -- subject del JWT del revisor
    decision_at            timestamptz NULL
    decision_observaciones text  NULL  -- nota libre del revisor

  Las columnas son NULLABLE y sin default explicito: las sesiones
  pre-existentes quedan con decision=NULL (= "no revisada todavia"). El
  endpoint POST /api/v1/review/session/{id}/decide setea las 4 atomicamente
  + audit log.

  INMUTABILIDAD: una vez seteada, la decision NO se puede modificar (regla
  dura L2.5 RN-RV-07: decision terminal inmutable). El check se hace a nivel
  servicio (no via trigger, para mantener la migracion simple y reversible).

ROLLBACK:
  alembic downgrade slim@0012  -> dropea las 4 columnas. Datos persistidos
  en estas columnas se PIERDEN al downgrade — documentado en design.

VERIFICACION:
  alembic upgrade slim@head    -> aplica 0012 -> 0013. Espera columnas
  `decision`, `decision_actor`, `decision_at`, `decision_observaciones`
  en proctoring_session (todas NULLABLE, sin server_default).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column("decision", sa.Text(), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("decision_actor", sa.Text(), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("decision_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("decision_observaciones", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "decision_observaciones")
    op.drop_column("proctoring_session", "decision_at")
    op.drop_column("proctoring_session", "decision_actor")
    op.drop_column("proctoring_session", "decision")
