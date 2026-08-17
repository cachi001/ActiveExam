"""0026 - examen de contenido + preguntas + opciones (activeexam, C-69 secciones 1-2).

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-27

RAMA: activeexam
  down_revision = "0025"
  branch_labels = None
  depends_on    = None

PROPÓSITO:
  Sección 1 — tablas para el modelo de contenido de examen (C-69):
    - examen_contenido: examen importado desde Moodle XML (comision_id NULLABLE, D11).
    - pregunta_examen:  preguntas con tipo multichoice/truefalse.
    - opcion_respuesta: opciones con es_correcta server-side (D3, regla dura #6).

  Migración ADITIVA (tablas nuevas). Un solo paso — no afecta tablas existentes (D2).
  La FK examen_contenido.comision_id → comision se agrega en sección 6.

ROLLBACK:
  alembic downgrade activeexam@0025 → dropea opcion_respuesta, pregunta_examen,
  examen_contenido (en ese orden por FK). No toca proctoring_session, exam_config
  ni ninguna tabla existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "examen_contenido",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("titulo", sa.Text, nullable=False),
        sa.Column(
            "comision_id",
            UUID(as_uuid=False),
            nullable=True,
            comment="FK a comision se añade en sección 6 (D11: nullable, sin FK por ahora).",
        ),
    )

    op.create_table(
        "pregunta_examen",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "examen_id",
            UUID(as_uuid=False),
            sa.ForeignKey("examen_contenido.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enunciado", sa.Text, nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("orden", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_pregunta_examen_examen_id", "pregunta_examen", ["examen_id"])

    op.create_table(
        "opcion_respuesta",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "pregunta_id",
            UUID(as_uuid=False),
            sa.ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column(
            "es_correcta",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="D3: solo server-side, NUNCA al cliente.",
        ),
        sa.Column("orden", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_opcion_respuesta_pregunta_id", "opcion_respuesta", ["pregunta_id"])


def downgrade() -> None:
    op.drop_index("ix_opcion_respuesta_pregunta_id", table_name="opcion_respuesta")
    op.drop_table("opcion_respuesta")
    op.drop_index("ix_pregunta_examen_examen_id", table_name="pregunta_examen")
    op.drop_table("pregunta_examen")
    op.drop_table("examen_contenido")
