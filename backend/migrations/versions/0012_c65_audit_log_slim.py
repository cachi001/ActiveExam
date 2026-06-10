"""012 - tabla audit_log append-only con hash encadenado (rama slim).

Revision ID: 0012
Revises: 0011 (branch slim)
Create Date: 2026-06-10

RAMA: slim
  down_revision = "0011"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  La feature de auditoria de re-enrollment biometrico (C-65 §7) escribe en
  ``audit_log`` (AuditLogSqlRepository, guardar_embedding_referencia.py). Esa
  tabla la crea SOLO la rama principal/full en 0002_core_models.py; la rama slim
  (0005 -> 0008 -> ... -> 0011) NUNCA la creo. En el deployment real (slim /
  Railway, postgres:16-alpine, sin TimescaleDB) el append a audit_log revienta
  con HTTP 500 porque la tabla no existe.

  Esta migracion porta a la rama slim la MISMA tabla + los 2 triggers de 0002,
  preservando la cadena de custodia (DD-07, D1+D2):
    - audit_log_no_mutacion()  + trg BEFORE UPDATE OR DELETE -> append-only, aborta.
    - audit_log_encadenar()    + trg BEFORE INSERT -> encadena hash_prev,
      materializa hash_self, completa timestamp.

  El cuerpo SQL de ambos triggers es IDENTICO al de 0002 (no se debilita ni se
  simplifica el hashing — la cadena depende de que sea byte a byte el mismo).

  DIFERENCIA vs 0002 (unica y obligatoria): la rama slim NO tiene tabla
  ``evidencia``, por lo que ``evidencia_id`` queda como columna UUID nullable
  SIN ForeignKeyConstraint. Todo lo demas (columnas, tipos, server_defaults,
  triggers) es identico a 0002.

  pgcrypto: el trigger de hash usa ``digest()``/``encode()``, por eso se crea la
  extension de forma idempotente (CREATE EXTENSION IF NOT EXISTS pgcrypto).

ROLLBACK:
  alembic downgrade slim@0011  -> dropea triggers, funciones y la tabla audit_log
  (espeja el downgrade de audit_log en 0002, sin tocar consentimiento/evidencia,
  que no existen en slim).

VERIFICACION:
  alembic upgrade slim@head    -> aplica 0011 -> 0012 contra postgres:16-alpine.
  Espera la tabla audit_log con sus 2 triggers tras el upgrade.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP, UUID

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgcrypto: digest()/encode() del trigger de hash. Idempotente.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- Audit log: tabla append-only con hash encadenado (DD-07, D1+D2) ----
    # Espejo EXACTO de 0002_core_models.py, salvo la FK a evidencia (no existe
    # en la rama slim): evidencia_id queda como UUID nullable SIN FK.
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("timestamp", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip", INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("accion", sa.String(255), nullable=False),
        sa.Column("evidencia_id", UUID(as_uuid=False), nullable=True),
        sa.Column("proposito", sa.Text, nullable=True),
        sa.Column("hash_prev", sa.String(64), nullable=False, server_default=sa.text("''")),
        sa.Column("hash_self", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )

    # Trigger 1: rechaza UPDATE/DELETE (inmutabilidad en el motor, D1). Solo INSERT.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_no_mutacion()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_log es append-only: % rechazado (cadena de custodia, DD-07)',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_mutacion
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutacion();
        """
    )

    # Trigger 2: encadena hash_prev = hash de la entrada anterior y materializa
    # hash_self de la entrada actual (D2). Toma la ultima entrada por timestamp/id.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_encadenar()
        RETURNS trigger AS $$
        DECLARE
            v_prev text;
            v_genesis constant text := repeat('0', 64);
        BEGIN
            SELECT hash_self INTO v_prev
            FROM audit_log
            ORDER BY timestamp DESC, id DESC
            LIMIT 1;

            IF v_prev IS NULL THEN
                v_prev := v_genesis;
            END IF;

            NEW.hash_prev := v_prev;
            -- hash_self = SHA-256 del contenido canonico (mismo orden que el
            -- dominio en app/domain/audit_chain.py: hash_entrada()).
            NEW.hash_self := encode(
                digest(
                    concat_ws('|',
                        NEW.actor,
                        to_char(NEW.timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                        host(NEW.ip),
                        coalesce(NEW.user_agent, ''),
                        NEW.accion,
                        coalesce(NEW.evidencia_id::text, ''),
                        coalesce(NEW.proposito, ''),
                        NEW.hash_prev
                    ),
                    'sha256'
                ),
                'hex'
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_encadenar
        BEFORE INSERT ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_encadenar();
        """
    )


def downgrade() -> None:
    # Espeja el downgrade de audit_log en 0002 (sin tocar consentimiento/evidencia,
    # inexistentes en slim): triggers -> funciones -> tabla.
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_encadenar ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_mutacion ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_encadenar()")
    op.execute("DROP FUNCTION IF EXISTS audit_log_no_mutacion()")
    op.drop_table("audit_log")
