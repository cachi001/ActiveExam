"""0077 - c-76-3 (rama activeexam): usuario.id_institucional -> usuario.username.

Revision ID: 0077
Revises: 0076
Create Date: 2026-08-16

PROPOSITO:
  El campo ``id_institucional`` era conceptualmente un "legajo", pero en la
  practica SIEMPRE fue tratado como username: es lo que el usuario tipea para
  loguearse (``POST /auth/login`` ya recibe ``{"username": ...}``), y para
  alumnos via LTI se genera como ``lti:{deployment_id}:{sub}`` (no es ningun
  legajo institucional real). Mantener el nombre "id_institucional" en la
  columna generaba confusion (UI pedia "Legajo" para TODO usuario, incluidos
  tutores/coordinadores/admin que no tienen legajo). Rename estructural del
  dominio: columna, MAS los DOS enforcers de unicidad redundantes que dejo la
  migracion 0008 (bug pre-existente: ``sa.Column(..., unique=True)`` genera el
  constraint autonombrado ``uq_usuario_id_institucional`` Y ademas 0008 crea a
  mano un indice explicito ``ix_usuario_id_institucional`` sobre la misma
  columna — redundante pero inofensivo hasta este rename), y la FK de
  ``solicitud_via_alternativa`` (unica tabla que referencia esta columna en
  vez de ``usuario.id``).

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: ``RENAME COLUMN`` y los dos ``RENAME`` de constraint/indice son
  operaciones de catalogo en Postgres, instantaneas, no reescriben la tabla ni
  pierden datos. La FK de ``solicitud_via_alternativa`` sigue apuntando al
  mismo atributo fisico (``attnum``) tras el rename de columna — no requiere
  recrearse.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion: el downgrade renombra de vuelta a
  ``id_institucional`` / ``ix_usuario_id_institucional`` / ``uq_usuario_id_institucional``.
"""

from __future__ import annotations

from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("usuario", "id_institucional", new_column_name="username")
    op.execute(
        "ALTER INDEX ix_usuario_id_institucional RENAME TO ix_usuario_username"
    )
    op.execute(
        "ALTER TABLE usuario RENAME CONSTRAINT uq_usuario_id_institucional "
        "TO uq_usuario_username"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE usuario RENAME CONSTRAINT uq_usuario_username "
        "TO uq_usuario_id_institucional"
    )
    op.execute(
        "ALTER INDEX ix_usuario_username RENAME TO ix_usuario_id_institucional"
    )
    op.alter_column("usuario", "username", new_column_name="id_institucional")
