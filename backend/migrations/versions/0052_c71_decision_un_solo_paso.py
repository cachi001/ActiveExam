"""052 - colapsa el modelo de decision a UN SOLO PASO (3 estados, slim).

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-03

RAMA: slim
  down_revision = "0051"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  El modelo de DOS FASES introducido en 0039 (c-71 slice 2: `DecisionRevision`
  fase 1 + `DecisionResolucion` fase 2, con `caso_abierto` como derivacion a
  una segunda instancia) fue RECHAZADO EXPLICITAMENTE por el owner del
  proyecto: "no existe el caso abierto, nunca dije que era un estado y no lo
  va a ser". Confirmado en pregunta directa: "si, un solo paso: quien revisa
  decide", SIN segunda instancia de validacion.

  Este migration colapsa el schema a UN SOLO ACTO, 3 estados:

    decision  text NULL  -- 'pendiente' | 'aprobado' | 'anulado'

  Cambios sobre `proctoring_session`:
    - `decision_observaciones` -> RENOMBRADA a `decision_motivo` (mismo uso:
      motivo del veredicto; ahora obligatorio no vacio cuando decision='anulado',
      validado en capa de aplicacion, no en el schema).
    - `decision_evidencia_ids` (NUEVA, jsonb NULL): lista ESTRUCTURADA de
      `proctoring_event.id` elegidos por el revisor como evidencia del
      veredicto. Reemplaza el string libre `evidencia_ref` que viajaba en el
      body del endpoint de resolucion (nunca persistido — c-71 slice 2 solo
      lo mandaba al audit log como texto). Sin esto, el informe de devolucion
      al alumno (D12) no podia filtrar capturas a lo que el revisor
      efectivamente eligio: mostraba TODA la evidencia de la sesion.
    - `resolucion`, `resolucion_actor`, `resolucion_at`, `resolucion_motivo`
      (agregadas en 0039) -> DROPEADAS. No hay fase 2 que persistir.

  Produccion (slim) tiene 0 filas en `proctoring_session` con `decision`
  seteada a esta fecha (verificado antes de este cambio): no hace falta
  mapeo de datos ni compatibilidad con los valores viejos
  ('sin_hallazgos'/'caso_abierto'/'derivada'/'escalada'/'anulado_por_fraude'/
  'caso_descartado'). El UPDATE defensivo de abajo es igual best-effort por si
  algun ambiente de desarrollo quedo con datos de prueba.

ROLLBACK:
  alembic downgrade slim@0051 -> recrea las 4 columnas `resolucion*` (vacias),
  renombra `decision_motivo` de vuelta a `decision_observaciones`, dropea
  `decision_evidencia_ids`, y mapea 'anulado' -> 'caso_abierto' en `decision`
  (best-effort: el veredicto en si se pierde, documentado y aceptado porque
  no hay datos reales).

VERIFICACION:
  alembic upgrade slim@head -> aplica 0051 -> 0052. Espera en
  `proctoring_session`: sin columnas `resolucion*`; `decision_motivo` (en vez
  de `decision_observaciones`); `decision_evidencia_ids` jsonb NULL; `decision`
  sin valores 'sin_hallazgos'/'caso_abierto'/'derivada'/'escalada' remanentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

_proctoring_session = sa.table(
    "proctoring_session",
    sa.column("decision", sa.Text()),
)


def upgrade() -> None:
    # --- Motivo: renombrar (mismo dato, mismo uso) ---
    op.alter_column(
        "proctoring_session",
        "decision_observaciones",
        new_column_name="decision_motivo",
    )

    # --- Evidencia estructurada (nueva) ---
    op.add_column(
        "proctoring_session",
        sa.Column("decision_evidencia_ids", JSONB(), nullable=True),
    )

    # --- Mapeo defensivo de valores viejos (best-effort, dev/test) ---
    op.execute(
        _proctoring_session.update()
        .where(
            _proctoring_session.c.decision.in_(
                ("sin_hallazgos", "caso_descartado")
            )
        )
        .values(decision="aprobado")
    )
    op.execute(
        _proctoring_session.update()
        .where(
            _proctoring_session.c.decision.in_(
                ("caso_abierto", "derivada", "escalada", "anulado_por_fraude")
            )
        )
        .values(decision="anulado")
    )

    # --- Fase 2 (dos-fases): dropear ---
    op.drop_column("proctoring_session", "resolucion_motivo")
    op.drop_column("proctoring_session", "resolucion_at")
    op.drop_column("proctoring_session", "resolucion_actor")
    op.drop_column("proctoring_session", "resolucion")


def downgrade() -> None:
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
        sa.Column("resolucion_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "proctoring_session",
        sa.Column("resolucion_motivo", sa.Text(), nullable=True),
    )

    # Best-effort: el veredicto 'anulado' vuelve a 'caso_abierto' (la
    # distincion de si ya habia sido resuelto se pierde; documentado arriba).
    op.execute(
        _proctoring_session.update()
        .where(_proctoring_session.c.decision == "anulado")
        .values(decision="caso_abierto")
    )

    op.drop_column("proctoring_session", "decision_evidencia_ids")
    op.alter_column(
        "proctoring_session",
        "decision_motivo",
        new_column_name="decision_observaciones",
    )
