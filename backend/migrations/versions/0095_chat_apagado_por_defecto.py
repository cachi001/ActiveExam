"""0095 - c-78 E-14: el chat del alumno viene APAGADO por defecto.

Revision ID: 0095
Revises: 0094
Create Date: 2026-08-25

PROPOSITO (decision del dueno, respaldada por medicion):
  `ChatBox` (frontend/src/ui/ChatBox.tsx) pollea cada 3.5 s y se monta en la
  pantalla de rendicion de CADA alumno. Con 100 alumnos rindiendo son ~28,6
  peticiones por segundo SOLO de chat — contra las ~0,83/s que generan las
  capturas. Es, por lejos, la fuente de trafico dominante durante un examen.

  Medido el 25/8/2026 contra la instancia real de Render (plan free): el techo de
  transporte esta en ~80 req/s, y a 100 conexiones concurrentes la latencia p50
  se triplica (280 ms -> 875 ms) aunque no aparezcan errores. 28,6 req/s es el
  36% de ese techo, gastado en una funcion que la mayoria de los examenes no usa.

  El chat sigue existiendo y se prende desde Configuracion cuando se lo necesita.
  Lo que cambia es de que lado esta el default.

POR QUE TAMBIEN SE APAGA LA FILA EXISTENTE:
  `configuracion_sistema` es un singleton: hay una sola fila, con id 'global',
  creada hace tiempo con el valor `true`. Cambiar solo el `server_default` no
  tendria NINGUN efecto sobre el sistema en marcha — el default solo aplica a
  filas nuevas, y no se va a crear ninguna. Por eso el UPDATE explicito.

  Es reversible desde la UI: Configuracion -> Proctoring -> "Chat habilitado".

REVERSIBILIDAD (downgrade):
  Vuelve el default a `true` y reactiva la fila 'global'. Simetrico.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "configuracion_sistema",
        "chat_habilitado",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    # Sin esto el cambio no se nota: la unica fila que existe ya tiene `true`.
    op.execute(
        sa.text(
            "UPDATE configuracion_sistema SET chat_habilitado = false "
            "WHERE id = 'global'"
        )
    )


def downgrade() -> None:
    op.alter_column(
        "configuracion_sistema",
        "chat_habilitado",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            "UPDATE configuracion_sistema SET chat_habilitado = true "
            "WHERE id = 'global'"
        )
    )
