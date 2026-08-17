"""0071 - c-76: remapea el rol "revisor" -> "coordinador" en usuario.roles.

Revision ID: 0071
Revises: 0070
Create Date: 2026-08-14

PROPOSITO:
  El rol **revisor** fue ELIMINADO del dominio (c-76, decision post-Tarea 7).
  El TUTOR ya supervisa/observa la sesion en vivo dentro de su comision
  (`supervisar_vivo`, C-76 bloques 6/8) y la decision disciplinaria terminal
  (`revisar_sesion` — aprobar/anular) queda en manos del COORDINADOR. Un rol
  REVISOR separado quedaba redundante frente al COORDINADOR, que ya cubria el
  mismo veredicto sin estar acotado a jurisdiccion. Los usuarios que tenian el
  rol "revisor" deben conservar su acceso, ahora como "coordinador".

  El valor del rol se guarda como string dentro del array JSONB ``usuario.roles``.
  Esta migracion reemplaza el elemento ``"revisor"`` por ``"coordinador"`` en toda
  fila que lo tenga, SIN DUPLICAR: si la fila ya tiene ``"coordinador"``, el
  elemento "revisor" se ELIMINA (no se agrega un segundo "coordinador"). Idempotente.

  Sigue el precedente exacto de la migracion 0068 (remapeo "proctor" -> "coordinador"),
  que a su vez sigue el precedente de la migracion 0060 (rename "docente" -> "tutor").

SOBRE "DESTRUCTIVA EN DOS PASOS":
  La regla del proyecto (migraciones destructivas en dos pasos) aplica a cambios
  de ESQUEMA irreversibles (DROP de columna/tabla), donde el paso 1 deja de usar
  y el paso 2 borra. Esta migracion NO toca el esquema: no dropea ninguna columna
  ni tabla — solo REESCRIBE VALORES dentro del JSONB ``usuario.roles``. Por eso se
  resuelve en un unico UPDATE idempotente, como el remapeo de 0068 y el rename de
  rol de 0060. La unica "perdida" es semantica (el valor "revisor" deja de existir),
  documentada abajo en ``downgrade``.

REVERSIBILIDAD (downgrade):
  El remapeo NO es reversible de forma segura y automatica. Tras el upgrade no se
  puede distinguir un coordinador que SIEMPRE fue coordinador de uno que era
  revisor y fue remapeado — ambos son "coordinador" identicos en la columna.
  Revertir coordinador -> revisor en masa degradaria a coordinadores legitimos.
  Por eso ``downgrade`` es un NO-OP DELIBERADO (documentado): si hay que revertir,
  se hace con un backup previo al upgrade o con un remapeo manual por lista de
  sujetos afectados.
"""

from __future__ import annotations

from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


# Reescribe el array JSONB roles: cada "revisor" -> "coordinador"; luego colapsa
# duplicados (jsonb_agg(DISTINCT ...)) para no dejar dos "coordinador" si la fila
# ya tenia el rol. Solo toca filas que contienen "revisor" (idempotente).
_UPGRADE = """
UPDATE usuario
SET roles = (
    SELECT jsonb_agg(DISTINCT elem)
    FROM jsonb_array_elements(
        (
            SELECT jsonb_agg(
                CASE WHEN e = '"revisor"'::jsonb THEN '"coordinador"'::jsonb ELSE e END
            )
            FROM jsonb_array_elements(roles) AS e
        )
    ) AS elem
)
WHERE roles @> '["revisor"]'::jsonb;
"""


def upgrade() -> None:
    op.execute(_UPGRADE)


def downgrade() -> None:
    # NO-OP DELIBERADO: el remapeo revisor -> coordinador es irreversible de forma
    # segura (no se puede distinguir un coordinador remapeado de uno legitimo). No
    # se degrada coordinador -> revisor en masa. Ver el docstring de arriba: para
    # revertir se usa un backup previo o un remapeo manual por lista de sujetos.
    pass
