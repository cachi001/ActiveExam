"""0073 - c-76: renombra los valores proctor del ENUM estado_via_alternativa -> coordinador.

Revision ID: 0073
Revises: 0072
Create Date: 2026-08-15

PROPOSITO:
  El flujo de "via alternativa" (C-63) ya esta autorizado en el codigo por
  ``coordinador``/``admin`` (``consent/router.py``, roles.intersection) desde que
  el rol PROCTOR fue eliminado (c-76, migracion 0068) — pero el ENUM nativo de
  Postgres ``estado_via_alternativa`` (creado en la migracion 0010) seguia usando
  los valores historicos ``pendiente_proctor``/``habilitado_por_proctor``. Esta
  migracion alinea el ENUM persistido con quien realmente decide (COORDINADOR),
  siguiendo la misma regla de dominio que dirigio el resto de c-76: el TUTOR
  supervisa/pausa/chatea, el COORDINADOR es quien aprueba o habilita.

  Renombra tambien el ``server_default`` de la columna ``estado`` en
  ``solicitudes_via_alternativa`` (de ``'pendiente_proctor'`` a
  ``'pendiente_coordinador'``).

SOBRE "DESTRUCTIVA EN DOS PASOS":
  ``ALTER TYPE ... RENAME VALUE`` (soportado desde Postgres 10) NO borra datos:
  renombra la etiqueta del valor del enum, preservando las filas existentes que
  ya la usaban (Postgres actualiza la referencia interna del OID del enum, no el
  texto en cada fila). No es un DROP de columna/tabla — no aplica el patron de
  dos pasos de la regla de migraciones destructivas.

REVERSIBILIDAD (downgrade):
  Reversible por completo: ``ALTER TYPE ... RENAME VALUE`` en sentido inverso,
  mas el ``server_default`` original. A diferencia del remapeo de datos de 0068/
  0071 (que reescribe filas y por eso es irreversible), este cambio es solo de
  etiqueta y no pierde informacion en ningun sentido.

VERIFICACION:
  alembic upgrade activeexam@head   -> aplica hasta 0073 contra postgres:16-alpine
  psql -c "\\dT+ estado_via_alternativa"  -> debe listar 'pendiente_coordinador'
  y 'habilitado_por_coordinador' como valores del enum.
"""

from __future__ import annotations

from alembic import op

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE estado_via_alternativa RENAME VALUE "
        "'pendiente_proctor' TO 'pendiente_coordinador'"
    )
    op.execute(
        "ALTER TYPE estado_via_alternativa RENAME VALUE "
        "'habilitado_por_proctor' TO 'habilitado_por_coordinador'"
    )
    op.execute(
        "ALTER TABLE solicitudes_via_alternativa "
        "ALTER COLUMN estado SET DEFAULT 'pendiente_coordinador'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE solicitudes_via_alternativa "
        "ALTER COLUMN estado SET DEFAULT 'pendiente_proctor'"
    )
    op.execute(
        "ALTER TYPE estado_via_alternativa RENAME VALUE "
        "'habilitado_por_coordinador' TO 'habilitado_por_proctor'"
    )
    op.execute(
        "ALTER TYPE estado_via_alternativa RENAME VALUE "
        "'pendiente_coordinador' TO 'pendiente_proctor'"
    )
