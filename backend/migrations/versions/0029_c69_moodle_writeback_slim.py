"""0029 - write-back de nota a Moodle + respuestas del alumno (slim, C-69 sección 7, D10).

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-28

RAMA: slim
  down_revision = "0028"
  branch_labels = None
  depends_on    = None

PROPÓSITO (D10):
  Persiste el estado del envío de nota a Moodle (idempotencia/reintentos) y
  el audit log de cada intento. También agrega la tabla de respuestas del alumno,
  necesaria para calcular la nota server-side sin confiar en el cliente (D8).

  Tablas nuevas:
  - respuesta_alumno: respuesta del alumno por pregunta en una sesión.
      UNIQUE(session_id, pregunta_id): una respuesta por pregunta.
      FK a proctoring_session y pregunta_examen con ON DELETE CASCADE.
  - moodle_writeback_estado: estado del envío (pendiente/enviado/fallido).
      UNIQUE(session_id): una entrada por sesión (clave de idempotencia).
      El token NUNCA se almacena aquí.
  - moodle_writeback_audit: log append-only de cada intento (sin token).

ROLLBACK:
  alembic downgrade slim@0028 → dropea las 3 tablas nuevas. No toca ninguna
  tabla existente (aditivo, D10).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

_UQ_RESPUESTA = "uq_respuesta_alumno_sesion_pregunta"
_IX_RESPUESTA_SESSION = "ix_respuesta_alumno_session_id"
_IX_AUDIT_SESSION = "ix_moodle_writeback_audit_session_id"


def upgrade() -> None:
    # ── respuesta_alumno ──────────────────────────────────────────────────────
    op.create_table(
        "respuesta_alumno",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pregunta_id",
            UUID(as_uuid=False),
            sa.ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opcion_elegida_id",
            UUID(as_uuid=False),
            sa.ForeignKey("opcion_respuesta.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("session_id", "pregunta_id", name=_UQ_RESPUESTA),
    )
    op.create_index(_IX_RESPUESTA_SESSION, "respuesta_alumno", ["session_id"])

    # ── moodle_writeback_estado ───────────────────────────────────────────────
    op.create_table(
        "moodle_writeback_estado",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("alumno_idnumber", sa.String(255), nullable=True),
        sa.Column("alumno_email", sa.String(320), nullable=True),
        sa.Column("nota", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default="pendiente",
        ),
        sa.Column("intento", sa.Integer, nullable=False, server_default="0"),
        sa.Column("moodle_courseid", sa.Integer, nullable=True),
        sa.Column("moodle_cmid", sa.Integer, nullable=True),
        sa.Column("moodle_userid", sa.Integer, nullable=True),
        sa.Column("error_detalle", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── moodle_writeback_audit ────────────────────────────────────────────────
    op.create_table(
        "moodle_writeback_audit",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alumno_idnumber", sa.String(255), nullable=True),
        sa.Column("nota", sa.Numeric(5, 2), nullable=True),
        sa.Column("moodle_courseid", sa.Integer, nullable=True),
        sa.Column("moodle_cmid", sa.Integer, nullable=True),
        sa.Column("moodle_userid", sa.Integer, nullable=True),
        sa.Column("resultado", sa.String(10), nullable=False),
        sa.Column("error_detalle", sa.Text, nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(_IX_AUDIT_SESSION, "moodle_writeback_audit", ["session_id"])


def downgrade() -> None:
    op.drop_index(_IX_AUDIT_SESSION, table_name="moodle_writeback_audit")
    op.drop_table("moodle_writeback_audit")
    op.drop_table("moodle_writeback_estado")
    op.drop_index(_IX_RESPUESTA_SESSION, table_name="respuesta_alumno")
    op.drop_table("respuesta_alumno")
