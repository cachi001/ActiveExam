"""0090 - c-78 D14: marcado MANUAL de la nota cargada en el campus.

Revision ID: 0090
Revises: 0089
Create Date: 2026-08-24

PROPOSITO (E-10 / D14):
  Hay campus SIN API: la nota se carga a mano en Moodle y en ActiveExam quedaba
  'pendiente' PARA SIEMPRE. Un estado que nunca cambia deja de significar algo —
  la pantalla de notas mostraba una lista entera de "pendientes" que en realidad
  ya estaban cargadas.

  Se habilita marcarla a mano. Dos columnas nuevas registran QUIEN lo hizo y
  CUANDO, y el estado resultante es 'manual' (valor nuevo de la columna
  `estado`), NO 'enviado'.

POR QUE UN ESTADO PROPIO Y NO REUSAR 'enviado':
  Porque no valen lo mismo. 'enviado' significa "el campus confirmo que recibio
  la nota"; 'manual' significa "una persona dice que la cargo". Colapsarlos
  borraria la diferencia justo donde importa: cuando hay un reclamo por una nota
  que no aparece en el campus. Ademas, el codigo trata 'enviado' como final e
  idempotente (no re-envia); un 'manual' que se hiciera pasar por 'enviado'
  bloquearia el envio real si despues el campus vuelve a estar disponible.

  Por lo mismo, el endpoint RECHAZA (409) marcar a mano una fila ya 'enviado':
  una afirmacion humana no puede pisar una confirmacion del sistema.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: dos columnas aditivas y NULLABLE, sin backfill. La columna `estado`
  es un String(20) libre (no un ENUM de Postgres), asi que admitir un valor mas
  no requiere ALTER TYPE ni reescritura.

REVERSIBILIDAD (downgrade):
  Dropea las dos columnas y normaliza las filas en 'manual' a 'pendiente' — que
  es lo que el codigo anterior entiende y, ademas, la lectura conservadora: sin
  el registro de quien lo marco, no hay respaldo para afirmar que se cargo.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "moodle_writeback_estado",
        sa.Column(
            "marcada_manual_por",
            sa.Text(),
            nullable=True,
            comment="c-78 D14: quien marco a mano que la nota se cargo en el campus.",
        ),
    )
    op.add_column(
        "moodle_writeback_estado",
        sa.Column(
            "marcada_manual_en",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="c-78 D14: cuando se marco a mano. NULL = nunca se marco.",
        ),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE moodle_writeback_estado SET estado = 'pendiente' "
            "WHERE estado = 'manual'"
        )
    )
    op.drop_column("moodle_writeback_estado", "marcada_manual_en")
    op.drop_column("moodle_writeback_estado", "marcada_manual_por")
