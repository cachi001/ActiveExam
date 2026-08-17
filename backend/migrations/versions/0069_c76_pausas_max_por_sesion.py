"""C-76 bloque 4: límite configurable de pausas por sesión
(configuracion_sistema.pausas_max_por_sesion).

Cantidad máxima de pausas en estado aprobada+finalizada que puede acumular una
sesión. Se consume al APROBAR (no al solicitar): el alumno siempre puede pedir,
el límite lo aplica quien aprueba (tutor/coordinador/admin). Default 2.

Aditiva (columna con server_default) — no destructiva.
"""

from alembic import op
import sqlalchemy as sa

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_sistema",
        sa.Column(
            "pausas_max_por_sesion",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion_sistema", "pausas_max_por_sesion")
