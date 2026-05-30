"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

CONVENCION DE MIGRACIONES DESTRUCTIVAS EN DOS PASOS (expand/contract):
Todo cambio que elimine o renombre una columna/tabla se parte en DOS migraciones:
  1. EXPAND: agrega lo nuevo y mantiene compatibilidad con lo viejo (deploy seguro).
  2. CONTRACT: elimina lo viejo una vez que ningun codigo en produccion lo usa.
Nunca eliminar y agregar en la misma migracion: evita downtime y perdida de datos.
"""

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
