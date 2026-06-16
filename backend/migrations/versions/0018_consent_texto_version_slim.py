"""018 - tabla consent_texto_version (rama slim, texto versionado Ley 25.326).

Revision ID: 0018
Revises: 0016 (rama slim)
Create Date: 2026-06-16

RAMA: slim
  down_revision = "0016"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Crea la tabla ``consent_texto_version`` para persistir cada version del texto
  de consentimiento informado (Ley 25.326) en la DB, de modo que el admin pueda
  publicar nuevas versiones y los estudiantes deban re-consentir cuando cambie la
  version vigente (``configuracion_sistema.consent_version_vigente``).

  La tabla es APPEND-ONLY por semantica: version es PK, el texto NUNCA muta
  (misma version => mismo hash; texto nuevo => nueva version).

  Esta migracion es SLIM (solo crea la estructura). El seed de v1 va en 0019.

  Columnas:
    version    VARCHAR PK    — clave de la version ('v1', 'v2', ...)
    bloques    JSONB         — lista de bloques [{titulo, cuerpo}]
    hash_texto VARCHAR       — SHA-256 deterministico de version+bloques
    created_at TIMESTAMPTZ   — auto-now
    created_by VARCHAR NULL  — quien publico la version (id_institucional)

ROLLBACK:
  alembic downgrade slim@0016 -> dropea la tabla (destructivo, paso 2 separado).

VERIFICACION:
  alembic upgrade slim@head -> aplica 0016 -> 0018 -> 0019.
  Espera consent_texto_version con una fila v1.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0018"
down_revision = "0016"
branch_labels = None
depends_on = None

TIMESTAMPTZ = TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "consent_texto_version",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("bloques", JSONB, nullable=False),
        sa.Column("hash_texto", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("consent_texto_version")
