"""0084 - tabla de confirmacion de alta LTI (primer ingreso).

Revision ID: 0084
Revises: 0083
Create Date: 2026-08-19

PROPOSITO:
  Hasta ahora un launch LTI que resultaba en una cuenta NUEVA se
  auto-provisionaba y logueaba sin ningun paso intermedio (bug real
  2026-08-19: el dueño del proyecto entro con su cuenta ADMIN de Moodle y
  quedo logueado como alumno sin haber confirmado nada). Esta tabla guarda,
  de forma efimera (5 min, uso unico), los claims YA VALIDADOS de un launch
  que resultaria en un alta nueva, para que el frontend pueda mostrar una
  pantalla de confirmacion ("vas a entrar como X, con el email Y") ANTES de
  crear la cuenta. Los reingresos (cuenta ya existente) NO pasan por aca —
  siguen logueando directo, sin friccion.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: tabla nueva, ningun lector/escritor existente depende de su
  ausencia.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion relevante: son registros efimeros
  (expiran en minutos); el downgrade dropea la tabla entera.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lti_provisioning_pendiente",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "deployment_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("lti_deployment_confiable.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claims",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Claims YA VALIDADOS del id_token (firma/nonce/aud/exp verificados "
            "en /lti/launch). Se re-usan tal cual al confirmar, sin re-validar el "
            "id_token (de un solo uso, ya consumido por el nonce).",
        ),
        sa.Column(
            "creado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expira_en", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "usado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="NULL = pendiente de confirmar. NOT NULL = ya consumido (uso unico).",
        ),
    )


def downgrade() -> None:
    op.drop_table("lti_provisioning_pendiente")
