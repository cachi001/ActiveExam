"""010 - solicitudes de via alternativa (C-63, rama slim).

Revision ID: 0010
Revises: 0009 (branch slim)
Create Date: 2026-06-08

RAMA: slim
  down_revision = "0009"   <- rama slim; no depende de rama principal
  branch_labels = None     <- hereda label "slim" de la cadena 0005 -> 0008 -> 0009
  depends_on    = None     <- SIN dependencia de migraciones de la rama principal

PROPOSITO:
  Crea el ENUM ``estado_via_alternativa`` y la tabla
  ``solicitudes_via_alternativa`` para persistir el estado mutable
  del ciclo de vida de la solicitud de via alternativa del alumno
  (pendiente_proctor -> habilitado_por_proctor).

  La tabla es NUEVA — no toca tablas existentes (no destructiva).
  Compatible con postgres:16-alpine (sin TimescaleDB, sin extensiones).

  Diseno (C-63 D-01, D-02, D-07):
    - ``user_id`` es id_institucional (TEXT, FK a usuario.id_institucional)
    - ``exam_id``  puede ser un UUID de examen o el valor sentinel "perfil"
      para el enrollment del perfil (D-08).
    - El par (user_id, exam_id) tiene un UNIQUE para evitar duplicados.
    - No hay columna ``rechazado`` (Non-Goal de C-63; se agrega en c-47).

ROLLBACK:
  alembic downgrade slim@0009  -> elimina tabla + tipo ENUM.

VERIFICACION:
  alembic upgrade slim@head   -> aplica 0005->0008->0009->0010 contra postgres:16-alpine
  alembic history             -> debe mostrar 0010 al tope de la rama slim
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "0010"
down_revision = "0009"   # rama slim — NO la rama principal
branch_labels = None     # hereda el label "slim" de la cadena
depends_on = None        # SIN dependencia de migraciones de la rama principal

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    """Crea el ENUM y la tabla solicitudes_via_alternativa (no destructivo)."""

    # 1. Crear el tipo ENUM nativo de Postgres (IF NOT EXISTS: idempotente)
    op.execute(
        "CREATE TYPE estado_via_alternativa AS ENUM "
        "('pendiente_proctor', 'habilitado_por_proctor')"
    )

    # 2. Crear la tabla usando el ENUM ya existente via DDL crudo para la columna.
    #    Usamos sa.Text + cast en la columna estado para evitar que SQLAlchemy
    #    intente crear el tipo otra vez (conflicto con create_type).
    #    La columna estado se crea con el tipo ENUM via server_default y DDL explícito.
    op.create_table(
        "solicitudes_via_alternativa",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Text,
            sa.ForeignKey("usuario.id_institucional", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exam_id",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "timestamp_solicitud",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "timestamp_habilitacion",
            TIMESTAMPTZ,
            nullable=True,
        ),
        sa.Column(
            "habilitado_por",
            sa.Text,
            nullable=True,
        ),
        # El par (user_id, exam_id) debe ser unico: un alumno solo puede tener
        # una solicitud activa por examen.
        sa.UniqueConstraint("user_id", "exam_id", name="uq_solicitud_via_alternativa"),
    )

    # 3. Agregar la columna estado con tipo ENUM via DDL puro (evita que SQLAlchemy
    #    intente hacer CREATE TYPE nuevamente).
    op.execute(
        "ALTER TABLE solicitudes_via_alternativa "
        "ADD COLUMN estado estado_via_alternativa NOT NULL "
        "DEFAULT 'pendiente_proctor'"
    )

    # Indice para buscar por user_id
    op.create_index(
        "ix_solicitudes_via_alternativa_user_id",
        "solicitudes_via_alternativa",
        ["user_id"],
    )

    # Indice para listar por estado (consulta del proctor: listar pendientes)
    op.create_index(
        "ix_solicitudes_via_alternativa_estado",
        "solicitudes_via_alternativa",
        ["estado"],
    )


def downgrade() -> None:
    """Elimina la tabla y el ENUM (rollback completo)."""
    op.drop_index(
        "ix_solicitudes_via_alternativa_estado",
        table_name="solicitudes_via_alternativa",
    )
    op.drop_index(
        "ix_solicitudes_via_alternativa_user_id",
        table_name="solicitudes_via_alternativa",
    )
    op.drop_table("solicitudes_via_alternativa")
    op.execute("DROP TYPE IF EXISTS estado_via_alternativa")
