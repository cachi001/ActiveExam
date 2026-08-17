"""0038 - código de matriculación único por comisión (activeexam, C-70).

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-07

RAMA: activeexam
  down_revision = "0037"
  branch_labels = None
  depends_on    = None

PROPÓSITO (modelo enrolment-key de Moodle):
  Agregar ``comision.codigo_matriculacion`` — código único GLOBAL con el que el
  alumno se auto-matricula a UNA comisión. Autogenerado a partir del código de la
  materia + sufijo aleatorio corto, o provisto por el docente.

MIGRACIÓN ADITIVA EN DOS PASOS (destructive-in-two-steps aplicado a unicidad):
  No se puede aplicar ``UNIQUE NOT NULL`` de una sobre filas existentes. Por eso:
    1. add_column nullable (String(80)).
    2. backfill: cada comisión preexistente recibe ``{materia.codigo}-{sufijo}``
       único (sufijo de alfabeto sin caracteres ambiguos, reintento ante colisión).
    3. aplicar UNIQUE (constraint nombrado) + NOT NULL (el backfill garantiza no-nulos).

  No reescribe otras tablas (patrón activeexam).

ROLLBACK:
  ``downgrade activeexam@0037`` dropea el constraint UNIQUE y la columna. No toca otras
  tablas ni las inscripciones.
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

_UQ_CODIGO_MATRICULACION = "uq_comision_codigo_matriculacion"

# Alfabeto sin caracteres ambiguos (sin O/0, I/1, L) — solo para el sufijo GENERADO.
_ALFABETO_SUFIJO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LARGO_SUFIJO = 4


def _sufijo() -> str:
    return "".join(secrets.choice(_ALFABETO_SUFIJO) for _ in range(_LARGO_SUFIJO))


def upgrade() -> None:
    # (1) Columna nullable.
    op.add_column(
        "comision",
        sa.Column("codigo_matriculacion", sa.String(80), nullable=True),
    )

    # (2) Backfill: código único por comisión preexistente.
    bind = op.get_bind()
    filas = bind.execute(
        sa.text(
            "SELECT c.id, m.codigo AS materia_codigo "
            "FROM comision c JOIN materia m ON m.id = c.materia_id"
        )
    ).fetchall()

    usados: set[str] = set()
    for fila in filas:
        prefijo = fila.materia_codigo
        while True:
            candidato = f"{prefijo}-{_sufijo()}"
            if candidato in usados:
                continue
            existe = bind.execute(
                sa.text(
                    "SELECT 1 FROM comision WHERE codigo_matriculacion = :cod LIMIT 1"
                ),
                {"cod": candidato},
            ).first()
            if existe is None:
                break
        usados.add(candidato)
        bind.execute(
            sa.text(
                "UPDATE comision SET codigo_matriculacion = :cod WHERE id = :id"
            ),
            {"cod": candidato, "id": fila.id},
        )

    # (3) UNIQUE + NOT NULL (el backfill dejó todas las filas con valor).
    op.create_unique_constraint(
        _UQ_CODIGO_MATRICULACION, "comision", ["codigo_matriculacion"]
    )
    op.alter_column("comision", "codigo_matriculacion", nullable=False)


def downgrade() -> None:
    op.drop_constraint(_UQ_CODIGO_MATRICULACION, "comision", type_="unique")
    op.drop_column("comision", "codigo_matriculacion")
