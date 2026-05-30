"""002 - modelo de datos del dominio: tablas, enum de Sesion, audit log
append-only (trigger + hash encadenado), Consentimiento inmutable, y el Evento
como hypertable TimescaleDB (indices + compresion + continuous aggregates).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-30

Scope (C-05, core-models). Sobre la 001 que dejo habilitada la extension
TimescaleDB. Materializa las invariantes EN EL MOTOR (no solo en la aplicacion):
- ``estado`` de Sesion restringido al ENUM ``estado_sesion`` (D3).
- ``audit_log`` con trigger BEFORE UPDATE/DELETE que ABORTA la operacion (D1) y
  trigger BEFORE INSERT que encadena ``hash_prev`` + materializa ``hash_self`` (D2).
- ``consentimiento`` con trigger anti-UPDATE/DELETE (inmutabilidad, D5).
- ``evento`` como hypertable particionada por dia + indices + compresion 7d/>7d +
  continuous aggregates base (D4).

CONVENCION DESTRUCTIVA EN DOS PASOS (expand/contract): el ``downgrade`` revierte
en dos fases ordenadas -- (1) agregados/policies/triggers/hypertable, (2) tablas y
tipo enum -- de modo que el esquema vuelve al estado post-001 (extension presente,
sin tablas de dominio) sin pasos destructivos mezclados con creacion.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


# Valores del enum del ciclo de vida de la Sesion (`04` Sesion).
_ESTADOS_SESION = ("iniciada", "activa", "finalizada", "flaggeada", "cerrada")


def upgrade() -> None:
    # gen_random_uuid() vive en pgcrypto (default en server_default de las PK).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- ENUM de estado de Sesion (D3) -------------------------------------
    op.execute(
        "CREATE TYPE estado_sesion AS ENUM "
        "('iniciada', 'activa', 'finalizada', 'flaggeada', 'cerrada')"
    )

    estado_sesion = sa.Enum(*_ESTADOS_SESION, name="estado_sesion", create_type=False)

    # --- Tablas transaccionales (cardinalidades del ERD, `04`) -------------
    op.create_table(
        "usuario",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("id_institucional", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("roles", JSONB, server_default="[]", nullable=False),
        sa.Column("attrs_federados", JSONB, server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint("id_institucional", name="uq_usuario_id_institucional"),
    )

    op.create_table(
        "examen",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("umbral_score", sa.Float, nullable=False),
        sa.Column("parametros", JSONB, server_default="{}", nullable=False),
        sa.Column("detectores", JSONB, server_default="[]", nullable=False),
        sa.Column("ventana", JSONB, server_default="{}", nullable=False),
        sa.Column("retencion", JSONB, server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_examen"),
    )

    op.create_table(
        "sesion",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), nullable=False),
        sa.Column("exam_id", UUID(as_uuid=False), nullable=False),
        # Restriccion de estado en el MOTOR: el ENUM rechaza valores fuera de la
        # lista aun por fuera de la aplicacion (D3, capability session-lifecycle-enum).
        sa.Column("estado", estado_sesion, server_default="iniciada", nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("clave_sesion", sa.String(255), nullable=False),
        sa.Column("creada_en", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizada_en", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sesion"),
        sa.ForeignKeyConstraint(["user_id"], ["usuario.id"], name="fk_sesion_user_id_usuario"),
        sa.ForeignKeyConstraint(["exam_id"], ["examen.id"], name="fk_sesion_exam_id_examen"),
    )

    op.create_table(
        "asignacion",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proctor_id", UUID(as_uuid=False), nullable=False),
        sa.Column("exam_id", UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_asignacion"),
        sa.ForeignKeyConstraint(["proctor_id"], ["usuario.id"], name="fk_asignacion_proctor_id_usuario"),
        sa.ForeignKeyConstraint(["exam_id"], ["examen.id"], name="fk_asignacion_exam_id_examen"),
        # *—* materializada: un proctor no se asigna dos veces al mismo examen.
        sa.UniqueConstraint("proctor_id", "exam_id", name="uq_asignacion_proctor_exam"),
    )

    op.create_table(
        "consentimiento",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), nullable=False),
        sa.Column("exam_id", UUID(as_uuid=False), nullable=False),
        sa.Column("version_texto", sa.String(64), nullable=False),
        sa.Column("timestamp", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_consentimiento"),
        sa.ForeignKeyConstraint(["user_id"], ["usuario.id"], name="fk_consentimiento_user_id_usuario"),
        sa.ForeignKeyConstraint(["exam_id"], ["examen.id"], name="fk_consentimiento_exam_id_examen"),
    )

    op.create_table(
        "embedding",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), nullable=False),
        # BYTEA: vector CIFRADO at-rest (ciphertext del KMS), nunca en claro (D5, SU-08).
        sa.Column("vector_cifrado", sa.LargeBinary, nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("fecha", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_embedding"),
        sa.ForeignKeyConstraint(["user_id"], ["usuario.id"], name="fk_embedding_user_id_usuario"),
    )

    op.create_table(
        "evidencia",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=False), nullable=False),
        sa.Column("uri_bucket", sa.Text, nullable=False),
        sa.Column("hash_cliente", sa.String(128), nullable=True),
        sa.Column("firma_cliente", sa.Text, nullable=True),
        sa.Column("hash_backend", sa.String(128), nullable=True),
        sa.Column("firma_maestra", sa.Text, nullable=True),
        sa.Column("output_reinferencia", JSONB, server_default="{}", nullable=False),
        sa.Column("meta", JSONB, server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_evidencia"),
        sa.ForeignKeyConstraint(["session_id"], ["sesion.id"], name="fk_evidencia_session_id_sesion"),
    )

    op.create_table(
        "caso_disciplinario",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=False), nullable=False),
        sa.Column("estado", sa.String(64), nullable=False),
        sa.Column("refs_evidencia", JSONB, server_default="[]", nullable=False),
        sa.Column("decisiones", JSONB, server_default="[]", nullable=False),
        sa.Column("vinculo_externo", sa.Text, nullable=True),
        sa.Column("hold", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_caso_disciplinario"),
        sa.ForeignKeyConstraint(["session_id"], ["sesion.id"], name="fk_caso_disciplinario_session_id_sesion"),
    )

    # --- Audit log: tabla append-only con hash encadenado (DD-07, D1+D2) ----
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
        sa.ForeignKeyConstraint(["evidencia_id"], ["evidencia.id"], name="fk_audit_log_evidencia_id_evidencia"),
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

    # --- Consentimiento inmutable (D5): rechaza UPDATE/DELETE -----------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION consentimiento_no_mutacion()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'consentimiento es inmutable: % rechazado (DD-13, Ley 25.326)',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_consentimiento_no_mutacion
        BEFORE UPDATE OR DELETE ON consentimiento
        FOR EACH ROW EXECUTE FUNCTION consentimiento_no_mutacion();
        """
    )

    # --- Evento: HYPERTABLE TimescaleDB (D4, `04` Evento, SU-06) -------------
    op.create_table(
        "evento",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        # Columna de particionado: debe formar parte de toda clave unica/PK.
        sa.Column("timestamp", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=False), nullable=False),
        sa.Column("exam_id", UUID(as_uuid=False), nullable=False),
        sa.Column("tipo", sa.String(64), nullable=False),
        sa.Column("severidad", sa.String(32), nullable=False),
        sa.Column("timestamp_cliente", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("timestamp_backend", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload", JSONB, server_default="{}", nullable=False),
        # Firma HMAC-SHA256: la VALIDACION de produccion es C-10 (aqui solo la columna).
        sa.Column("firma", sa.Text, nullable=True),
        sa.Column("schema_version", sa.Integer, server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id", "timestamp", name="pk_evento"),
    )

    # Convierte evento en hypertable particionada por DIA (chunks de 1 dia).
    op.execute(
        "SELECT create_hypertable("
        "'evento', 'timestamp', "
        "chunk_time_interval => INTERVAL '1 day', "
        "if_not_exists => TRUE)"
    )

    # Indices obligatorios del modelo (`04` Evento).
    op.create_index("ix_evento_session_ts", "evento", ["session_id", "timestamp"])
    op.create_index("ix_evento_exam_ts", "evento", ["exam_id", "timestamp"])

    # --- Compresion escalonada: chunks <7d sin comprimir, >7d comprimidos ----
    op.execute(
        """
        ALTER TABLE evento SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'session_id',
            timescaledb.compress_orderby = 'timestamp DESC'
        )
        """
    )
    op.execute("SELECT add_compression_policy('evento', INTERVAL '7 days')")

    # --- Continuous aggregates base (`04` Evento, CQRS-lite, D4) -------------
    # 1) eventos por sesion por minuto.
    op.execute(
        """
        CREATE MATERIALIZED VIEW cagg_eventos_sesion_min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', timestamp) AS bucket,
            session_id,
            count(*) AS eventos
        FROM evento
        GROUP BY bucket, session_id
        WITH NO DATA;
        """
    )
    # 2) score por sesion: severidad agregada por sesion por minuto (proxy de score).
    op.execute(
        """
        CREATE MATERIALIZED VIEW cagg_score_sesion
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', timestamp) AS bucket,
            session_id,
            count(*) FILTER (WHERE severidad IN ('alta', 'critica')) AS eventos_severos,
            count(*) AS eventos_total
        FROM evento
        GROUP BY bucket, session_id
        WITH NO DATA;
        """
    )
    # 3) sesiones activas por examen (sesiones distintas con actividad por minuto).
    op.execute(
        """
        CREATE MATERIALIZED VIEW cagg_sesiones_activas_examen
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', timestamp) AS bucket,
            exam_id,
            count(DISTINCT session_id) AS sesiones_activas
        FROM evento
        GROUP BY bucket, exam_id
        WITH NO DATA;
        """
    )
    # 4) distribucion por tipo (por examen, por minuto).
    op.execute(
        """
        CREATE MATERIALIZED VIEW cagg_distribucion_tipo
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 minute', timestamp) AS bucket,
            exam_id,
            tipo,
            count(*) AS eventos
        FROM evento
        GROUP BY bucket, exam_id, tipo
        WITH NO DATA;
        """
    )

    # Politicas de refresco de los agregados (materializacion incremental).
    for cagg in (
        "cagg_eventos_sesion_min",
        "cagg_score_sesion",
        "cagg_sesiones_activas_examen",
        "cagg_distribucion_tipo",
    ):
        op.execute(
            f"""
            SELECT add_continuous_aggregate_policy('{cagg}',
                start_offset => INTERVAL '1 hour',
                end_offset => INTERVAL '1 minute',
                schedule_interval => INTERVAL '1 minute')
            """
        )


def downgrade() -> None:
    # PASO 1 (CONTRACT - efimero): quitar agregados, politicas, triggers e
    # hypertable. Se eliminan ANTES que las tablas para no dejar objetos colgados.
    for cagg in (
        "cagg_distribucion_tipo",
        "cagg_sesiones_activas_examen",
        "cagg_score_sesion",
        "cagg_eventos_sesion_min",
    ):
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {cagg} CASCADE")

    op.execute("DROP TRIGGER IF EXISTS trg_consentimiento_no_mutacion ON consentimiento")
    op.execute("DROP FUNCTION IF EXISTS consentimiento_no_mutacion()")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_encadenar ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_mutacion ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_encadenar()")
    op.execute("DROP FUNCTION IF EXISTS audit_log_no_mutacion()")

    op.drop_index("ix_evento_exam_ts", table_name="evento")
    op.drop_index("ix_evento_session_ts", table_name="evento")
    # DROP TABLE elimina tambien la hypertable y sus chunks/politica de compresion.
    op.drop_table("evento")

    # PASO 2 (CONTRACT): eliminar las tablas transaccionales en orden inverso de
    # dependencias (FKs) y el tipo enum. El esquema vuelve al estado post-001.
    op.drop_table("audit_log")
    op.drop_table("caso_disciplinario")
    op.drop_table("evidencia")
    op.drop_table("embedding")
    op.drop_table("consentimiento")
    op.drop_table("asignacion")
    op.drop_table("sesion")
    op.drop_table("examen")
    op.drop_table("usuario")

    op.execute("DROP TYPE IF EXISTS estado_sesion")
