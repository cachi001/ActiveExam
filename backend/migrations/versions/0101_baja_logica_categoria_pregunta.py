"""0101 - baja logica de las categorias del banco.

Revision ID: 0101
Revises: 0100
Create Date: 2026-08-27

PROPOSITO:
  `DELETE /categorias/{id}` hacia un DELETE FISICO. Por el ON DELETE CASCADE de
  `categoria_padre_id` se llevaba puestas TODAS las subcategorias, y por el
  SET NULL de `pregunta_banco.categoria_id` mandaba sus preguntas a "Sin
  clasificar". Con un banco organizado en unidades y bloques, un solo click
  destruia la organizacion entera y no habia forma de deshacerlo: las preguntas
  sobrevivian, pero saber a cual categoria pertenecia cada una ya no.

  Con baja logica la categoria y su rama salen del arbol, las preguntas
  conservan su `categoria_id`, y todo se puede reactivar.

MISMO PATRON que materia, comision, examen, usuario y (0100) pregunta del banco:
NULL = vigente, timestamp = dada de baja.

SOBRE LA CASCADA:
  El ON DELETE CASCADE del esquema se conserva, pero deja de dispararse porque
  ya no se hace DELETE. La baja de una rama se resuelve en la aplicacion
  marcando la categoria y sus descendientes, para que el arbol no quede con
  subcategorias colgando de un padre invisible.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: una columna aditiva y NULLABLE, sin backfill. Lo ya cargado queda
  con NULL, o sea vigente, que es el comportamiento de hoy.

REVERSIBILIDAD (downgrade):
  Dropea el indice y la columna. Las categorias dadas de baja vuelven a estar
  vigentes: sin la columna no hay forma de expresar la baja, y mostrar de mas es
  preferible a que desaparezca contenido.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categoria_pregunta",
        sa.Column(
            "eliminada_en",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Baja logica: NULL = vigente, con timestamp = dada de baja.",
        ),
    )
    # Parcial: el arbol pide SOLO las vigentes, que es el caso frecuente.
    op.create_index(
        "ix_categoria_pregunta_materia_vigentes",
        "categoria_pregunta",
        ["materia_id"],
        postgresql_where=sa.text("eliminada_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_categoria_pregunta_materia_vigentes", table_name="categoria_pregunta"
    )
    op.drop_column("categoria_pregunta", "eliminada_en")
