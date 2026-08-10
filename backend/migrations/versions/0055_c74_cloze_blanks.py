"""055 - C-74: tablas pregunta_cloze_blank y opcion_cloze_blank.

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-03

RAMA: slim
  down_revision = "0054"

PROPOSITO:
  Modelo de datos para preguntas cloze (rellenar huecos):
    - pregunta_cloze_blank: un hueco dentro de una pregunta cloze
      (orden, tipo, contexto antes/después del hueco).
    - opcion_cloze_blank: cada opción de respuesta para un hueco
      (texto, es_correcta, peso [0-100]).

  Soporta MULTICHOICE, MULTICHOICE_S y SHORTANSWER del formato Moodle.
  Es ADITIVA: no modifica ninguna tabla existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pregunta_cloze_blank",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "pregunta_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("orden", sa.Integer, nullable=False),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column("texto_antes", sa.Text, nullable=True),
        sa.Column("texto_despues", sa.Text, nullable=True),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pregunta_cloze_blank_pregunta_orden",
        "pregunta_cloze_blank",
        ["pregunta_id", "orden"],
    )

    op.create_table(
        "opcion_cloze_blank",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "blank_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("pregunta_cloze_blank.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("es_correcta", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("peso", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_opcion_cloze_blank_blank_id",
        "opcion_cloze_blank",
        ["blank_id"],
    )


def downgrade() -> None:
    op.drop_table("opcion_cloze_blank")
    op.drop_table("pregunta_cloze_blank")
