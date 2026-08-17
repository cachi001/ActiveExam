"""0049 - docente a cargo de la comision.

Revision ID: 0049
Revises: 0048 (branch activeexam)
Create Date: 2026-07-29

RAMA: activeexam

PROPOSITO:
  Agrega `comision.docente_id` (FK -> usuario): el docente a cargo de esa comision.

  POR QUE IMPORTA:
  Hasta ahora la cadena docente -> comision -> examen -> nota estaba CORTADA en el
  primer eslabon. `comision` no tenia docente, `inscripcion` no tiene rol (es
  matriculacion de alumnos) y `examen_contenido` no tiene dueno. Eso dejaba dos
  agujeros:

  1. ATRIBUCION: toda nota escrita en Moodle figuraba como puesta por la cuenta de
     servicio institucional. En la libreta no habia forma de saber que docente la
     devolvio. Una nota sin responsable identificable, en un sistema donde la
     decision siempre es humana, es un problema de rendicion de cuentas.

  2. AUTORIZACION: el rol DOCENTE dice que administra "lo suyo" (ver `roles.py`),
     pero el sistema no tenia contra que validar esa pertenencia. Los guards son por
     CAPACIDAD (`gestionar_academico`), no por propiedad, asi que cualquier docente
     podia fijar el destino Moodle del examen de OTRA comision — y mandar esa nota a
     la libreta que quisiera.

  Con este vinculo, el docente se DERIVA (examen.comision_id -> comision.docente_id)
  y las dos cosas se cierran con el mismo dato.

NULLABLE A PROPOSITO:
  Las comisiones existentes no tienen docente y no se puede adivinar cual es. Queda
  nullable y se asigna desde la UI de Materias y comisiones. Una comision sin docente
  no rompe nada: el write-back de sus examenes cae a la cuenta de servicio
  institucional (degradacion, no bloqueo).

ondelete="SET NULL":
  Dar de baja a un usuario NO debe borrar la comision ni sus examenes. La comision
  queda sin docente a cargo hasta que se reasigne.
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "comision",
        sa.Column("docente_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_comision_docente",
        "comision",
        "usuario",
        ["docente_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Se consulta "las comisiones de este docente" en cada pantalla del docente y en
    # cada validacion de pertenencia: sin indice es un scan de toda la tabla.
    op.create_index("ix_comision_docente_id", "comision", ["docente_id"])


def downgrade() -> None:
    op.drop_index("ix_comision_docente_id", table_name="comision")
    op.drop_constraint("fk_comision_docente", "comision", type_="foreignkey")
    op.drop_column("comision", "docente_id")
