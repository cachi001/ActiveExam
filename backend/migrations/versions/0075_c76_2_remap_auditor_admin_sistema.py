"""0075 - c-76-2: remapea el rol "auditor" -> "admin_sistema" en usuario.roles.

Revision ID: 0075
Revises: 0074
Create Date: 2026-08-16

PROPOSITO:
  El rol **auditor** fue ELIMINADO del dominio (c-76-2). La capacidad
  ``ver_auditoria`` (solo lectura del registro de auditoria) queda exclusiva de
  ADMIN_SISTEMA — el endpoint real (``audit_router.py``) ya usaba
  ``require_roles(ADMIN_SISTEMA)`` hardcodeado, nunca conectado a la capacidad
  config-driven, asi que esta eliminacion no le saca acceso real a nadie. Los
  usuarios que tenian el rol "auditor" deben conservar su acceso nominal, ahora
  como "admin_sistema".

  El valor del rol se guarda como string dentro del array JSONB ``usuario.roles``.
  Esta migracion reemplaza el elemento ``"auditor"`` por ``"admin_sistema"`` en
  toda fila que lo tenga, SIN DUPLICAR: si la fila ya tiene ``"admin_sistema"``,
  el elemento "auditor" se ELIMINA (no se agrega un segundo "admin_sistema").
  Idempotente. Sigue el precedente exacto de 0068/0071/0074.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: esta migracion no toca el esquema (no dropea columna/tabla), solo
  reescribe valores dentro del JSONB ``usuario.roles`` en un unico UPDATE
  idempotente, igual que 0068/0071/0074.

REVERSIBILIDAD (downgrade):
  NO reversible de forma segura y automatica: tras el upgrade no se puede
  distinguir un admin_sistema que SIEMPRE lo fue de uno que era auditor y fue
  remapeado. ``downgrade`` es un NO-OP DELIBERADO, mismo criterio que
  0068/0071/0074: para revertir se usa un backup previo al upgrade o un
  remapeo manual por lista de sujetos afectados.
"""

from __future__ import annotations

from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


# Reescribe el array JSONB roles: cada "auditor" -> "admin_sistema"; luego colapsa
# duplicados (jsonb_agg(DISTINCT ...)) para no dejar dos "admin_sistema" si la
# fila ya tenia el rol. Solo toca filas que contienen "auditor".
_UPGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(DISTINCT elem)
    FROM jsonb_array_elements(
        (
            SELECT jsonb_agg(
                CASE WHEN e = '"auditor"'::jsonb THEN '"admin_sistema"'::jsonb ELSE e END
            )
            FROM jsonb_array_elements(roles) AS e
        )
    ) AS elem
)
WHERE roles @> '["auditor"]'::jsonb;
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    # NO-OP DELIBERADO: el remapeo auditor -> admin_sistema es irreversible de
    # forma segura (no se puede distinguir un admin_sistema remapeado de uno
    # legitimo). No se degrada admin_sistema -> auditor en masa. Ver el
    # docstring de arriba: para revertir se usa un backup previo o un remapeo
    # manual por lista de sujetos.
    pass
