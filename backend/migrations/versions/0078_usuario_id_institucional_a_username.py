"""0078 - usuario.id_institucional -> usuario.username (rama principal).

Revision ID: 0078
Revises: 0020
Create Date: 2026-08-16

PROPOSITO:
  Mismo rename que 0077 en la rama ``activeexam`` (ver ese docstring para el
  detalle completo), aplicado aqui a la rama principal (``main.py`` / Settings
  full) porque el modelo ORM ``UsuarioModel`` es compartido entre ambas apps —
  si solo se renombra en una rama de DB, el ORM queda desincronizado con la
  rama que no se migro.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: ``RENAME COLUMN`` y el rename de la unique constraint son
  operaciones de catalogo instantaneas, sin perdida de datos.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion.
"""

from __future__ import annotations

from alembic import op

revision = "0078"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("usuario", "id_institucional", new_column_name="username")
    op.execute(
        "ALTER TABLE usuario RENAME CONSTRAINT uq_usuario_id_institucional "
        "TO uq_usuario_username"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE usuario RENAME CONSTRAINT uq_usuario_username "
        "TO uq_usuario_id_institucional"
    )
    op.alter_column("usuario", "username", new_column_name="id_institucional")
