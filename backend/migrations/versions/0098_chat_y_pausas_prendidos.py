"""El chat y las pausas vienen PRENDIDOS por defecto.

Revision ID: 0098
Revises: 0097
Create Date: 2026-08-25

REVIERTE la 0095, a pedido del dueño.

La 0095 apagó el chat por CAPACIDAD: medido el 25/8/2026, su poller son ~29 req/s
con 100 alumnos sobre un techo de 80, y a esa altura no se pone lento el chat
sino TODO, incluido el autoguardado de las respuestas.

El dueño decidió prenderlo igual: el sistema tiene que venir con la
funcionalidad completa para poder probarla, y la prueba de carga contra el
entorno real es lo que va a decir si el techo aguanta. Medirlo es mejor que
asumirlo — que es exactamente lo que motivó la 0095.

Lo que hace que esto sea sostenible es que en el medio se corrigieron las dos
cosas que hacían caro tener el chat prendido:
  - `PausaAlumno` pasó a cadencia adaptativa (20 s en reposo, 3,5 s solo cuando
    hay algo esperando): ~29 -> ~5 req/s.
  - El interruptor dejó de ser cosmético: hasta c-78 apagarlo no apagaba nada
    porque ningún endpoint consultaba la config, así que el "ahorro" de tenerlo
    apagado no existía.

Si la carga muestra que no da, se apaga desde la pantalla de Configuración — es
un toggle de runtime, no hace falta otra migración. El valor por sesión queda
congelado en `proctoring_session.config_snapshot`, así que apagarlo no altera
una rendición ya empezada.

Toca el `server_default` (para instalaciones nuevas) y ADEMÁS actualiza las filas
existentes, por el mismo motivo que la 0095 hizo lo propio: la fila del singleton
ya existe desde la migración 0014, así que cambiar solo el default no la movería.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "configuracion_sistema",
        "chat_habilitado",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    # Las pausas ya venían en true; se deja explícito para que el estado quede
    # parejo aunque alguien las hubiera apagado a mano.
    op.execute(
        "UPDATE configuracion_sistema SET chat_habilitado = true, "
        "pausas_habilitadas = true"
    )


def downgrade() -> None:
    op.alter_column(
        "configuracion_sistema",
        "chat_habilitado",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.execute("UPDATE configuracion_sistema SET chat_habilitado = false")
