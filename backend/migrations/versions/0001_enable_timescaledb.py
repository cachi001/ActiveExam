"""001 - habilita la extension TimescaleDB sobre esquema vacio.

Revision ID: 0001
Revises:
Create Date: 2026-05-30

Scope (C-04, db-migrations-baseline):
- ``upgrade``: habilita la extension TimescaleDB. NO crea tablas de dominio:
  esas (la hypertable de eventos, audit log, etc.) son scope de C-05.
- ``downgrade``: remueve la extension. Es reversible SIN PERDIDA porque el
  esquema no contiene tablas de dominio (esquema vacio).

Deja la extension lista para que C-05 cree la hypertable sobre ella.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Habilita TimescaleDB. IF NOT EXISTS hace la migracion idempotente.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")


def downgrade() -> None:
    # Reversible sobre base limpia: el esquema esta vacio (sin tablas de dominio),
    # asi que dropear la extension no pierde datos de negocio.
    op.execute("DROP EXTENSION IF EXISTS timescaledb")
