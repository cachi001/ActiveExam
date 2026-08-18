"""0074 - c-76-2: remapea el rol "admin_examenes" -> "admin_sistema" en usuario.roles.

Revision ID: 0074
Revises: 0073
Create Date: 2026-08-16

PROPOSITO:
  El rol **admin_examenes** fue ELIMINADO del dominio (c-76-2). El dueno del
  producto decidio que solo debe existir un rol "Admin" (ADMIN_SISTEMA): la
  gestion academica que tenia admin_examenes (examenes/materias/comisiones sin
  poder de supervision) pasa a ser exclusiva de ADMIN_SISTEMA. Los usuarios que
  tenian el rol "admin_examenes" deben conservar su acceso, ahora como
  "admin_sistema".

  El valor del rol se guarda como string dentro del array JSONB ``usuario.roles``.
  Esta migracion reemplaza el elemento ``"admin_examenes"`` por ``"admin_sistema"``
  en toda fila que lo tenga, SIN DUPLICAR: si la fila ya tiene ``"admin_sistema"``,
  el elemento "admin_examenes" se ELIMINA (no se agrega un segundo
  "admin_sistema"). Idempotente. Sigue el precedente exacto de 0068/0071.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: esta migracion no toca el esquema (no dropea columna/tabla), solo
  reescribe valores dentro del JSONB ``usuario.roles`` en un unico UPDATE
  idempotente, igual que 0068/0071.

REVERSIBILIDAD (downgrade):
  NO reversible de forma segura y automatica: tras el upgrade no se puede
  distinguir un admin_sistema que SIEMPRE lo fue de uno que era admin_examenes
  y fue remapeado. ``downgrade`` es un NO-OP DELIBERADO, mismo criterio que
  0068/0071: para revertir se usa un backup previo al upgrade o un remapeo
  manual por lista de sujetos afectados.
"""

from __future__ import annotations

from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


# Reescribe el array JSONB roles: cada "admin_examenes" -> "admin_sistema"; luego
# colapsa duplicados (jsonb_agg(DISTINCT ...)) para no dejar dos "admin_sistema"
# si la fila ya tenia el rol. Solo toca filas que contienen "admin_examenes".
_UPGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(DISTINCT elem)
    FROM jsonb_array_elements(
        (
            SELECT jsonb_agg(
                CASE WHEN e = '"admin_examenes"'::jsonb THEN '"admin_sistema"'::jsonb ELSE e END
            )
            FROM jsonb_array_elements(roles) AS e
        )
    ) AS elem
)
WHERE roles @> '["admin_examenes"]'::jsonb;
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    # NO-OP DELIBERADO: el remapeo admin_examenes -> admin_sistema es irreversible
    # de forma segura (no se puede distinguir un admin_sistema remapeado de uno
    # legitimo). No se degrada admin_sistema -> admin_examenes en masa. Ver el
    # docstring de arriba: para revertir se usa un backup previo o un remapeo
    # manual por lista de sujetos.
    pass
