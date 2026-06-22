"""0022 - detectores_activos por defecto = TODOS los detectores (slim).

Revises: 0021 (rama slim)
Create Date: 2026-06-22

RAMA: slim (alineado con el stack de Railway y dev). Para la rama full, agregar una
migracion analoga aguas abajo cuando corresponda.

PROPOSITO:
  El default de ``configuracion_sistema.detectores_activos`` era ``'[]'`` (vacio),
  lo que dejaba TODOS los detectores inactivos al crear el singleton. El comportamiento
  esperado es que arranquen TODOS activos (el admin desactiva los que no quiera).

  1. Cambia el server_default de la columna a la lista completa de detectores.
  2. Backfill ADITIVO: las filas existentes con la lista vacia se actualizan a la
     lista completa (no pisa configuraciones que ya tengan detectores elegidos).

ROLLBACK:
  Revierte el server_default a ``'[]'``. NO toca los datos backfilleados (no es
  destructivo): si se quiere limpiar, hacerlo como paso 2 separado y explicito.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_ALL_DETECTORES = (
    '["rostro_ausente", "multiples_rostros", "mirada_desviada_sostenida", '
    '"perdida_de_foco", "cambio_pestana", "monitor_adicional", '
    '"salida_pantalla_completa", "copiar_pegar", "corte_conectividad_prolongado"]'
)


def upgrade() -> None:
    # 1) Nuevo default para filas futuras.
    op.alter_column(
        "configuracion_sistema",
        "detectores_activos",
        server_default=sa.text(f"'{_ALL_DETECTORES}'::jsonb"),
    )
    # 2) Backfill: filas con el default viejo (lista vacia, o la lista de 8 que
    #    sembro 0014 sin 'corte_conectividad_prolongado') -> lista completa de 9.
    #    Detectamos "default viejo" por la AUSENCIA de corte_conectividad_prolongado,
    #    asi cubrimos tanto '[]' como la lista de 8. No toca configuraciones que ya
    #    incluyan el evento critico (no pisa customizaciones del admin).
    op.execute(
        sa.text(
            "UPDATE configuracion_sistema "
            f"SET detectores_activos = '{_ALL_DETECTORES}'::jsonb "
            "WHERE NOT (detectores_activos @> '[\"corte_conectividad_prolongado\"]'::jsonb)"
        )
    )


def downgrade() -> None:
    # Revierte solo el default (no toca datos — no destructivo).
    op.alter_column(
        "configuracion_sistema",
        "detectores_activos",
        server_default=sa.text("'[]'::jsonb"),
    )
