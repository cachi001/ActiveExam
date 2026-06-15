"""015 - configuracion_sistema (singleton) + consentimiento_perfil (rama FULL).

Revision ID: 0015
Revises: 0007 (rama principal/full)
Create Date: 2026-06-15

RAMA: full (principal, con TimescaleDB)
  down_revision = "0007"   # cabeza de la rama full (0001->0002->0003->0004->0006->0007)
  branch_labels = None
  depends_on    = None

PROPOSITO (change configuracion-sistema-funcional, Grupo 0):
  Espeja en la rama FULL las dos tablas ADITIVAS creadas en slim por 0014:
  ``configuracion_sistema`` (singleton global versionado) y ``consentimiento_perfil``
  (append-only, Ley 25.326). Mismo schema que slim (no usan TimescaleDB).

  El numero de revision 0015 NO colisiona con 0008-0014 (rama slim): alembic
  identifica por revision id, y esta migracion cuelga de 0007 (rama full), no de la
  cadena slim. Aditivas: sin DROP/ALTER destructivo.

ROLLBACK:
  alembic downgrade 0007  -> dropea las dos tablas (destructivo, paso 2 separado).

VERIFICACION:
  alembic upgrade head    -> aplica 0007 -> 0015 sobre la rama full.
  Espera configuracion_sistema (1 fila id='global') y consentimiento_perfil (vacia).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision = "0015"
down_revision = "0007"
branch_labels = None
depends_on = None

TIMESTAMPTZ = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "configuracion_sistema",
        sa.Column("id", sa.String(32), primary_key=True, server_default="global"),
        sa.Column("face_absent_ms", sa.Integer, nullable=False, server_default="3000"),
        sa.Column(
            "multiple_faces_frames", sa.Integer, nullable=False, server_default="5"
        ),
        sa.Column(
            "gaze_deviation_threshold", sa.Float, nullable=False, server_default="0.20"
        ),
        sa.Column("gaze_sustained_ms", sa.Integer, nullable=False, server_default="2500"),
        sa.Column(
            "gaze_fixation_tolerance", sa.Float, nullable=False, server_default="0.25"
        ),
        sa.Column(
            "umbral_cola_revision", sa.Integer, nullable=False, server_default="70"
        ),
        sa.Column("detectores_activos", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "retencion_dias_default", sa.Integer, nullable=False, server_default="365"
        ),
        sa.Column(
            "consent_version_vigente",
            sa.String(64),
            nullable=False,
            server_default="v1",
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.CheckConstraint(
            "umbral_cola_revision >= 0 AND umbral_cola_revision <= 100",
            name="ck_configuracion_sistema_umbral_rango",
        ),
    )
    op.execute(
        """
        INSERT INTO configuracion_sistema
            (id, face_absent_ms, multiple_faces_frames, gaze_deviation_threshold,
             gaze_sustained_ms, gaze_fixation_tolerance, umbral_cola_revision,
             detectores_activos, retencion_dias_default, consent_version_vigente, version)
        VALUES
            ('global', 3000, 5, 0.20, 2500, 0.25, 70,
             '["rostro_ausente","multiples_rostros","mirada_desviada_sostenida",
               "perdida_de_foco","cambio_pestana","monitor_adicional",
               "salida_pantalla_completa","copiar_pegar"]'::jsonb,
             365, 'v1', 1)
        ON CONFLICT (id) DO NOTHING
        """
    )

    op.create_table(
        "consentimiento_perfil",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=False),
            sa.ForeignKey("usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_texto", sa.String(64), nullable=False),
        sa.Column("hash_texto", sa.String(64), nullable=False),
        sa.Column(
            "timestamp", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("estado", sa.String(32), nullable=False),
        sa.Column("hash_registro", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "estado IN ('otorgado','revocado','via_alternativa')",
            name="ck_consentimiento_perfil_estado_valido",
        ),
    )
    op.create_index(
        "ix_consentimiento_perfil_usuario_id",
        "consentimiento_perfil",
        ["usuario_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consentimiento_perfil_usuario_id", table_name="consentimiento_perfil"
    )
    op.drop_table("consentimiento_perfil")
    op.drop_table("configuracion_sistema")
