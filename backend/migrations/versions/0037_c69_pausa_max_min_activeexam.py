"""C-69: límite de duración de la pausa autorizada (configuracion_sistema.pausa_max_min).

Minutos máximos que puede durar una pausa autorizada antes de reanudarse sola
(evita que la pausa se use para hacer tiempo / copiarse). Default 10.

Aditiva (columna con server_default) — no destructiva.
"""

from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_sistema",
        sa.Column(
            "pausa_max_min",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion_sistema", "pausa_max_min")
