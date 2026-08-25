"""0091 - c-78 E-06 (task 14.1): lote de replicas de un examen multi-comision.

Revision ID: 0091
Revises: 0090
Create Date: 2026-08-24

PROPOSITO:
  Crear un examen para varias comisiones se resuelve REPLICANDO (D12): N examenes
  independientes, uno por comision, con el mismo set de preguntas. Cada replica es
  una fila propia de `examen_contenido` y el modelo de datos no cambia.

  Lo unico que el sistema no puede reconstruir despues es CUALES nacieron juntas.
  `lote_replica_id` es esa marca: las N replicas de una misma operacion comparten
  el valor; un examen creado suelto lo tiene en NULL.

  Con eso el detalle del examen puede decir "replica 1 de 3" con link a las
  hermanas, y mas adelante se puede aplicar una configuracion o un destino de
  Moodle al lote entero sin volver a tocar la base.

POR QUE NO UNA TABLA APARTE:
  Un lote no tiene atributos propios — es solo identidad compartida. Una tabla
  `lote_replica` con una sola columna id agregaria un join a cada lectura del
  catalogo para no guardar ningun dato. Si algun dia el lote necesita atributos
  (quien lo creo, cuando, el titulo base), la tabla se agrega y esta columna pasa
  a ser su FK sin mover ninguna fila.

POR QUE NO ES UNA FK A `examen_contenido`:
  Apuntar a "el examen original" haria que borrar ese examen rompa o huerfane a
  las hermanas, y ninguna replica es mas original que las otras: nacen todas en
  la misma transaccion. El lote es un id sin dueno, a proposito.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: una columna nueva NULLABLE, sin backfill. Los examenes ya creados
  quedan en NULL, que es exactamente lo que son — examenes sueltos. Ningun lector
  existente se rompe.

REVERSIBILIDAD (downgrade):
  Dropea solo la columna. Se pierde la marca de que un grupo de examenes nacio
  junto; los examenes en si quedan intactos y siguen funcionando, cada uno con su
  comision. No se pierde dato de dominio.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "lote_replica_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            nullable=True,
            comment=(
                "c-78 E-06: id compartido por las replicas creadas en una misma "
                "operacion multi-comision. NULL = examen suelto."
            ),
        ),
    )
    # Se consulta siempre por lote completo ("las hermanas de este examen"), nunca
    # por rango: indice comun, y parcial porque la enorme mayoria de las filas
    # tiene NULL y no aporta nada indexarlas.
    op.create_index(
        "ix_examen_contenido_lote_replica",
        "examen_contenido",
        ["lote_replica_id"],
        postgresql_where=sa.text("lote_replica_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_examen_contenido_lote_replica", table_name="examen_contenido")
    op.drop_column("examen_contenido", "lote_replica_id")
