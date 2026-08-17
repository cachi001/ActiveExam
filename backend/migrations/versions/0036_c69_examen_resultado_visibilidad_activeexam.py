"""C-69: visibilidad de resultados por examen (mostrar_nota, revision_habilitada).

Gate estilo Moodle "Review options": la nota y la revisión se muestran al alumno
según la config del examen, NO siempre al instante:
- ``mostrar_nota``: 'al_cerrar' (default) | 'inmediata'. 'al_cerrar' → la nota se
  muestra recién cuando pasa la fecha de cierre del examen.
- ``revision_habilitada``: si el alumno puede ver la corrección (respuestas
  correctas). Default false. Nunca se muestra antes que la nota.

Aditiva (columnas con server_default) — no destructiva.
"""

from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "examen_contenido",
        sa.Column(
            "mostrar_nota",
            sa.String(20),
            nullable=False,
            server_default="al_cerrar",
        ),
    )
    op.add_column(
        "examen_contenido",
        sa.Column(
            "revision_habilitada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("examen_contenido", "revision_habilitada")
    op.drop_column("examen_contenido", "mostrar_nota")
