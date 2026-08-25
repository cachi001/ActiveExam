"""0088 - c-78 E-04: materia_profesor (pertenencia del rol PROFESOR).

Revision ID: 0088
Revises: 0087
Create Date: 2026-08-24

PROPOSITO:
  c-78 suma el rol PROFESOR, que cubre el hueco entre TUTOR (no crea examenes ni
  toca el banco) y COORDINADOR (emite el VEREDICTO de integridad). El PROFESOR es
  un rol de MATERIA: arma los examenes y el banco de preguntas de toda la materia.

  Necesita su propia membresia. Se espeja `materia_coordinador` (migracion 0086):
  tabla puente aditiva, UNIQUE(materia_id, profesor_id), indices en ambas
  direcciones, ON DELETE CASCADE en las dos FKs.

POR QUE UNA TABLA PROPIA Y NO REUSAR `materia_coordinador`:
  Porque las dos membresias otorgan cosas DISTINTAS. El coordinador puede anular
  una nota por fraude; el profesor no (D11, regla dura #5: quien pone la nota no
  decide si hubo fraude). Colapsarlas en una sola tabla convertiria "asignar un
  profesor" en "darle el poder de anular notas" sin que nadie lo pidiera.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: tabla NUEVA, sin backfill y sin tocar ninguna existente. Ningun
  lector previo se rompe.

REVERSIBILIDAD (downgrade):
  Dropea la tabla. Se pierden las asignaciones profesor->materia (habria que
  volver a hacerlas); no se pierde ningun usuario, materia ni examen.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None

_UQ = "uq_materia_profesor_materia_profesor"
_IX_MATERIA = "ix_materia_profesor_materia_id"
_IX_PROFESOR = "ix_materia_profesor_profesor_id"


def upgrade() -> None:
    op.create_table(
        "materia_profesor",
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
        sa.Column(
            "profesor_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("materia_id", "profesor_id", name=_UQ),
    )
    op.create_index(_IX_MATERIA, "materia_profesor", ["materia_id"])
    op.create_index(_IX_PROFESOR, "materia_profesor", ["profesor_id"])


def downgrade() -> None:
    op.drop_index(_IX_PROFESOR, table_name="materia_profesor")
    op.drop_index(_IX_MATERIA, table_name="materia_profesor")
    op.drop_table("materia_profesor")
