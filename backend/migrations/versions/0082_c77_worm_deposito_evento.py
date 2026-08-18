"""0082 - c-77 (rama activeexam): columnas del deposito WORM en proctoring_event.

Revision ID: 0082
Revises: 0081
Create Date: 2026-08-18

PROPOSITO:
  Tarea 18.3 del change c-77-minio-worm-evidencia: cuando MinIO esta configurado
  (minio_configurado(settings) True), ademas de persistir screenshot_b64 en
  Postgres (sin cambios, comportamiento actual intacto), event_service deposita
  el mismo binario en el bucket WORM (Object Lock Compliance) y guarda la
  referencia (object_key, uri, retain_until) en estas 3 columnas nuevas.

  TODAS NULLABLE: si MinIO no esta configurado (Render hoy, sin VPS) quedan NULL
  para siempre y el comportamiento es identico al de antes de este change.

SOBRE "DESTRUCTIVA EN DOS PASOS":
  No aplica: 3 columnas nuevas nullable, sin default que reescriba filas
  existentes, sin lectores existentes que dependan de su ausencia.

REVERSIBILIDAD (downgrade):
  Reversible sin perdida de informacion relevante: el downgrade quita las 3
  columnas (se pierde solo la referencia al deposito WORM, no el screenshot en
  Postgres ni la sesion).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_event",
        sa.Column(
            "worm_object_key",
            sa.String(length=255),
            nullable=True,
            comment="Key del objeto en el bucket WORM (c-77). NULL si MinIO no esta configurado.",
        ),
    )
    op.add_column(
        "proctoring_event",
        sa.Column(
            "worm_uri",
            sa.Text(),
            nullable=True,
            comment="URI completa del deposito WORM (endpoint/bucket/object_key).",
        ),
    )
    op.add_column(
        "proctoring_event",
        sa.Column(
            "worm_retain_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="retain_until del Object Lock Compliance aplicado al depositar.",
        ),
    )


def downgrade() -> None:
    op.drop_column("proctoring_event", "worm_retain_until")
    op.drop_column("proctoring_event", "worm_uri")
    op.drop_column("proctoring_event", "worm_object_key")
