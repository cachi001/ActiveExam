"""065 - Tabla lti_tool_key (C-75, par de claves RS256 de ActiveExam-como-Tool).

Revision ID: 0065
Revises: 0064
Create Date: 2026-08-10

PROPOSITO:
  LTI 1.3 exige que el Tool exponga un JWKS público (`GET /lti/jwks`) con clave
  RS256 (asimétrica) para que Moodle verifique mensajes firmados por ActiveExam
  y para el registro dinámico (design D3). El JWT de sesión (`emitir_jwt_propio`)
  es HS256 simétrico y NO sirve para eso.

  `clave_privada_cifrada` guarda el PEM de la clave privada RSA cifrado con Fernet
  (`SecretCipher`, misma clave EMBEDDING_ENCRYPTION_KEY que `moodle_credencial`),
  NUNCA en claro. `clave_publica_jwk` guarda el JWK público (kid, kty, n, e) que
  se sirve tal cual en el JWKS.

  Rotación soportada: varias filas, `activo=true` en la vigente para firmar; el
  JWKS puede publicar 2 claves durante la transición.

  Es ADITIVA.

ROLLBACK:
  alembic downgrade slim@0064 → dropea la tabla nueva. No toca nada existente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None

_IX_ACTIVO = "ix_lti_tool_key_activo"


def upgrade() -> None:
    op.create_table(
        "lti_tool_key",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kid", sa.Text, nullable=False, unique=True),
        sa.Column("clave_privada_cifrada", sa.Text, nullable=False),
        sa.Column("clave_publica_jwk", JSONB, nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "creado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(_IX_ACTIVO, "lti_tool_key", ["activo"])


def downgrade() -> None:
    op.drop_index(_IX_ACTIVO, table_name="lti_tool_key")
    op.drop_table("lti_tool_key")
