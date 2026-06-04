"""0006 - Cola Postgres de trabajos para la PoC C-03 (DESCARTABLE).

Revision ID: 0006
Revises: (branch independiente — down_revision=None)
Create Date: 2026-06-03

Scope: PoC C-03 (poc-carga-mensajeria), Bloque 3. Tabla descartable ``poc_job_queue``
para medir el concern (a): cola Postgres con ``SELECT ... FOR UPDATE SKIP LOCKED``
y un worker con stubs de latencia fija. NADA de esto se promueve a produccion — el
adaptador real de la cola (C-05) vive en otra tabla; aqui solo se mide.

BRANCH INDEPENDIENTE (down_revision=None, igual que 0005 slim): no depende de la
cadena de prod (0001..0004). Se aplica aislada con ``alembic upgrade 0006`` y se
descarta con ``alembic downgrade -1`` sin tocar el esquema de produccion.

CONVENCION DESTRUCTIVA: el downgrade elimina la tabla completa (es descartable, no
hay datos a preservar).
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = None  # Branch independiente — PoC descartable, no cuelga de prod.
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tabla minima de cola. gen_random_uuid() es nativo en pg13+ (timescaledb-pg16).
    # taken_at NULL = pendiente; no-NULL = reclamado por un worker (dequeue lo fija).
    op.execute(
        """
        CREATE TABLE poc_job_queue (
            id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            topic      TEXT        NOT NULL,
            payload    JSONB       NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            taken_at   TIMESTAMPTZ NULL
        );
        """
    )
    # Indice parcial para el dequeue: solo filas pendientes (taken_at IS NULL),
    # ordenadas FIFO por created_at. Hace eficiente el SKIP LOCKED bajo carga.
    op.execute(
        """
        CREATE INDEX ix_poc_job_queue_pendientes
        ON poc_job_queue (topic, created_at)
        WHERE taken_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS poc_job_queue")
