"""0058 - Propiedad de la organización del banco de preguntas.

Revision ID: 0058
Revises: 0057
Create Date: 2026-08-05

PROPÓSITO:
  El docente organiza su banco de preguntas y el sync/import de Moodle NO debe
  pisarle esa organización. Dos piezas:

  1. ``pregunta_banco.categoria_manual`` (bool, default false)
     Se marca en true cuando el docente mueve la pregunta de categoría a mano.
     A partir de ahí, import y sync dejan ``categoria_id`` intacto — el enunciado
     y las opciones SÍ se siguen actualizando desde Moodle.

  2. ``categoria_pregunta.moodle_category_id`` (int, nullable)
     Identidad estable de la categoría en Moodle. Hasta ahora el sync matcheaba
     por ``(nombre, padre_id)``: si el docente renombraba la categoría, el sync
     no la reconocía y creaba un duplicado. Con el id de Moodle anclado, el
     rename local es seguro y el nombre local nunca se pisa.

  3. ``categoria_pregunta.moodle_nombre_origen`` (text, nullable)
     El XML de Moodle NO trae el id de categoría, solo la ruta de nombres. Para
     que el rename local tampoco rompa el import por XML, guardamos el nombre
     con el que Moodle la nombró. El import matchea por ese nombre de origen y
     respeta el nombre que le puso el docente.

  Backfill: las categorías que ya existen se asumen de origen Moodle con su
  nombre actual (es como se las venía matcheando). Así el primer import/sync
  posterior a esta migración las reconoce en vez de duplicarlas.

  Es ADITIVA: no elimina columnas ni datos existentes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pregunta_banco.categoria_manual ───────────────────────────────────────
    # Las preguntas ya existentes arrancan en false: nunca fueron movidas a mano
    # de forma rastreable, así que se comportan como hasta ahora hasta que el
    # docente las toque.
    op.add_column(
        "pregunta_banco",
        sa.Column(
            "categoria_manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ── categoria_pregunta.moodle_category_id ─────────────────────────────────
    op.add_column(
        "categoria_pregunta",
        sa.Column("moodle_category_id", sa.Integer(), nullable=True),
    )
    # Índice único parcial: una categoría de Moodle se mapea a lo sumo a una
    # categoría local por materia. NULL queda fuera (categorías creadas a mano
    # o importadas por XML, que no tienen contraparte conocida en Moodle).
    op.execute(
        "CREATE UNIQUE INDEX uq_categoria_pregunta_moodle_category "
        "ON categoria_pregunta (materia_id, moodle_category_id) "
        "WHERE moodle_category_id IS NOT NULL"
    )

    # ── categoria_pregunta.moodle_nombre_origen ───────────────────────────────
    op.add_column(
        "categoria_pregunta",
        sa.Column("moodle_nombre_origen", sa.Text(), nullable=True),
    )
    # Backfill: hasta ahora el match era por nombre, así que el nombre actual ES
    # el nombre de origen para todo lo que ya existe.
    op.execute(
        "UPDATE categoria_pregunta "
        "SET moodle_nombre_origen = nombre "
        "WHERE moodle_nombre_origen IS NULL"
    )
    op.create_index(
        "ix_categoria_pregunta_moodle_nombre_origen",
        "categoria_pregunta",
        ["materia_id", "moodle_nombre_origen"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_categoria_pregunta_moodle_nombre_origen",
        table_name="categoria_pregunta",
    )
    op.drop_column("categoria_pregunta", "moodle_nombre_origen")
    op.execute("DROP INDEX IF EXISTS uq_categoria_pregunta_moodle_category")
    op.drop_column("categoria_pregunta", "moodle_category_id")
    op.drop_column("pregunta_banco", "categoria_manual")
