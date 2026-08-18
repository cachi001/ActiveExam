"""0076 - usuario.auth_provider: default 'keycloak' -> 'jwt'.

Revision ID: 0076
Revises: 0075
Create Date: 2026-08-16

PROPOSITO:
  Keycloak fue ELIMINADO del dominio (backend wiring + frontend adapter).
  El unico auth_provider real hoy es 'jwt' (Literal["jwt"] en app.config.Settings
  y app.config_activeexam.ActiveExamSettings). La columna ``usuario.auth_provider``
  seguia con ``server_default='keycloak'`` — un default muerto que nunca se lee
  como fallback en la practica (todo el codigo real, seed_users.py y el flujo de
  registro/LTI, setea auth_provider explicitamente), pero queda como trampa
  latente para cualquier INSERT futuro que lo omita.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: esta migracion NO toca filas existentes ni el esquema de la
  columna (tipo/nullable), solo cambia el DEFAULT que aplica a futuros inserts
  sin valor explicito.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion: el downgrade restaura el default
  'keycloak' anterior. No revisa ni modifica filas existentes en ningun sentido.
"""

from __future__ import annotations

from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE usuario ALTER COLUMN auth_provider SET DEFAULT 'jwt'")


def downgrade() -> None:
    op.execute("ALTER TABLE usuario ALTER COLUMN auth_provider SET DEFAULT 'keycloak'")
