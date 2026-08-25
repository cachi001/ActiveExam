"""0093 - c-78 (deuda c-79): dropea comision.docente_id, ya sin lectores.

Revision ID: 0093
Revises: 0092
Create Date: 2026-08-25

PROPOSITO:
  Segundo paso de la migracion destructiva que empezo 0086. Esa migracion creo
  `comision_tutor` (N:M), backfilleo cada `docente_id` NOT NULL a la tabla puente
  y dejo la columna en su lugar para no romper lectores. El segundo paso nunca se
  corrio, y la columna quedo en un estado peor que muerta: VIVA PERO CONGELADA.

  Desde 0086 ningun endpoint la escribe (el alta de comision no tiene el campo y
  asignar tutores escribe solo en `comision_tutor`), pero DOS lectores criticos la
  seguian consultando:

    - `writeback_service._credencial_para` — resolvia con la credencial de QUIEN se
      firma la nota que va al campus. Ese camino no tiene respaldo institucional a
      proposito (C-73 §10.4), asi que con la columna en NULL devolvia
      `sin_docente` y la nota NUNCA salia.
    - `resultados_query` — marcaba las sesiones `sin_credencial` en la pantalla de
      Notas; con la columna en NULL marcaba TODAS.

  O sea: toda comision creada o gestionada desde la UI actual tenia el write-back
  de notas roto en silencio. Los dos lectores se migraron a `comision_tutor` antes
  de esta migracion (tests en `test_c78_writeback_credencial_nm.py`), asi que la
  columna ya no tiene lectores y se puede dropear.

CRITERIO PARA ELEGIR LA CREDENCIAL CON N TUTORES:
  El modelo de pertenencia es SIMETRICO — cualquier tutor de la comision esta igual
  de habilitado, mismo criterio que el sistema de referencia (su `comision_tutor`
  tampoco tiene tutor "principal"). Se firma con la del primer tutor que quedo a
  cargo y tenga credencial usable, con desempate por `tutor_id`. Deterministico a
  proposito: dos sincronizaciones de la misma nota tienen que salir firmadas por la
  misma persona, si no la columna *Fuente* de la libreta cambiaria sola.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  Esto ES el paso dos. El paso uno (crear la tabla puente + backfill + convivencia)
  fue 0086. No se pierde informacion: todo `docente_id` que existia ya vive en
  `comision_tutor` desde entonces.

REVERSIBILIDAD (downgrade):
  Recrea la columna y su indice, y RECONSTRUYE el contenido desde `comision_tutor`
  tomando el primer tutor de cada comision (mismo criterio de desempate que usa el
  write-back). No es una identidad perfecta —una comision con tres tutores vuelve
  con uno solo, porque la columna no puede representar mas— pero deja al codigo
  viejo funcionando en vez de con todo en NULL, que es como estaba antes de este
  arreglo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_comision_docente_id", table_name="comision")
    op.drop_column("comision", "docente_id")


def downgrade() -> None:
    op.add_column(
        "comision",
        sa.Column(
            "docente_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="SET NULL"),
            nullable=True,
            comment="C-73 §9: docente a cargo. Reemplazada por comision_tutor (c-79).",
        ),
    )
    op.create_index("ix_comision_docente_id", "comision", ["docente_id"])
    # Reconstruccion best-effort: el primer tutor de cada comision, con el mismo
    # desempate que usa el write-back.
    op.execute(
        sa.text(
            """
            UPDATE comision c
               SET docente_id = t.tutor_id
              FROM (
                    SELECT DISTINCT ON (comision_id) comision_id, tutor_id
                      FROM comision_tutor
                     ORDER BY comision_id, created_at, tutor_id
                   ) t
             WHERE t.comision_id = c.id
            """
        )
    )
