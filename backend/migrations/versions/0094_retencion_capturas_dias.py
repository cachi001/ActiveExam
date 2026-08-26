"""Retencion de CAPTURAS de proctoring: configuracion_sistema.retencion_capturas_dias.

Revision ID: 0094
Revises: 0093
Create Date: 2026-08-25

PROPOSITO:
  `proctoring_event.screenshot_b64` guarda la captura en base64 dentro de
  Postgres (sin WORM configurado en produccion hoy, es la UNICA copia) y nunca
  se borraba. Un examen de 100 alumnos escribe ~360 MB, y son imagenes de la
  cara y la pantalla de alumnos: guardarlas para siempre es un problema de
  cumplimiento (Ley 25.326 + el DPIA del proyecto), no solo de disco.

  Esta columna es la POLITICA (cuantos dias se conservan); el purgado en si lo
  dispara `POST /api/v1/admin/retention/capturas` (nunca solo, sin cron ni
  scheduler — WORM apagado en produccion, Postgres es la unica copia de la
  imagen hoy).

DECISION DEL DUEÑO: default 180 dias (un cuatrimestre), minimo 90. El minimo
  se valida en dominio (app.domain.retention.policy.validar_retencion_capturas_dias)
  y en el endpoint que edita la config — a proposito SIN CHECK de base, para
  poder devolver un mensaje entendible en vez de un error de constraint.

DISTINTA de `retencion_dias_default` (365, retencion GENERAL de sesion, C-19):
  esta es especifica del dato mas pesado y sensible (capturas). No se toca ni
  se reutiliza esa columna.

Aditiva (columna con server_default) — no destructiva.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_sistema",
        sa.Column(
            "retencion_capturas_dias",
            sa.Integer(),
            nullable=False,
            server_default="180",
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion_sistema", "retencion_capturas_dias")
