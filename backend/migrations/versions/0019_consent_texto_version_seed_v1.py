"""019 - seed v1 en consent_texto_version (slim + full convergente).

Revision ID: 0019
Revises: 0018 (rama slim) y 0017 (rama full) — MERGE POINT
Create Date: 2026-06-16

RAMA: converge slim (0018) + full (0017)
  down_revision = ("0018", "0017")
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Siembra la fila v1 en ``consent_texto_version`` con los cinco bloques
  informativos canonicos derivados del texto en
  ``app/domain/consent_flow/text_catalog.py`` (_V1).

  El hash es el SHA-256 del JSON canonico: version + bloques (sorted keys, sin
  whitespace, ensure_ascii=False). Esta funcion DEBE coincidir con
  ``compute_hash`` en ``app/application/consent/text_version_service.py``.

  INSERT idempotente (ON CONFLICT DO NOTHING): seguro en re-runs.

  En la rama FULL, la tabla fue creada por 0018 (que converge desde 0016, slim).
  Para la rama full hay que asegurarse de que la tabla exista antes — la migracion
  0020_consent_texto_version_full_table.py crea la tabla en full si no existe aun.
  Sin embargo, como este seed converge desde 0018 (que ya creó la tabla), el merge
  point garantiza la dependencia.

ROLLBACK:
  DELETE de la fila v1 (paso 2 destructivo). Se lista abajo en downgrade().

VERIFICACION:
  alembic upgrade head -> siembra v1. Espera 1 fila version='v1' en consent_texto_version.
"""

from __future__ import annotations

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Texto canonico v1 — espeja _V1 de text_catalog.py
# ---------------------------------------------------------------------------

_BLOQUES_V1 = [
    {
        "titulo": "¿Qué datos recolectamos?",
        "cuerpo": (
            "Se recolectan datos biometricos faciales (un embedding derivado de tu "
            "rostro), senales de tu camara y pantalla durante el examen, y metadatos "
            "de la sesion. El embedding se trata como dato sensible (Ley 25.326)."
        ),
    },
    {
        "titulo": "¿Cómo los recolectamos?",
        "cuerpo": (
            "Mediante tu camara y la captura de pantalla, con analisis en tu navegador; "
            "el servidor re-procesa y firma la evidencia (cadena de custodia)."
        ),
    },
    {
        "titulo": "¿Dónde se guardan?",
        "cuerpo": (
            "En infraestructura self-hosted de la institucion (soberania de datos), "
            "con la evidencia cifrada at-rest en almacenamiento WORM."
        ),
    },
    {
        "titulo": "¿Cuánto tiempo los conservamos?",
        "cuerpo": (
            "Segun la politica de retencion del examen; el embedding se elimina al "
            "egreso salvo que un caso disciplinario en curso difiera la eliminacion."
        ),
    },
    {
        "titulo": "Tus derechos",
        "cuerpo": (
            "Tenes derecho de acceso, rectificacion, supresion y a impugnar decisiones; "
            "la decision disciplinaria es siempre humana, el sistema no sanciona solo."
        ),
    },
]


def _compute_hash(version: str, bloques: list[dict]) -> str:
    canonical = json.dumps(
        {
            "version": version,
            "bloques": [{"titulo": b["titulo"], "cuerpo": b["cuerpo"]} for b in bloques],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    hash_v1 = _compute_hash("v1", _BLOQUES_V1)
    # ensure_ascii=True avoids UTF-8 encoding issues when embedding in SQL literals.
    # The JSON will use \\uXXXX escapes for non-ASCII chars; Postgres::jsonb decodes them.
    bloques_json = json.dumps(_BLOQUES_V1, ensure_ascii=True)
    bloques_escaped = bloques_json.replace("'", "''")

    op.execute(
        sa.text(
            f"INSERT INTO consent_texto_version (version, bloques, hash_texto, created_by) "
            f"VALUES ('v1', '{bloques_escaped}'::jsonb, '{hash_v1}', 'seed-migration-0019') "
            f"ON CONFLICT (version) DO NOTHING"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM consent_texto_version WHERE version = 'v1'")
    )
