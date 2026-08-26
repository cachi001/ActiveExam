"""Captura de proctoring en BINARIO: proctoring_event.screenshot_bin.

Revision ID: 0097
Revises: 0096
Create Date: 2026-08-25

PROPOSITO (c-78, task 16.4):
  Medido contra Postgres real con `pg_column_size`, una captura de 85 KB ocupaba
  **151.224 bytes** en `screenshot_b64`. Es una doble expansion base64:

      imagen 85.000 -> data URL base64 113.359 (133%) -> token Fernet 151.224 (178%)

  Fernet devuelve su token en base64, asi que el cifrado vuelve a inflar lo que ya
  venia inflado. Y TOAST no lo salva: lo cifrado es incompresible y Postgres lo
  guarda tal cual (comprobado, la fila comprimida pesa lo mismo).

  Guardando el token Fernet CRUDO sobre los BYTES de la imagen, la misma captura
  ocupa **85.065 bytes**: 44% menos. Un examen de 100 alumnos pasa de 577 MB a
  325 MB en una base de 1024 MB.

DOS COLUMNAS:
  - `screenshot_bin` (BYTEA): la captura cifrada at-rest, en binario.
  - `screenshot_prefijo`: el prefijo del data URL ('data:image/jpeg;base64') tal
    CUAL vino. No es cosmetico: `screenshot_sha256` se calcula sobre el string
    base64 completo y `verify-chain` lo recalcula para peritar la evidencia, asi
    que la reconstruccion tiene que ser byte a byte. Guardar un mime normalizado
    en vez del prefijo original rompería ese hash si el cliente cambiara de formato.

NINGUN HASH CAMBIA. Ni `screenshot_sha256` (el string reconstruido es identico al
  original) ni `screenshot_sha256_cliente` (hashea los bytes de la imagen, que son
  los mismos vaya en base64 o en binario). Eso esta fijado por tests de round-trip
  exacto en `tests/test_c78_captura_binaria.py`.

DOS PASOS (regla de migraciones destructivas del proyecto): esta migracion SOLO
  AGREGA. `screenshot_b64` se conserva con todo el historico y el camino de lectura
  mira primero el binario y cae al legacy si esta vacio. El DROP de la columna vieja
  va en una migracion posterior, una vez backfilleado el historico.

Aditiva (dos columnas nullable) — no destructiva.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_event",
        sa.Column(
            "screenshot_bin",
            sa.LargeBinary(),
            nullable=True,
            comment=(
                "Screenshot CIFRADO at-rest en binario (dato sensible Ley 25.326). "
                "Token Fernet sin su base64 externo."
            ),
        ),
    )
    op.add_column(
        "proctoring_event",
        sa.Column(
            "screenshot_prefijo",
            sa.String(length=128),
            nullable=True,
            comment=(
                "Prefijo del data URL original, tal cual vino, para que la "
                "reconstruccion sea byte a byte y screenshot_sha256 siga verificando."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("proctoring_event", "screenshot_prefijo")
    op.drop_column("proctoring_event", "screenshot_bin")
