"""0087 - c-78 D1 (rama activeexam): examen_contenido.eliminado_en (baja logica).

Revision ID: 0087
Revises: 0086
Create Date: 2026-08-24

PROPOSITO:
  Hasta aca `examen_contenido` no tenia NINGUNA forma de baja. Materia y comision
  tienen `activa BOOLEAN` (freeze de dictado, reversible y esperado) y un DELETE
  duro condicionado a estar 100% vacias; ese camino es inservible para un examen:
  un examen con sesiones rendidas nunca esta vacio, y esas sesiones son evidencia
  que no se puede tocar (reglas duras #6/#7). Sacar un examen del catalogo
  terminaba siendo un UPDATE a mano contra produccion.

  Se agrega `eliminado_en TIMESTAMPTZ NULL`, la MISMA convencion que ya usan
  usuario, proctoring_session, embedding y foto de referencia: NULL = activo,
  NOT NULL = baja logica, y ademas registra CUANDO (cosa que un boolean no hace).

  D2: la baja es administrativa y NO propaga a la evidencia. El examen dado de
  baja sale de los listados y del conteo de INVENTARIO (`total_examenes`), pero
  sus sesiones, eventos, capturas y notas siguen existiendo y consultables por id.
  `total_sesiones` de Estadisticas NO cae: esa actividad ocurrio y es un hecho.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: columna aditiva y NULLABLE, sin backfill. Las filas existentes
  quedan con NULL, o sea activas, que es exactamente el comportamiento previo.
  Ningun lector existente se rompe por una columna adicional.

REVERSIBILIDAD (downgrade):
  El downgrade dropea SOLO esta columna y no toca ninguna otra tabla. Si al
  momento del rollback ya habia examenes dados de baja, se pierde la MARCA de
  baja y esos examenes REAPARECEN en los listados. No se pierde ningun dato de
  dominio: ni el examen, ni sus preguntas, ni sus sesiones o evidencia.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "eliminado_en",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL = activo, NOT NULL = baja logica.",
        ),
    )


def downgrade() -> None:
    # Ver REVERSIBILIDAD arriba: se pierde la marca de baja, no el examen.
    op.drop_column("examen_contenido", "eliminado_en")
