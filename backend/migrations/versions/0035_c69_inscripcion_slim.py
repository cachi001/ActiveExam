"""0035 - inscripción alumno↔comisión (slim, C-69).

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-29

RAMA: slim
  down_revision = "0034"
  branch_labels = None
  depends_on    = None

PROPÓSITO:
  Modelar la INSCRIPCIÓN de alumnos a comisiones como tabla puente M:N entre
  usuario y comision:
    - inscripcion: id (PK) + usuario_id (FK usuario.id ON DELETE CASCADE) +
      comision_id (FK comision.id ON DELETE CASCADE) + created_at.
    - UNIQUE(usuario_id, comision_id): un alumno NO puede inscribirse dos veces a
      la misma comisión (el segundo intento → 409 duplicado).
    - Índices por comision_id (listar inscriptos de una comisión) y usuario_id
      (listar comisiones de un alumno).

  Migración ADITIVA: una tabla nueva con dos FKs. No reescribe filas ni toca usuario
  ni comision (D2).

ROLLBACK:
  alembic downgrade slim@0034 → dropea la tabla inscripcion (sus FKs/índices/unique
  caen con ella). No toca ninguna otra tabla.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

_UQ_INSCRIPCION = "uq_inscripcion_usuario_comision"
_IX_INSCRIPCION_COMISION = "ix_inscripcion_comision_id"
_IX_INSCRIPCION_USUARIO = "ix_inscripcion_usuario_id"


def upgrade() -> None:
    op.create_table(
        "inscripcion",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comision_id",
            UUID(as_uuid=False),
            sa.ForeignKey("comision.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("usuario_id", "comision_id", name=_UQ_INSCRIPCION),
    )
    op.create_index(_IX_INSCRIPCION_COMISION, "inscripcion", ["comision_id"])
    op.create_index(_IX_INSCRIPCION_USUARIO, "inscripcion", ["usuario_id"])


def downgrade() -> None:
    op.drop_index(_IX_INSCRIPCION_USUARIO, table_name="inscripcion")
    op.drop_index(_IX_INSCRIPCION_COMISION, table_name="inscripcion")
    op.drop_table("inscripcion")
