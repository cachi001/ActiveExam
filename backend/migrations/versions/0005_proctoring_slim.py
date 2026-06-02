"""005 - tablas del modulo slim de proctoring.

Revision ID: 0005
Revises: (ninguna — branch independiente)
Create Date: 2026-06-02

Branch: slim (independiente del branch default de produccion)
  - NO depende de 0001 (TimescaleDB) ni de 0002 (hypertable, trigger, ENUM nativo).
  - Se corre con: alembic upgrade slim@head
  - El Dockerfile.slim usa este comando explicitamente.

Scope (C-45, proctoring-slim):
  - upgrade: crea proctoring_session, proctoring_event, proctoring_biometria +
    indices de rendimiento.
  - downgrade: elimina las 3 tablas en orden inverso (biometria → event → session).

PRODUCCION (Ley 25.326):
  - screenshot_b64: dato sensible; para produccion usar MinIO/S3 WORM + cifrado.
  - embedding: dato sensible; cifrar con KMS; purgar al egreso del alumno (DSR).
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = None  # Branch independiente — no depende de migraciones de produccion
branch_labels = ("slim",)
depends_on = None

# Tipo TIMESTAMPTZ para columnas de tiempo (Postgres nativo)
TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    # --- proctoring_session ---
    op.create_table(
        "proctoring_session",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("modo", sa.String(20), nullable=False, comment="'test' o 'examen'"),
        sa.Column("exam_id", sa.String(255), nullable=True),
        sa.Column("etiqueta", sa.String(255), nullable=True),
        sa.Column(
            "creada_en",
            TIMESTAMPTZ,
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finalizada_en", TIMESTAMPTZ, nullable=True),
    )

    # Indice para listar sesiones ordenadas por fecha descendente (D5)
    op.create_index(
        "ix_proctoring_session_creada_en",
        "proctoring_session",
        [sa.text("creada_en DESC")],
    )

    # --- proctoring_event ---
    op.create_table(
        "proctoring_event",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column(
            "severidad",
            sa.String(20),
            nullable=False,
            comment="'bajo' | 'medio' | 'alto' | 'critico'",
        ),
        sa.Column("ts_cliente", TIMESTAMPTZ, nullable=False),
        sa.Column(
            "ts_backend",
            TIMESTAMPTZ,
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "screenshot_b64",
            sa.Text,
            nullable=True,
            comment=(
                "PRODUCCION: dato sensible Ley 25.326 — "
                "mover a MinIO/S3 WORM con cifrado at-rest y politica de retencion."
            ),
        ),
        sa.Column(
            "screenshot_sha256",
            sa.String(64),
            nullable=True,
            comment=(
                "SHA-256 hex del screenshot (integridad liviana, D9). "
                "PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)."
            ),
        ),
        sa.Column(
            "face_count_cliente",
            sa.Integer,
            nullable=True,
            comment="Conteo de rostros reportado por el cliente",
        ),
        sa.Column(
            "face_count_servidor",
            sa.Integer,
            nullable=True,
            comment="Conteo re-detectado server-side con MediaPipe (mismo motor que cliente, D8)",
        ),
        sa.Column(
            "veredicto_reinferencia",
            sa.String(20),
            nullable=False,
            server_default="no_evaluado",
            comment="'coincide' | 'discrepancia' | 'no_evaluado'. L2.5: nunca sanciona.",
        ),
    )

    # Indice para queries de historial por sesion ordenado por ts_backend
    op.create_index(
        "ix_proctoring_event_session_ts",
        "proctoring_event",
        ["session_id", "ts_backend"],
    )

    # --- proctoring_biometria ---
    op.create_table(
        "proctoring_biometria",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=False),
            sa.ForeignKey("proctoring_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("liveness_ok", sa.Boolean, nullable=False),
        sa.Column(
            "retos_resueltos",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "embedding",
            sa.Text,
            nullable=True,
            comment=(
                "PRODUCCION: dato sensible (Ley 25.326); "
                "cifrar con KMS antes de persistir; purgar al egreso (DD-13, DSR)."
            ),
        ),
        sa.Column("resultado", sa.String(50), nullable=False),
        sa.Column(
            "registrada_en",
            TIMESTAMPTZ,
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Eliminar en orden inverso (respetar FK constraints)
    op.drop_table("proctoring_biometria")
    op.drop_index("ix_proctoring_event_session_ts", table_name="proctoring_event")
    op.drop_table("proctoring_event")
    op.drop_index("ix_proctoring_session_creada_en", table_name="proctoring_session")
    op.drop_table("proctoring_session")
