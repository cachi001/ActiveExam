"""017 - seed corte_conectividad_prolongado como evento critico (rama FULL).

Revision ID: 0017
Revises: 0015 (rama principal/full)
Create Date: 2026-06-15

RAMA: full (principal, con TimescaleDB)
  down_revision = "0015"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Espeja en la rama FULL el seed de ``corte_conectividad_prolongado`` creado en
  slim por 0016: INSERT idempotente en ``evento_score_config`` con severidad
  ``critica`` y peso 100.

ROLLBACK:
  alembic downgrade 0015 -> DELETE de esa fila (destructivo, paso 2 separado).

VERIFICACION:
  alembic upgrade head -> aplica 0015 -> 0017 sobre la rama full.
  Espera corte_conectividad_prolongado con severidad=critica, peso=100, activo=true.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO evento_score_config "
            "(tipo_evento, severidad, peso, descripcion, activo) "
            "VALUES (:tipo, :sev, :peso, :desc, :activo) "
            "ON CONFLICT (tipo_evento) DO NOTHING"
        ),
        {
            "tipo": "corte_conectividad_prolongado",
            "sev": "critica",
            "peso": 100,
            "desc": (
                "Se perdio la conexion con el servidor de monitoreo "
                "por un periodo prolongado."
            ),
            "activo": True,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM evento_score_config "
            "WHERE tipo_evento = 'corte_conectividad_prolongado'"
        )
    )
