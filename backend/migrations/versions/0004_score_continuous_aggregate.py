"""004 - continuous aggregate de score PONDERADO por sesion (C-13, DD-05/RN-SC-02).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-30

Scope (C-13, incremental-risk-score). La 002 dejo ``cagg_score_sesion`` como proxy
(cuenta severos/total por minuto). Esta migracion agrega ``cagg_score_ponderado_min``:
un continuous aggregate que PONDERA cada evento por su severidad (mismos pesos que el
dominio ``app/domain/scoring/risk_score.py``: baseline 0, baja 0.5, media 1, alta 3,
critica 6) y lo agrega por sesion por minuto. La lectura del score sale del agregado
materializado (CQRS-lite), no de recorrer la hypertable.

La CORRELACION y el score final (con bono de eventos coincidentes) los calcula el
dominio puro sobre los eventos al cierre (recomputable e idempotente); el agregado
provee el score incremental EN VIVO (panel C-15) al minuto. Refresh incremental cada
minuto (start_offset 1h, end_offset 1min) como los agregados de la 002.

CONVENCION DESTRUCTIVA EN DOS PASOS: el ``downgrade`` dropea solo el agregado nuevo
(CASCADE), sin tocar la hypertable ni los agregados de la 002.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Score ponderado por severidad, por sesion, por minuto. Los pesos replican
    # _PESO_SEVERIDAD_DEFAULT del dominio (single source: dominio puro; este SQL es
    # el insumo CQRS-lite EN VIVO consistente con esa ponderacion).
    op.execute(
        """
        CREATE MATERIALIZED VIEW cagg_score_ponderado_min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', timestamp) AS bucket,
            session_id,
            sum(
                CASE severidad
                    WHEN 'baseline' THEN 0.0
                    WHEN 'baja' THEN 0.5
                    WHEN 'media' THEN 1.0
                    WHEN 'alta' THEN 3.0
                    WHEN 'critica' THEN 6.0
                    ELSE 0.0
                END
            ) AS score_ponderado,
            count(*) AS eventos
        FROM evento
        GROUP BY bucket, session_id
        WITH NO DATA;
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('cagg_score_ponderado_min',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '1 minute',
            schedule_interval => INTERVAL '1 minute')
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP MATERIALIZED VIEW IF EXISTS cagg_score_ponderado_min CASCADE"
    )
