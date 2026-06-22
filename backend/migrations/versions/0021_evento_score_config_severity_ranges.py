"""021 - CHECK constraint para rangos de peso por severidad en evento_score_config.

Revision ID: 0021
Revises: 0019 (rama slim)
Create Date: 2026-06-19

RAMA: slim (alineado con el stack de Railway y dev). Si se quiere el equivalente en
la rama full, agregar una migracion analoga aguas abajo de 0020 (no convergir aca
para evitar arrastrar la cadena full sobre el stack slim de dev/Railway).
  down_revision = "0019"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Defense-in-depth para los rangos institucionales de peso por severidad
  (SEVERITY_RANGES en app/domain/scoring/risk_score.py). La validacion ya existe
  a nivel aplicacion (PATCH /scoring/config/{tipo}), pero un INSERT manual,
  una migracion futura, o cualquier acceso fuera del endpoint puede violar el
  invariante. El CHECK constraint a nivel DB lo enforza siempre.

  Rangos: baja [1-10], media [11-30], alta [31-60], critica [61-100]. La
  severidad ``baseline`` NO es configurable por evento (es el piso 0 del score)
  y queda EXCLUIDA del catalogo permitido.

VERIFICACION:
  alembic upgrade head -> aplica el CHECK constraint.
  - INSERT/UPDATE con (severidad='baja', peso=100) debe fallar con 23514 (CHECK).
  - INSERT/UPDATE con (severidad='critica', peso=80) debe pasar.

ROLLBACK:
  alembic downgrade head-1 -> drop del constraint.
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0019"
branch_labels = None
depends_on = None


_CONSTRAINT_NAME = "ck_evento_score_config_peso_en_rango_severidad"

_CHECK_SQL = """
    (severidad = 'baja'    AND peso BETWEEN 1  AND 10)  OR
    (severidad = 'media'   AND peso BETWEEN 11 AND 30)  OR
    (severidad = 'alta'    AND peso BETWEEN 31 AND 60)  OR
    (severidad = 'critica' AND peso BETWEEN 61 AND 100)
"""


def upgrade() -> None:
    # Guardrail: si alguna fila viola los rangos, abortar antes de crear el
    # constraint (mejor fallar fuerte aca que dejar la migracion a medio aplicar).
    op.execute(
        f"""
        DO $$
        DECLARE
            violaciones int;
        BEGIN
            SELECT count(*) INTO violaciones
            FROM evento_score_config
            WHERE NOT ({_CHECK_SQL});
            IF violaciones > 0 THEN
                RAISE EXCEPTION
                    'No se puede aplicar el CHECK: hay % filas en evento_score_config '
                    'con peso fuera del rango de su severidad. Corregilas antes.',
                    violaciones;
            END IF;
        END $$;
        """
    )
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "evento_score_config",
        _CHECK_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "evento_score_config", type_="check")
