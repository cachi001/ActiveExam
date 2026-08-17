"""016 - seed corte_conectividad_prolongado como evento critico (rama activeexam).

Revision ID: 0016
Revises: 0014 (branch activeexam)
Create Date: 2026-06-15

RAMA: activeexam
  down_revision = "0014"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Agrega ``corte_conectividad_prolongado`` al catalogo de ``evento_score_config``
  con severidad ``critica`` y peso 100. Es el unico tipo del catalogo del frontend
  (TipoEvento) que aun no tenia entrada en la tabla. Sin detector activo que emita
  este evento todavia; la fila documenta el nivel critico para que
  GET /scoring/config y GET /config/effective lo incluyan.

  INSERT idempotente (ON CONFLICT DO NOTHING): seguro en re-runs.

ROLLBACK:
  alembic downgrade activeexam@0014 -> DELETE de esa fila (paso 2 destructivo separado).

VERIFICACION:
  alembic upgrade activeexam@head -> aplica 0014 -> 0016.
  Espera corte_conectividad_prolongado con severidad=critica, peso=100, activo=true.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0014"
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
