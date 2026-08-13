"""063 - Tabla lti_deployment_confiable (C-75, allowlist de emisores LTI).

Revision ID: 0063
Revises: 0062
Create Date: 2026-08-10

PROPOSITO:
  Guarda qué `(iss, deployment_id, client_id)` de Moodle son de CONFIANZA para
  lanzar un launch LTI 1.3, y a qué `comision_id` de ActiveExam mapea ese contexto
  de curso (`context_id`). La confianza no es "el JWT está bien firmado" sino
  "está bien firmado Y el emisor es uno que dimos de alta" (design D2).

  Falla cerrado: tabla vacía = ningún `iss` confiable = todo launch se rechaza.

  Es ADITIVA. `comision_id` es nullable (ON DELETE SET NULL): un curso sin mapeo
  crea/loguea al alumno igual, pero no lo matricula.

ROLLBACK:
  alembic downgrade slim@0062 → dropea la tabla nueva. No toca nada existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

_UQ = "uq_lti_deployment_confiable_triple"
_IX_ISS = "ix_lti_deployment_confiable_iss"


def upgrade() -> None:
    op.create_table(
        "lti_deployment_confiable",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("iss", sa.Text, nullable=False),
        sa.Column("deployment_id", sa.Text, nullable=False),
        sa.Column("client_id", sa.Text, nullable=False),
        sa.Column("jwks_uri", sa.Text, nullable=False),
        sa.Column("context_id", sa.Text, nullable=True),
        sa.Column(
            "comision_id",
            UUID(as_uuid=False),
            sa.ForeignKey("comision.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "creado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("iss", "deployment_id", "client_id", name=_UQ),
    )
    op.create_index(_IX_ISS, "lti_deployment_confiable", ["iss"])


def downgrade() -> None:
    op.drop_index(_IX_ISS, table_name="lti_deployment_confiable")
    op.drop_table("lti_deployment_confiable")
