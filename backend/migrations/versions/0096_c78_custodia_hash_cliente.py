"""Cadena de custodia cliente -> backend: proctoring_event.screenshot_sha256_cliente.

Revision ID: 0096
Revises: 0095
Create Date: 2026-08-25

PROPOSITO:
  El cliente calcula el SHA-256 de la captura y lo manda en
  `screenshot_sha256_cliente`. El schema `IngestEventoIn` lo acepta desde C-64 y
  `event_service.ingestar_evento` lo DESCARTABA, con un comentario explicito de
  que no habia columna donde guardarlo. O sea que la primera capa de la cadena de
  custodia de la regla dura #6 ("el backend re-hashea lo que manda el cliente")
  no existia: nadie comparaba nada con nada.

  Peor todavia, los dos lados hasheaban COSAS DISTINTAS: el cliente hashea los
  bytes decodificados de la imagen y `sha256_hex` hashea los bytes UTF-8 del
  string base64 completo (prefijo `data:image/jpeg;base64,` incluido). Comparar
  esos dos valores de frente habria marcado TODOS los eventos como manipulados.
  Por eso se agrego `sha256_de_imagen`, que hashea lo mismo que el cliente.

COLUMNAS:
  - `screenshot_sha256_cliente`: lo que AFIRMA el cliente. Se guarda tal cual
    llego, sea verdad o no — es parte de la evidencia.
  - `custodia_cliente`: veredicto de la comparacion contra lo que recalculo el
    servidor. 'coincide' | 'discrepancia' | 'no_verificable'.

L2.5 (regla dura #5): una 'discrepancia' NUNCA rechaza el evento ni sanciona. Es
  una senal para el revisor humano. Las filas preexistentes quedan en
  'no_verificable', que es la verdad: de esas nunca se comparo nada.

Aditiva (dos columnas, una nullable y otra con server_default) — no destructiva.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_event",
        sa.Column(
            "screenshot_sha256_cliente",
            sa.String(length=64),
            nullable=True,
            comment=(
                "SHA-256 hex de la imagen segun el CLIENTE (sensor no confiable). "
                "NULL si el cliente no lo mando o no hubo screenshot."
            ),
        ),
    )
    op.add_column(
        "proctoring_event",
        sa.Column(
            "custodia_cliente",
            sa.String(length=20),
            nullable=False,
            server_default="no_verificable",
            comment=(
                "'coincide' | 'discrepancia' | 'no_verificable'. Compara el hash "
                "del cliente contra el que recalcula el servidor. L2.5: nunca sanciona."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("proctoring_event", "custodia_cliente")
    op.drop_column("proctoring_event", "screenshot_sha256_cliente")
