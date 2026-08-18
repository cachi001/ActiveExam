"""0072 - c-76: renombra la tabla "observacion_proctor" -> "observacion_tutor".

Revision ID: 0072
Revises: 0071
Create Date: 2026-08-14

PROPOSITO:
  El rol PROCTOR fue eliminado del dominio (c-76, bloque 7). La palabra
  "proctor" no debe seguir apareciendo como nombre de ACTOR en el esquema —
  quien escribe estas observaciones ahora es el TUTOR (o el COORDINADOR, de
  alcance global). Esta migracion renombra la TABLA; la columna que registra
  quien escribio la observacion ya se renombro por separado en la migracion
  0070 (``proctor_actor`` -> ``tutor_actor``).

SOBRE "DESTRUCTIVA EN DOS PASOS":
  La regla del proyecto (migraciones destructivas en dos pasos) aplica a
  cambios de ESQUEMA irreversibles (DROP de columna/tabla). Esta migracion NO
  dropea nada: ``ALTER TABLE ... RENAME TO`` conserva filas, columnas, indices,
  constraints y el nombre logico de la FK hacia proctoring_session — es
  puramente un cambio de nombre, reversible en un solo paso (ver downgrade).

REVERSIBILIDAD (downgrade):
  Total: ``op.rename_table`` de vuelta a "observacion_proctor" restaura el
  estado previo exacto (a diferencia del remapeo de VALORES de 0068/0071, que
  es irreversible porque pierde informacion sobre el valor original).
"""

from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("observacion_proctor", "observacion_tutor")


def downgrade() -> None:
    op.rename_table("observacion_tutor", "observacion_proctor")
