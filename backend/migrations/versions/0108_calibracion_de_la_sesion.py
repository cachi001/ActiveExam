"""Calibracion de mirada de la sesion: con que cero se evaluo la mirada.

PROBLEMA
--------
La calibracion de mirada corre en el CLIENTE (paso previo del ingreso, o el
respaldo que corre el propio examen si el paso previo no dejo nada) pero el
resultado nunca viajaba al backend: solo vivia en memoria del navegador.
Revisar una sesion despues no permitia saber si el alumno calibro, con que
cero se evaluo su mirada, ni si la calibracion midio las 4 esquinas de la
pantalla o fue solo el punto de respaldo.

QUE HACE ESTA MIGRACION
------------------------
Aditiva. Agrega ``calibracion`` (JSONB, nullable) a ``proctoring_session``: un
objeto descriptivo ``{ centro: {x,y}, rango_x: [min,max]|null,
rango_y: [min,max]|null, origen: 'paso_previo'|'respaldo',
muestras_por_punto: int }``.

NUNCA participa del score ni de ninguna decision automatica (reglas duras
#5/#6): es documentacion de con que cero se evaluo la mirada de esta sesion,
no evidencia ni criterio de sancion.

Sin backfill: las sesiones existentes quedan con ``calibracion = NULL`` (se
calibraron, si acaso, sin que quedara registro server-side).

ROLLBACK
--------
Dropea la columna. Aditivo: no toca ninguna otra tabla ni dato.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column("calibracion", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proctoring_session", "calibracion")
