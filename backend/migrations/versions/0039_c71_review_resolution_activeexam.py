"""039 - modelo de decision de dos fases + estado de resolucion (activeexam, c-71
slice 2).

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-13

RAMA: activeexam
  down_revision = "0038"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  c-71 slice 2 (D6/D9/D10) evoluciona el modelo de decision del revisor
  (c-16) a dos fases:

    Fase 1 -- REVISION (columnas `decision*` ya existentes, migracion 0013):
      valores viejos 'descartada' | 'escalada' | 'derivada' se REEMPLAZAN por
      'sin_hallazgos' | 'caso_abierto' (el propio `escalada` se DROPEA del
      modelo, sin downstream -- D6). Mapeo exacto:

        'pendiente'  -> 'pendiente'   (sin cambio)
        'descartada' -> 'sin_hallazgos'
        'derivada'   -> 'caso_abierto'
        'escalada'   -> 'caso_abierto'

      Produccion activeexam tiene ~0 filas con decision seteada (c-16 recien
      desplegado); el UPDATE de mapeo es defensivo/idempotente igual.

    Fase 2 -- RESOLUCION (NUEVA, este migration): 4 columnas NULLABLE en
      `proctoring_session`, junto a las de decision:

        resolucion            text  NULL  -- 'anulado_por_fraude' | 'caso_descartado'
        resolucion_actor      text  NULL  -- subject del JWT de quien resolvio
        resolucion_at         timestamptz NULL
        resolucion_motivo     text  NULL  -- motivo obligatorio del veredicto (D11)

  Sin tabla nueva de "actos": la reversibilidad de la anulacion se hace por
  acto compensatorio append-only en el `audit_log` YA EXISTENTE (0012, D10b)
  -- cero infra nueva. NO se toca `moodle_writeback_estado` (D10): el
  write-back se GATEA por el estado de revision/resolucion (D15), no se
  fusiona con la nota de Moodle.

ROLLBACK:
  alembic downgrade activeexam@0038 -> dropea las 4 columnas `resolucion*` y
  revierte el mapeo de `decision` a los valores viejos ('sin_hallazgos' ->
  'descartada', 'caso_abierto' -> 'derivada'; el valor 'escalada' original
  NO se puede recuperar distinguido de 'derivada' -- perdida documentada,
  aceptada porque produccion no tenia filas con esa decision al momento del
  deploy de este migration).

VERIFICACION:
  alembic upgrade activeexam@head -> aplica 0038 -> 0039. Espera columnas
  `resolucion`, `resolucion_actor`, `resolucion_at`, `resolucion_motivo` en
  `proctoring_session` (todas NULLABLE, sin server_default) y `decision` sin
  valores 'descartada'/'escalada'/'derivada' remanentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

_proctoring_session = sa.table(
    "proctoring_session",
    sa.column("decision", sa.Text()),
)


def upgrade() -> None:
    # --- Fase 2: columnas de resolucion (nuevas) ---
    op.add_column(
        "proctoring_session",
        sa.Column("resolucion", sa.Text(), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("resolucion_actor", sa.Text(), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("resolucion_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("resolucion_motivo", sa.Text(), nullable=True),
    )

    # --- Fase 1: mapeo de valores viejos de `decision` (D6) ---
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "descartada")
        .values(decision="sin_hallazgos")
    )
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "derivada")
        .values(decision="caso_abierto")
    )
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "escalada")
        .values(decision="caso_abierto")
    )


def downgrade() -> None:
    # Revertir el mapeo de `decision` (best-effort, ver nota de ROLLBACK)
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "sin_hallazgos")
        .values(decision="descartada")
    )
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "caso_abierto")
        .values(decision="derivada")
    )

    op.drop_column("proctoring_session", "resolucion_motivo")
    op.drop_column("proctoring_session", "resolucion_at")
    op.drop_column("proctoring_session", "resolucion_actor")
    op.drop_column("proctoring_session", "resolucion")
