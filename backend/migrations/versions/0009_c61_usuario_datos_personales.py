"""009 - datos personales y baja logica en tabla usuario (c-61, rama slim).

Revision ID: 0009
Revises: 0008 (branch slim)
Create Date: 2026-06-07

RAMA: slim
  down_revision = "0008"   <- solo la rama slim
  branch_labels = None     <- hereda label "slim" de 0008 -> 0005
  depends_on    = None     <- cero dependencia de la rama principal

PROPOSITO:
  Agrega tres columnas nullable a la tabla ``usuario`` (slim y full comparten el
  mismo nombre de tabla fisico ``usuario``; en Railway solo existe la rama slim):
    - nombre       VARCHAR(255) NULL  -- nombre de pila del usuario
    - apellido     VARCHAR(255) NULL  -- apellido del usuario
    - eliminado_en TIMESTAMPTZ  NULL  -- soft-delete: NULL = activo

  COLUMNAS NULLABLE: garantiza compatibilidad con usuarios pre-existentes sin
  nombre/apellido (federados / seed / admins creados antes de este change).

  GOTCHA CONOCIDO (incidente c-55/c-56): si down_revision apunta a la rama
  principal o depends_on no es None, el deploy slim de Railway rompe porque
  arrastra 0001_enable_timescaledb. Mantener SIEMPRE:
    down_revision = "0008"
    depends_on    = None

ROLLBACK:
  alembic downgrade slim@0008  -> dropea las tres columnas en orden inverso.
  Es no destructivo (solo agrega columnas nullable; no mueve datos).

VERIFICACION:
  alembic upgrade slim@head   -> aplica 0005 -> 0008 -> 0009 contra postgres:16-alpine
  alembic history             -> debe mostrar rama slim con 0009 al tope
"""

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "0009"
down_revision = "0008"   # rama slim - NO la rama principal
branch_labels = None     # hereda el label "slim" de la cadena 0005 -> 0008
depends_on = None        # SIN dependencia de migraciones de la rama principal

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    """Agrega nombre, apellido y eliminado_en (nullable) a la tabla usuario."""
    op.add_column(
        "usuario",
        sa.Column("nombre", sa.String(255), nullable=True),
    )
    op.add_column(
        "usuario",
        sa.Column("apellido", sa.String(255), nullable=True),
    )
    op.add_column(
        "usuario",
        sa.Column("eliminado_en", TIMESTAMPTZ, nullable=True),
    )


def downgrade() -> None:
    """Dropea las tres columnas en orden inverso al upgrade."""
    op.drop_column("usuario", "eliminado_en")
    op.drop_column("usuario", "apellido")
    op.drop_column("usuario", "nombre")
