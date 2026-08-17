"""0046 - mezclar_preguntas siempre activo + limite de preguntas por examen.

Revision ID: 0046
Revises: 0045 (branch activeexam)
Create Date: 2026-07-28

RAMA: activeexam
  down_revision = "0045"

PROPOSITO:
  1. `examen_contenido.mezclar_preguntas` pasa a ser SIEMPRE true. Deja de ser
     una opcion del docente: el orden aleatorio por alumno es una medida de
     integridad de la rendicion, no una preferencia. Con el toggle apagado, dos
     alumnos sentados juntos ven exactamente la misma pregunta al mismo tiempo.

     Mezclar solo cambia el ORDEN; no elige un subconjunto de preguntas ni
     cambia la nota (todos rinden las mismas preguntas). Por eso se puede forzar
     sin afectar la equidad — al contrario, la protege.

     Backfill: las filas existentes en false pasan a true. Es un cambio de
     comportamiento para esos examenes, pero solo en el orden de presentacion.
     Los examenes YA rendidos no se recalculan: la nota no depende del orden.

  2. `examen_contenido.limite_preguntas` INTEGER NULL: tope de preguntas que se
     pueden importar/seleccionar para ese examen. NULL = sin tope. Se agrega
     aditiva y sin backfill.

REVERSIBILIDAD:
  El downgrade devuelve el server_default a false y borra la columna nueva, pero
  NO puede restaurar que examenes tenian mezclar_preguntas en false (el dato
  original se pierde en el backfill). Es aceptable: el valor previo era una
  preferencia, no un dato del negocio.
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Mezclar SIEMPRE: default nuevo + backfill de lo existente.
    op.alter_column(
        "examen_contenido",
        "mezclar_preguntas",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.execute(
        "UPDATE examen_contenido SET mezclar_preguntas = true "
        "WHERE mezclar_preguntas = false"
    )

    # 2. Tope de preguntas por examen (NULL = sin tope).
    op.add_column(
        "examen_contenido",
        sa.Column("limite_preguntas", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_examen_contenido_limite_preguntas_positivo",
        "examen_contenido",
        "limite_preguntas IS NULL OR limite_preguntas > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_examen_contenido_limite_preguntas_positivo",
        "examen_contenido",
        type_="check",
    )
    op.drop_column("examen_contenido", "limite_preguntas")
    op.alter_column(
        "examen_contenido",
        "mezclar_preguntas",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
