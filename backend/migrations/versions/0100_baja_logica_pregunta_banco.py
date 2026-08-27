"""0100 - baja logica de las preguntas del banco.

Revision ID: 0100
Revises: 0099
Create Date: 2026-08-27

PROPOSITO:
  No habia NINGUNA forma de sacar una pregunta del banco desde la aplicacion: no
  existia el endpoint ni el boton. La unica salida era entrar a la base a mano.
  Eso se volvio un problema concreto cuando se detecto que el reimport por XML
  duplicaba preguntas al editarlas (arreglado en 0099): el banco se ensuciaba y
  no habia manera de limpiarlo.

POR QUE LOGICA Y NO BORRADO FISICO:
  Mismo criterio que materia, comision, examen y usuario. Un examen ya rendido
  tiene que poder reconstruirse exactamente como fue (regla dura #6, cadena de
  custodia), y `pregunta_examen` referencia `pregunta_banco`. Borrar la fila
  romperia esa reconstruccion o forzaria un ON DELETE que perderia trazabilidad.
  NULL = vigente; con timestamp = dada de baja y recuperable.

QUE HACE LA BAJA (en el codigo, no en el esquema):
  - La pregunta sale del listado del banco (filtro `estado`, default 'activa').
  - No entra a examenes nuevos (crear-desde-banco la excluye).
  - No se incorpora al ampliar el pool de un examen existente.
  - No se cuenta como disponible en el desglose del sorteo.
  - Se revierte con POST /preguntas/{id}/reactivar.

GUARDA (409 'pregunta_en_uso'):
  No se puede dar de baja una pregunta que esta en el pool de un examen ACTIVO.
  El pool es una copia, asi que el examen no se romperia; pero ahi la pregunta se
  seguiria sorteando, que es lo contrario de lo que espera quien la da de baja.
  La respuesta lista los examenes involucrados para que la decision sea informada.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: una columna aditiva y NULLABLE, sin backfill. Todo lo que ya esta
  cargado queda con NULL, o sea vigente, que es el comportamiento de hoy.

REVERSIBILIDAD (downgrade):
  Dropea el indice y la columna. Las preguntas que estuvieran dadas de baja
  vuelven a estar vigentes — la lectura conservadora: sin la columna no hay forma
  de expresar la baja, y perder contenido seria peor que mostrar de mas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pregunta_banco",
        sa.Column(
            "eliminada_en",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Baja logica: NULL = vigente, con timestamp = dada de baja.",
        ),
    )
    # Parcial: el listado por defecto pide SOLO las vigentes, que es el caso
    # frecuente, y el indice no crece con lo que se va dando de baja.
    op.create_index(
        "ix_pregunta_banco_materia_vigentes",
        "pregunta_banco",
        ["materia_id"],
        postgresql_where=sa.text("eliminada_en IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_pregunta_banco_materia_vigentes", table_name="pregunta_banco")
    op.drop_column("pregunta_banco", "eliminada_en")
