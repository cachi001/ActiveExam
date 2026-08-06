"""060 - Renombra el rol "docente" -> "tutor" en usuario.roles.

Revision ID: 0060
Revises: 0059
Create Date: 2026-08-05

PROPOSITO:
  El rol académico pasó a llamarse **tutor** (antes "docente"). El valor del rol
  se guarda como string dentro del array JSONB ``usuario.roles``. Esta migración
  reemplaza el elemento ``"docente"`` por ``"tutor"`` en todas las filas que lo
  tengan, para que los usuarios académicos existentes conserven su acceso tras el
  rename del enum (``Rol.TUTOR = "tutor"``).

  Idempotente y reversible. NO toca la columna ``comision.docente_id`` (identificador
  interno del tutor a cargo), solo el valor del rol en ``usuario.roles``.
"""

from __future__ import annotations

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


# Reemplaza un elemento string dentro del array JSONB roles.
_UPGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(
        CASE WHEN elem = '"docente"'::jsonb THEN '"tutor"'::jsonb ELSE elem END
    )
    FROM jsonb_array_elements(roles) AS elem
)
WHERE roles @> '["docente"]'::jsonb;
"""

_DOWNGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(
        CASE WHEN elem = '"tutor"'::jsonb THEN '"docente"'::jsonb ELSE elem END
    )
    FROM jsonb_array_elements(roles) AS elem
)
WHERE roles @> '["tutor"]'::jsonb;
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    op.execute(_DOWNGRADE)
