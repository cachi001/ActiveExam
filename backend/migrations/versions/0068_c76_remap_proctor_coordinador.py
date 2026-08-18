"""0068 - c-76: remapea el rol "proctor" -> "coordinador" en usuario.roles.

Revision ID: 0068
Revises: 0067
Create Date: 2026-08-13

PROPOSITO:
  El rol **proctor** fue ELIMINADO del dominio (c-76, Tarea 7). El COORDINADOR
  absorbe la supervision global en vivo + el veredicto. Los usuarios que tenian
  el rol "proctor" deben conservar su acceso, ahora como "coordinador".

  El valor del rol se guarda como string dentro del array JSONB ``usuario.roles``.
  Esta migracion reemplaza el elemento ``"proctor"`` por ``"coordinador"`` en toda
  fila que lo tenga, SIN DUPLICAR: si la fila ya tiene ``"coordinador"``, el
  elemento "proctor" se ELIMINA (no se agrega un segundo "coordinador"). Idempotente.

  Sigue el precedente exacto de la migracion 0060 (rename "docente" -> "tutor").

SOBRE "DESTRUCTIVA EN DOS PASOS":
  La regla del proyecto (migraciones destructivas en dos pasos) aplica a cambios
  de ESQUEMA irreversibles (DROP de columna/tabla), donde el paso 1 deja de usar
  y el paso 2 borra. Esta migracion NO toca el esquema: no dropea ninguna columna
  ni tabla — solo REESCRIBE VALORES dentro del JSONB ``usuario.roles``. Por eso se
  resuelve en un unico UPDATE idempotente, como el rename de rol de 0060. La unica
  "perdida" es semantica (el valor "proctor" deja de existir), documentada abajo en
  ``downgrade``.

REVERSIBILIDAD (downgrade):
  El remapeo NO es reversible de forma segura y automatica. Tras el upgrade no se
  puede distinguir un coordinador que SIEMPRE fue coordinador de uno que era
  proctor y fue remapeado — ambos son "coordinador" identicos en la columna.
  Revertir coordinador -> proctor en masa degradaria a coordinadores legitimos.
  Por eso ``downgrade`` es un NO-OP DELIBERADO (documentado): si hay que revertir,
  se hace con un backup previo al upgrade o con un remapeo manual por lista de
  sujetos afectados (ver relevamiento c-76 Tarea 7.1).
"""

from __future__ import annotations

from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


# Reescribe el array JSONB roles: cada "proctor" -> "coordinador"; luego colapsa
# duplicados (jsonb_agg(DISTINCT ...)) para no dejar dos "coordinador" si la fila
# ya tenia el rol. Solo toca filas que contienen "proctor" (idempotente).
_UPGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(DISTINCT elem)
    FROM jsonb_array_elements(
        (
            SELECT jsonb_agg(
                CASE WHEN e = '"proctor"'::jsonb THEN '"coordinador"'::jsonb ELSE e END
            )
            FROM jsonb_array_elements(roles) AS e
        )
    ) AS elem
)
WHERE roles @> '["proctor"]'::jsonb;
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    # NO-OP DELIBERADO: el remapeo proctor -> coordinador es irreversible de forma
    # segura (no se puede distinguir un coordinador remapeado de uno legitimo). No
    # se degrada coordinador -> proctor en masa. Ver el docstring de arriba: para
    # revertir se usa un backup previo o un remapeo manual por lista de sujetos.
    pass
