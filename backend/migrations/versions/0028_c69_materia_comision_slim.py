"""0028 - materia + comisión + FK examen_contenido→comisión (slim, C-69 sección 6, D11).

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-28

RAMA: slim
  down_revision = "0027"
  branch_labels = None
  depends_on    = None

PROPÓSITO (D11):
  Modelar materia y comisión como concepto real del producto, pero con la
  asociación examen→comisión OPCIONAL (NULLABLE):
    - materia:  codigo único + nombre.
    - comision: codigo + nombre + FK obligatoria a materia (ON DELETE CASCADE) +
                período/cuatrimestre y año opcionales. Único (materia_id, codigo).
    - examen_contenido.comision_id (ya existe NULLABLE desde 0026) recibe AHORA su
      FK a comision(id) con ON DELETE SET NULL: borrar una comisión NUNCA borra el
      examen ni su contenido — solo se pierde la asociación.

  Migración ADITIVA: tablas nuevas + una FK sobre una columna ya existente. No
  reescribe filas (la columna nace NULL en 0026) ni toca otras tablas (D2).

ROLLBACK:
  alembic downgrade slim@0027 → dropea la FK examen→comisión, luego comision y
  materia (en ese orden por la FK comision→materia). No toca examen_contenido
  (salvo quitarle la FK) ni ninguna otra tabla.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

_FK_EXAMEN_COMISION = "fk_examen_contenido_comision"
_UQ_COMISION = "uq_comision_materia_codigo"
_IX_COMISION_MATERIA = "ix_comision_materia_id"


def upgrade() -> None:
    op.create_table(
        "materia",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("codigo", sa.String(64), nullable=False, unique=True),
        sa.Column("nombre", sa.Text, nullable=False),
    )

    op.create_table(
        "comision",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "materia_id",
            UUID(as_uuid=False),
            sa.ForeignKey("materia.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo", sa.String(64), nullable=False),
        sa.Column("nombre", sa.Text, nullable=False),
        sa.Column("periodo", sa.String(32), nullable=True),
        sa.Column("anio", sa.Integer, nullable=True),
        sa.UniqueConstraint("materia_id", "codigo", name=_UQ_COMISION),
    )
    op.create_index(_IX_COMISION_MATERIA, "comision", ["materia_id"])

    # FK de la columna ya existente examen_contenido.comision_id (NULLABLE, 0026).
    # ON DELETE SET NULL: borrar una comisión deja el examen sin asociación, no lo borra.
    op.create_foreign_key(
        _FK_EXAMEN_COMISION,
        source_table="examen_contenido",
        referent_table="comision",
        local_cols=["comision_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_EXAMEN_COMISION, "examen_contenido", type_="foreignkey")
    op.drop_index(_IX_COMISION_MATERIA, table_name="comision")
    op.drop_table("comision")
    op.drop_table("materia")
