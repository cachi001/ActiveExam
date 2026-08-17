"""0048 - elimina el destino GLOBAL de Moodle (courseid/cmid).

Revision ID: 0048
Revises: 0047 (branch activeexam)
Create Date: 2026-07-28

RAMA: activeexam

PROPOSITO:
  Saca `courseid` y `cmid` de `moodle_credencial`. No son configuracion
  institucional: son el curso y la actividad CONCRETOS donde se escribe una nota, y
  eso es propio de cada examen (`examen_contenido.moodle_courseid` / `moodle_cmid`,
  D12 parte B).

  POR QUE IMPORTA:
  El destino global existia como fallback de cuando el write-back no tenia destino
  por examen. Al agregarse el destino por examen, el global quedo como red de
  seguridad — y esa red era peor que el agujero: un examen sin destino propio no
  fallaba, escribia la nota en el curso global. O sea, la nota de Programacion 1
  aterrizaba en la libreta de otra materia y la fila figuraba como 'enviado'. El
  docente veia una nota que no puso y el alumno que rindio no veia la suya, sin
  ningun error en el medio.

  Ahora, sin destino propio, la nota se retiene con el motivo "sin_destino" y se
  muestra en la pantalla de resultados. Un bloqueo visible en vez de un desvio mudo.

  `base_url`, el token y `component` SI quedan: una institucion tiene un campus, una
  cuenta de servicio y un tipo de actividad habitual (que cada examen puede
  sobreescribir).

IRREVERSIBLE EN LOS HECHOS:
  El downgrade recrea las columnas vacias (0). No se restauran los valores: eran
  configuracion de un mecanismo que se elimino a proposito.
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("moodle_credencial", "courseid")
    op.drop_column("moodle_credencial", "cmid")


def downgrade() -> None:
    op.add_column(
        "moodle_credencial",
        sa.Column("courseid", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "moodle_credencial",
        sa.Column("cmid", sa.Integer(), nullable=False, server_default="0"),
    )
