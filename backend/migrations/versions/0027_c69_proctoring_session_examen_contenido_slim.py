"""0027 - vinculo proctoring_session ↔ examen_contenido (slim, C-69).

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-27

RAMA: slim
  down_revision = "0026"
  branch_labels = None
  depends_on    = None

PROPÓSITO:
  Vincular la SESIÓN de proctoring del alumno con el EXAMEN DE CONTENIDO importado
  de Moodle XML (examen_contenido, migración 0026). El alumno rinde un contenido
  concreto; la sesión debe registrar contra QUÉ rindió, server-side, para la
  revisión humana (C-16) y el flujo del alumno.

  ¿Por qué en proctoring_session y no en `examen`? En la rama slim la tabla `examen`
  (config de proctoring) NO existe; `examen_contenido` (0026) y `proctoring_session`
  (0005) SÍ coexisten. El vínculo vive donde ambas tablas existen.

  Migración ADITIVA (una sola columna NULLABLE + FK + índice). No reescribe filas
  existentes (la columna nace NULL) ni toca otras tablas (D2).

  - examen_contenido_id: UUID NULLABLE. NULL = sesión sin contenido (modo 'test' o
    examen sin contenido asociado): la sesión sigue siendo válida.
  - FK ON DELETE SET NULL: borrar un examen_contenido del catálogo NUNCA borra la
    sesión ni su evidencia (cadena de custodia, L2.5) — solo se pierde la referencia.
  - índice: lecturas por contenido (cola de revisión / agrupar sesiones por examen).

ROLLBACK:
  alembic downgrade slim@0026 → dropea índice, FK y columna (en ese orden). No toca
  examen_contenido ni ninguna otra tabla.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_FK_NAME = "fk_proctoring_session_examen_contenido"
_IX_NAME = "ix_proctoring_session_examen_contenido_id"


def upgrade() -> None:
    op.add_column(
        "proctoring_session",
        sa.Column(
            "examen_contenido_id",
            UUID(as_uuid=False),
            nullable=True,
            comment="FK a examen_contenido(id). NULL = sesión sin contenido vinculado (C-69).",
        ),
    )
    op.create_foreign_key(
        _FK_NAME,
        source_table="proctoring_session",
        referent_table="examen_contenido",
        local_cols=["examen_contenido_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index(_IX_NAME, "proctoring_session", ["examen_contenido_id"])


def downgrade() -> None:
    op.drop_index(_IX_NAME, table_name="proctoring_session")
    op.drop_constraint(_FK_NAME, "proctoring_session", type_="foreignkey")
    op.drop_column("proctoring_session", "examen_contenido_id")
