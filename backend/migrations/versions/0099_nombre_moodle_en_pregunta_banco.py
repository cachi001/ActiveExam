"""0099 - nombre de la pregunta en Moodle, para reimportar sin duplicar.

Revision ID: 0099
Revises: 0098
Create Date: 2026-08-27

PROPOSITO:
  El import de banco por XML resolvia "pregunta nueva vs pregunta ya existente"
  comparando el ENUNCIADO. Es la unica clave que tenia: `moodle_question_id` solo
  se llena por el sync via API, y un export XML de Moodle no trae ese id.

  Consecuencia, verificada contra produccion el 26/8/2026: corregir el texto de
  una pregunta en Moodle y volver a subir el banco la daba de alta OTRA VEZ. La
  version vieja quedaba viva, las dos elegibles para el sorteo del mismo examen, y
  sin forma de borrar ninguna desde la aplicacion (no hay endpoint de baja de
  preguntas del banco). Un docente que corrige una errata termina con el banco
  contaminado y sin manera de limpiarlo.

  El XML si trae algo estable: `<name><text>`, el nombre de la pregunta. Se guarda
  y pasa a ser la clave de reconocimiento del reimport.

ORDEN DE MATCHEO (en import_service):
  1. `moodle_question_id` — sync via API, el mas confiable.
  2. `nombre_moodle` — reimport por XML. NUEVO.
  3. enunciado — respaldo para lo cargado antes de esta migracion.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: una columna aditiva y NULLABLE, sin backfill. Las preguntas que ya
  estan en la base quedan con NULL y se siguen reconociendo por enunciado, o sea
  exactamente como venian funcionando.

POR QUE NO ES UNIQUE:
  Moodle no garantiza nombres unicos dentro de un curso (dos categorias distintas
  pueden tener una "Pregunta 1"). Un UNIQUE (materia_id, nombre_moodle) rechazaria
  imports validos. El indice es solo para que la busqueda del import no escanee la
  tabla entera.

REVERSIBILIDAD (downgrade):
  Dropea el indice y la columna. Se pierde la clave de reimport y se vuelve al
  matcheo por enunciado; ninguna pregunta se borra.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pregunta_banco",
        sa.Column(
            "nombre_moodle",
            sa.Text(),
            nullable=True,
            comment="Nombre de la pregunta en Moodle; clave de reimport por XML.",
        ),
    )
    op.create_index(
        "ix_pregunta_banco_materia_nombre_moodle",
        "pregunta_banco",
        ["materia_id", "nombre_moodle"],
        postgresql_where=sa.text("nombre_moodle IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_pregunta_banco_materia_nombre_moodle", table_name="pregunta_banco")
    op.drop_column("pregunta_banco", "nombre_moodle")
