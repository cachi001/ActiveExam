"""062 - respuesta_alumno_cloze: respuestas de blanks (cloze/ddwtos) por sesión.

Revision ID: 0062
Revises: 0061
Create Date: 2026-08-10

PROPOSITO:
  `respuesta_alumno` (migración 0029) exige `opcion_elegida_id` NOT NULL con FK
  a `opcion_respuesta` — solo sirve para multichoice/truefalse. Una pregunta
  cloze/ddwtos no tiene filas en `opcion_respuesta` (sus opciones viven por-blank
  en `opcion_cloze_blank`), así que hoy NO HAY forma de persistir la respuesta de
  un blank: el alumno la contesta en la UI pero nunca llega a calificarse
  (`calcular_nota_academica` soporta `respuesta_cloze` pero ningún endpoint lo
  alimentaba — toda pregunta cloze/ddwtos puntuaba 0 siempre).

  `respuesta_alumno_cloze` guarda, por blank, el id de la opción elegida (blank
  MULTICHOICE) o el texto libre tipeado (blank SHORTANSWER) — mismo contrato que
  `RespuestaAlumno.respuesta_cloze` en grade_calculator.py.

  UNIQUE(session_id, blank_id): una respuesta por blank por sesión (upsert).
  FK a proctoring_session, pregunta_examen y pregunta_cloze_blank, ON DELETE CASCADE.

ROLLBACK:
  alembic downgrade slim@0061 → dropea la tabla nueva. No toca nada existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

_UQ = "uq_respuesta_alumno_cloze_sesion_blank"
_IX_SESSION = "ix_respuesta_alumno_cloze_session_id"


def upgrade() -> None:
    op.create_table(
        "respuesta_alumno_cloze",
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
            "blank_id",
            UUID(as_uuid=False),
            sa.ForeignKey("pregunta_cloze_blank.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valor", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("session_id", "blank_id", name=_UQ),
    )
    op.create_index(_IX_SESSION, "respuesta_alumno_cloze", ["session_id"])


def downgrade() -> None:
    op.drop_index(_IX_SESSION, table_name="respuesta_alumno_cloze")
    op.drop_table("respuesta_alumno_cloze")
