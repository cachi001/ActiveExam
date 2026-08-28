"""0102 - marcar las rendiciones de prueba del docente.

Revision ID: 0102
Revises: 0101
Create Date: 2026-08-28

PROPOSITO:
  Un examen en borrador existe para probarlo antes de soltarlo, pero el docente
  no podia rendirlo: la guarda de inscripcion (C-71) lo frena, porque nunca esta
  inscripto como alumno de su propia comision. Al destrabar eso aparece el
  problema de verdad: su rendicion quedaria guardada como una sesion igual a la
  de cualquier alumno, o sea que el docente figuraria en la tabla de resultados
  con nota propia, contaria en las estadisticas y seria candidato a que esa nota
  se publique en Moodle.

  Esta columna es lo que separa las dos cosas. La marca la pone el SERVIDOR
  segun el rol de quien crea la sesion, nunca el cliente (regla dura #6: el
  cliente es un sensor no confiable, y un alumno no puede auto-declararse
  docente para que su rendicion no cuente).

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: columna aditiva con server_default 'false'. Todo lo ya rendido
  queda como rendicion real, que es lo que es.

REVERSIBILIDAD (downgrade):
  Dropea el indice y la columna. Las pruebas de docentes que hubiera vuelven a
  contarse como rendiciones reales — por eso el downgrade solo es seguro si no
  se uso la funcionalidad todavia.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column(
            "es_prueba",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment=(
                "El docente probando su propio examen. No cuenta como rendicion: "
                "queda fuera de notas, estadisticas y write-back."
            ),
        ),
    )
    # Las consultas de resultados piden las rendiciones REALES de un examen, o
    # sea que filtran por esta columna en todos los casos.
    op.create_index(
        "ix_proctoring_session_examen_reales",
        "proctoring_session",
        ["examen_contenido_id"],
        postgresql_where=sa.text("es_prueba = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_proctoring_session_examen_reales", table_name="proctoring_session"
    )
    op.drop_column("proctoring_session", "es_prueba")
