"""0080 - usuario.email pasa a ser UNIQUE (rama principal).

Revision ID: 0080
Revises: 0078
Create Date: 2026-08-16

PROPOSITO:
  Mismo fix que 0079 en la rama ``activeexam`` (ver ese docstring para el
  detalle completo de la vulnerabilidad), aplicado aqui a la rama principal
  (``main.py`` / Settings full) porque el modelo ORM ``UsuarioModel`` y el
  router de auth son compartidos entre ambas apps.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion.
"""

from __future__ import annotations

from alembic import op

revision = "0080"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_usuario_email", "usuario", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_usuario_email", "usuario", type_="unique")
