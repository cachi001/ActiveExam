"""0086 - comision_tutor + materia_coordinador: modelo N:M de pertenencia (c-79).

Revision ID: 0086
Revises: 0085
Create Date: 2026-08-22

RAMA: activeexam
  down_revision = "0085"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Hasta acá, `comision.docente_id` era una FK 1:1 (una comisión, a lo sumo un
  tutor) y el rol COORDINADOR tenía alcance GLOBAL (bypass total de pertenencia,
  igual que admin_sistema). El dueño decidió alinear esto con el modelo de su
  otro sistema (Sistema-de-Reserva-Salon / active-ia-correccion-automatica):

  - `comision_tutor`: M:N entre usuario (tutor) y comision. Un tutor puede estar
    a cargo de varias comisiones; una comisión puede tener varios tutores
    (co-dictado, cobertura de licencias, sin perder el historial del titular).
  - `materia_coordinador`: M:N entre usuario (coordinador) y materia. El
    coordinador deja de tener alcance global — queda acotado a SUS materias,
    igual que el tutor queda acotado a SUS comisiones. admin_sistema es el
    ÚNICO rol con alcance global de acá en más.

  Mismo patrón que `inscripcion` (migración 0035): tabla puente aditiva,
  UNIQUE(a, b), índices en ambas direcciones, ON DELETE CASCADE.

BACKFILL:
  Cada `comision.docente_id` NOT NULL existente se copia a una fila de
  `comision_tutor` (preserva quién era el titular antes de esta migración).
  `comision.docente_id` NO se toca ni se dropea acá — migración destructiva en
  dos pasos (regla dura de código): esta es la primera (aditiva + backfill); una
  migración posterior, una vez que el código deje de leer/escribir la columna,
  la dropea.

ROLLBACK:
  alembic downgrade activeexam@0085 -> dropea ambas tablas (backfill incluido,
  no hay pérdida de la columna original `docente_id` porque nunca se tocó).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None

_UQ_COMISION_TUTOR = "uq_comision_tutor_comision_tutor"
_IX_COMISION_TUTOR_COMISION = "ix_comision_tutor_comision_id"
_IX_COMISION_TUTOR_TUTOR = "ix_comision_tutor_tutor_id"

_UQ_MATERIA_COORDINADOR = "uq_materia_coordinador_materia_coordinador"
_IX_MATERIA_COORDINADOR_MATERIA = "ix_materia_coordinador_materia_id"
_IX_MATERIA_COORDINADOR_COORDINADOR = "ix_materia_coordinador_coordinador_id"


def upgrade() -> None:
    op.create_table(
        "comision_tutor",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "comision_id",
            UUID(as_uuid=False),
            sa.ForeignKey("comision.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tutor_id",
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
        sa.UniqueConstraint("comision_id", "tutor_id", name=_UQ_COMISION_TUTOR),
    )
    op.create_index(_IX_COMISION_TUTOR_COMISION, "comision_tutor", ["comision_id"])
    op.create_index(_IX_COMISION_TUTOR_TUTOR, "comision_tutor", ["tutor_id"])

    op.create_table(
        "materia_coordinador",
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
            "coordinador_id",
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
        sa.UniqueConstraint("materia_id", "coordinador_id", name=_UQ_MATERIA_COORDINADOR),
    )
    op.create_index(_IX_MATERIA_COORDINADOR_MATERIA, "materia_coordinador", ["materia_id"])
    op.create_index(
        _IX_MATERIA_COORDINADOR_COORDINADOR, "materia_coordinador", ["coordinador_id"]
    )

    # Backfill: cada docente_id existente se preserva como fila de comision_tutor.
    op.execute(
        sa.text(
            """
            INSERT INTO comision_tutor (comision_id, tutor_id)
            SELECT id, docente_id FROM comision WHERE docente_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(_IX_MATERIA_COORDINADOR_COORDINADOR, table_name="materia_coordinador")
    op.drop_index(_IX_MATERIA_COORDINADOR_MATERIA, table_name="materia_coordinador")
    op.drop_table("materia_coordinador")

    op.drop_index(_IX_COMISION_TUTOR_TUTOR, table_name="comision_tutor")
    op.drop_index(_IX_COMISION_TUTOR_COMISION, table_name="comision_tutor")
    op.drop_table("comision_tutor")
