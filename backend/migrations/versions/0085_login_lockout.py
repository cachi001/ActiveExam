"""0085 - lockout de login por intentos fallidos.

Revision ID: 0085
Revises: 0084
Create Date: 2026-08-21

PROPOSITO:
  Pentest activo (2026-08-21) confirmó que POST /auth/login no tenía ningún
  límite de intentos fallidos: 25 intentos seguidos con password incorrecta
  contra 'admin' devolvieron 401 sin bloqueo, sin captcha, sin demora
  creciente. Se agrega el mismo patrón de lockout ya usado en otro proyecto
  del dueño (Sistema-de-Reserva-Salon): contador de intentos fallidos +
  timestamp de bloqueo, ambos persistidos en la fila del usuario.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: columnas nuevas ADITIVAS con default, ningún lector/escritor
  existente se ve afectado (todas las filas existentes quedan con
  intentos_fallidos=0, bloqueado_hasta=NULL, exactamente el estado "nunca
  bloqueado").

REVERSIBILIDAD (downgrade):
  Reversible sin pérdida de información relevante: son contadores efímeros
  de seguridad, no datos de negocio. El downgrade dropea ambas columnas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "intentos_fallidos",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "usuario",
        sa.Column(
            "bloqueado_hasta",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "bloqueado_hasta")
    op.drop_column("usuario", "intentos_fallidos")
