"""0057 - Banco de preguntas independiente de exámenes.

Revision ID: 0057
Revises: 0056
Create Date: 2026-08-04

PROPÓSITO:
  Las preguntas del banco viven en su propia tabla (pregunta_banco), ligada
  a materia — no a un examen. Los exámenes referencian las preguntas del banco
  a través de pregunta_examen.pregunta_banco_id (nullable).

  Tablas nuevas:
    - pregunta_banco       — preguntas dueñas, FK materia
    - opcion_banco         — opciones para multichoice/truefalse del banco
    - blank_banco          — blanks cloze del banco
    - opcion_blank_banco   — opciones de cada blank cloze del banco

  Tabla modificada:
    - pregunta_examen: agrega pregunta_banco_id (nullable FK a pregunta_banco)

  Es ADITIVA: no modifica ni elimina columnas existentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pregunta_banco ────────────────────────────────────────────────────────
    op.create_table(
        "pregunta_banco",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("materia_id", sa.UUID(), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("categoria_id", sa.UUID(), nullable=True),
        sa.Column("moodle_question_id", sa.Integer(), nullable=True),
        sa.Column("creada_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_pregunta_banco"),
        sa.ForeignKeyConstraint(
            ["materia_id"], ["materia.id"],
            name="fk_pregunta_banco_materia_id_materia",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["categoria_id"], ["categoria_pregunta.id"],
            name="fk_pregunta_banco_categoria_id_categoria_pregunta",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_pregunta_banco_materia_id", "pregunta_banco", ["materia_id"])
    op.create_index("ix_pregunta_banco_categoria_id", "pregunta_banco", ["categoria_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_pregunta_banco_moodle_question "
        "ON pregunta_banco (materia_id, moodle_question_id) "
        "WHERE moodle_question_id IS NOT NULL"
    )

    # ── opcion_banco ──────────────────────────────────────────────────────────
    op.create_table(
        "opcion_banco",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pregunta_banco_id", sa.UUID(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("es_correcta", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_opcion_banco"),
        sa.ForeignKeyConstraint(
            ["pregunta_banco_id"], ["pregunta_banco.id"],
            name="fk_opcion_banco_pregunta_banco_id_pregunta_banco",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_opcion_banco_pregunta_banco_id", "opcion_banco", ["pregunta_banco_id"])

    # ── blank_banco ───────────────────────────────────────────────────────────
    op.create_table(
        "blank_banco",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pregunta_banco_id", sa.UUID(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("texto_antes", sa.Text(), nullable=True),
        sa.Column("texto_despues", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_blank_banco"),
        sa.ForeignKeyConstraint(
            ["pregunta_banco_id"], ["pregunta_banco.id"],
            name="fk_blank_banco_pregunta_banco_id_pregunta_banco",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_blank_banco_pregunta_banco_id", "blank_banco", ["pregunta_banco_id"])

    # ── opcion_blank_banco ────────────────────────────────────────────────────
    op.create_table(
        "opcion_blank_banco",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("blank_banco_id", sa.UUID(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("es_correcta", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("peso", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_opcion_blank_banco"),
        sa.ForeignKeyConstraint(
            ["blank_banco_id"], ["blank_banco.id"],
            name="fk_opcion_blank_banco_blank_banco_id_blank_banco",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_opcion_blank_banco_blank_banco_id", "opcion_blank_banco", ["blank_banco_id"])

    # ── pregunta_examen: agrega pregunta_banco_id (trazabilidad) ──────────────
    op.add_column(
        "pregunta_examen",
        sa.Column("pregunta_banco_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pregunta_examen_pregunta_banco_id_pregunta_banco",
        "pregunta_examen", "pregunta_banco",
        ["pregunta_banco_id"], ["id"],
        ondelete="SET NULL",
    )

    # Backfill: migrar preguntas existentes (pregunta_examen con comision/materia)
    # al banco, luego linkear pregunta_examen.pregunta_banco_id.
    op.execute("""
        INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id, moodle_question_id)
        SELECT
            gen_random_uuid(),
            c.materia_id,
            pe.enunciado,
            pe.tipo,
            pe.categoria_id,
            pe.moodle_question_id
        FROM pregunta_examen pe
        JOIN examen_contenido ec ON pe.examen_id = ec.id
        JOIN comision c ON ec.comision_id = c.id
        WHERE pe.pregunta_banco_id IS NULL
    """)
    op.execute("""
        UPDATE pregunta_examen pe
        SET pregunta_banco_id = pb.id
        FROM pregunta_banco pb
        JOIN examen_contenido ec ON ec.comision_id IS NOT NULL
        JOIN comision c ON ec.comision_id = c.id AND c.materia_id = pb.materia_id
        WHERE pe.examen_id = ec.id
          AND pe.enunciado = pb.enunciado
          AND pe.pregunta_banco_id IS NULL
    """)


def downgrade() -> None:
    op.drop_constraint(
        "fk_pregunta_examen_pregunta_banco_id_pregunta_banco",
        "pregunta_examen",
        type_="foreignkey",
    )
    op.drop_column("pregunta_examen", "pregunta_banco_id")
    op.drop_table("opcion_blank_banco")
    op.drop_table("blank_banco")
    op.drop_table("opcion_banco")
    op.execute("DROP INDEX IF EXISTS uq_pregunta_banco_moodle_question")
    op.drop_table("pregunta_banco")
