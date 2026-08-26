"""0089 - c-78 D9/D10: mostrar_nota='nunca' por default + eventos al alumno.

Revision ID: 0089
Revises: 0088
Create Date: 2026-08-24

PROPOSITO (D9 — E-01):
  `mostrar_nota` tenia dos valores ('al_cerrar' | 'inmediata') y ninguno de los
  dos permite lo que el docente realmente hace: revisar ANTES de publicar. Con
  'al_cerrar' la nota se publicaba SOLA al vencer el cierre, sin que nadie la
  mirara. Se suma el valor 'nunca' y pasa a ser el DEFAULT de todo examen nuevo:
  la nota se publica cuando una persona lo decide.

  Se agregan `notas_publicadas_en` / `notas_publicadas_por` para que el detalle
  del examen pueda decir "publicadas el {fecha} por {persona}" en vez de dejar
  el estado ambiguo.

  La transicion es de IDA (nunca -> al_cerrar -> inmediata). Eso se valida en el
  dominio (`transicion_visibilidad_permitida`), no con un CHECK: la regla mira el
  valor ANTERIOR, cosa que un constraint de columna no puede hacer.

PROPOSITO (D10 — E-02):
  `mostrar_eventos_alumno`: si el alumno ve los eventos de proctoring MIENTRAS
  rinde. Default false por decision del dueno.

BACKFILL — LA PARTE QUE IMPORTA:
  Los examenes EXISTENTES se quedan con su valor actual ('al_cerrar' o
  'inmediata'). El default nuevo aplica SOLO a los examenes que se creen de acá
  en más. Cambiarle la visibilidad a un examen ya rendido seria esconder una nota
  que el alumno pudo haber visto — el reverso exacto de lo que D9 quiere evitar.

  Por eso el ALTER usa `SET DEFAULT` sobre la columna y NO un UPDATE masivo.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: dos columnas nuevas NULLABLE, una nueva NOT NULL con default, y un
  cambio de DEFAULT (que no reescribe filas existentes). Ningun lector se rompe.

REVERSIBILIDAD (downgrade):
  Vuelve el default a 'al_cerrar' y dropea las tres columnas nuevas. Los examenes
  que hayan quedado en 'nunca' se normalizan a 'al_cerrar' en el downgrade: el
  codigo viejo no conoce ese valor y lo trataria como "no inmediata", o sea
  'al_cerrar' de hecho — se hace explicito para no dejar un valor que el enum
  anterior no admite.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D9: el default nuevo. NO se hace UPDATE de las filas existentes (ver arriba).
    op.alter_column(
        "examen_contenido",
        "mostrar_nota",
        server_default="nunca",
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "notas_publicadas_en",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="c-78: cuando se publicaron las notas. NULL = todavia ocultas.",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "notas_publicadas_por",
            sa.Text(),
            nullable=True,
            comment="c-78: actor que publico las notas (email). NULL = sin publicar.",
        ),
    )
    # D10: eventos de proctoring visibles al alumno mientras rinde. Default NO.
    op.add_column(
        "examen_contenido",
        sa.Column(
            "mostrar_eventos_alumno",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="c-78 D10: el alumno ve sus eventos de proctoring mientras rinde.",
        ),
    )


def downgrade() -> None:
    op.drop_column("examen_contenido", "mostrar_eventos_alumno")
    op.drop_column("examen_contenido", "notas_publicadas_por")
    op.drop_column("examen_contenido", "notas_publicadas_en")
    # 'nunca' no existe en el enum anterior: se normaliza al valor que el codigo
    # viejo interpretaria de hecho (no-inmediata = al_cerrar).
    op.execute(
        sa.text(
            "UPDATE examen_contenido SET mostrar_nota = 'al_cerrar' "
            "WHERE mostrar_nota = 'nunca'"
        )
    )
    op.alter_column(
        "examen_contenido",
        "mostrar_nota",
        server_default="al_cerrar",
        existing_type=sa.String(20),
        existing_nullable=False,
    )
