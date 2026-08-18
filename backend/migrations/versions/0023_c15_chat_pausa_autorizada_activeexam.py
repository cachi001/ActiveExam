"""0023 - chat bidireccional + pausa autorizada (activeexam, C-15 tareas 6.x).

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-22

RAMA: activeexam
  down_revision = "0022"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  C-15 backend activeexam (chat proctor<->alumno + flujo de pausa autorizada). El activeexam
  NO monta el WS de eventos: el transporte es REST + polling. Esta migracion es
  ADITIVA — crea dos tablas nuevas, no toca tablas existentes:

    mensaje_chat      -- mensajes del chat (autor 'alumno'|'proctor', texto)
    pausa_autorizada  -- solicitudes/resoluciones de pausa (estado, ventana, actor)

  Ambas FK -> proctoring_session.id con ON DELETE CASCADE (al borrar la sesion se
  borran sus mensajes y pausas).

  L2.5 (regla dura #5 y #6): la pausa solo CONTEXTUALIZA el score (excluye eventos
  dentro de la ventana del puntaje, no los borra). ``pausa_autorizada``, con
  proctor_actor + timestamps, ES el rastro de auditoria persistente de la pausa.

ROLLBACK:
  alembic downgrade activeexam@0022 -> dropea ambas tablas (y sus datos). No destructivo
  para el resto del esquema.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mensaje_chat",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("autor", sa.String(20), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("texto", sa.String(2000), nullable=False),
        sa.Column(
            "creado_en",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_mensaje_chat_session_creado",
        "mensaje_chat",
        ["session_id", "creado_en"],
    )

    op.create_table(
        "pausa_autorizada",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column(
            "solicitada_en",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resuelta_en", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("proctor_actor", sa.String(255), nullable=True),
        sa.Column("inicio_en", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fin_en", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_pausa_autorizada_session_solicitada",
        "pausa_autorizada",
        ["session_id", "solicitada_en"],
    )
    op.create_index(
        "ix_pausa_autorizada_estado",
        "pausa_autorizada",
        ["estado"],
    )


def downgrade() -> None:
    op.drop_index("ix_pausa_autorizada_estado", table_name="pausa_autorizada")
    op.drop_index(
        "ix_pausa_autorizada_session_solicitada", table_name="pausa_autorizada"
    )
    op.drop_table("pausa_autorizada")
    op.drop_index("ix_mensaje_chat_session_creado", table_name="mensaje_chat")
    op.drop_table("mensaje_chat")
