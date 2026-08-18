"""0070 - c-76: renombra la columna "proctor_actor" -> "tutor_actor" en
pausa_autorizada y observacion_proctor.

Revision ID: 0070
Revises: 0069
Create Date: 2026-08-14

PROPOSITO:
  El rol **proctor** fue ELIMINADO del dominio (c-76, Tarea 7; ver migracion
  0068). El actor que resuelve una pausa o escribe una observacion es ahora
  conceptualmente un **tutor** (comision-scoped) o **coordinador** (global),
  nunca un "proctor". El pedido explicito del owner del proyecto es que el
  nombre del campo no siga referenciando un concepto que ya no existe en el
  dominio ("no tiene que estar en el campo el actor proctor, si no se usa, no
  tiene sentido"). Esta migracion renombra la columna en las dos tablas que la
  tenian:

    - pausa_autorizada.proctor_actor    -> pausa_autorizada.tutor_actor
    - observacion_proctor.proctor_actor -> observacion_proctor.tutor_actor

  El VALOR de la columna no cambia (sigue siendo el ``sub`` del JWT de quien
  resolvio la pausa / escribio la observacion) — solo el NOMBRE del campo.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  La regla del proyecto (migraciones destructivas en dos pasos) aplica a
  cambios de ESQUEMA IRREVERSIBLES (DROP de columna/tabla), donde el paso 1
  deja de usar la columna y el paso 2 la borra, dejando una ventana para
  revertir sin perdida de datos. Esta migracion NO es un DROP: es un RENAME
  (``ALTER TABLE ... RENAME COLUMN``) via ``op.alter_column(new_column_name=)``.
  No se pierde ningun dato, ninguna fila, ningun valor — la columna sigue
  existiendo con el mismo contenido bajo otro nombre. El downgrade revierte el
  rename exacto (``tutor_actor`` -> ``proctor_actor``), por lo que la operacion
  es 100% reversible sin backup. Por eso se resuelve en un unico paso, igual
  que el precedente de 0068 (que tampoco es una migracion destructiva).
"""

from __future__ import annotations

from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "pausa_autorizada", "proctor_actor", new_column_name="tutor_actor"
    )
    op.alter_column(
        "observacion_proctor", "proctor_actor", new_column_name="tutor_actor"
    )


def downgrade() -> None:
    op.alter_column(
        "observacion_proctor", "tutor_actor", new_column_name="proctor_actor"
    )
    op.alter_column(
        "pausa_autorizada", "tutor_actor", new_column_name="proctor_actor"
    )
