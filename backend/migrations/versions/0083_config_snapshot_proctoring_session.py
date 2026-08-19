"""0083 - snapshot de config del sistema al iniciar la sesion de proctoring.

Revision ID: 0083
Revises: 0082
Create Date: 2026-08-19

PROPOSITO:
  Hoy el score de riesgo y el umbral de cola de revision se leen SIEMPRE de la
  config VIVA (configuracion_sistema/evento_score_config), sin importar cuando
  se rindio la sesion. Si un admin cambia el umbral o los pesos de scoring, el
  cambio se aplica retroactivamente a sesiones ya rendidas (o en curso) la
  proxima vez que alguien las mira o se evalua el gate de sincronizacion a
  Moodle. Eso viola la regla de producto: un cambio de config solo debe regir
  para examenes rendidos DESPUES del cambio, nunca para uno que ya arranco.

  Esta columna guarda una FOTO de umbral_cola_revision + pesos/severidades/
  desactivados de evento_score_config, tomada al CREAR la sesion (no al
  reanudarla). El scoring de esa sesion usa esta foto en vez de la config
  viva; si es NULL (sesiones anteriores a este change, o degradacion sin
  config disponible), se cae a la config viva como antes.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: 1 columna nueva JSONB nullable, sin default que reescriba filas
  existentes, sin lectores existentes que dependan de su ausencia (el codigo
  que la lee trata NULL como "usar config viva", el comportamiento actual).

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion relevante para el resto del sistema:
  el downgrade quita la columna: las sesiones vuelven a puntuarse con la
  config viva (comportamiento previo a este change).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column(
            "config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Foto de umbral_cola_revision + scoring_weights/severidades/"
                "desactivados vigentes al CREAR la sesion (no al reanudarla). "
                "NULL = sesion anterior a este change o config no disponible "
                "al crear; el scoring cae a la config viva."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "config_snapshot")
