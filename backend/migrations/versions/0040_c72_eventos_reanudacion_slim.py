"""0040 - seed recarga_pagina y reanudacion_tardia en evento_score_config (rama slim).

Revision ID: 0040
Revises: 0039 (branch slim)
Create Date: 2026-07-17

RAMA: slim
  down_revision = "0039"
  branch_labels = None
  depends_on    = None

PROPOSITO (C-72 seccion 5, H-4):
  Agrega los dos tipos de evento de REAPERTURA de la rendicion, emitidos
  server-side al reanudar una sesion activa (session_service.crear_o_reanudar_sesion):
    - recarga_pagina      severidad baja,  peso 2  -> recarga rapida, benigna.
    - reanudacion_tardia  severidad media, peso 11 -> ausencia larga, merece mirada.

  Pesos CONSERVADORES a proposito, y dentro del rango por severidad que impone el
  CHECK de la migracion 0021 (baja [1-10], media [11-30]): peso 11 es el MINIMO de
  'media'. Por si solos NO empujan una sesion sobre el umbral de encolado a revision
  (RN-SC). Son SENAL para el revisor humano, nunca sancion automatica (regla dura
  #5). Ajustables por admin sin redeploy.

  INSERT idempotente (ON CONFLICT DO NOTHING): seguro en re-runs.

ROLLBACK:
  alembic downgrade slim@0039 -> DELETE de esas dos filas (paso 2 destructivo).

VERIFICACION:
  alembic upgrade slim@head -> aplica hasta 0040.
  Espera recarga_pagina (baja, 2) y reanudacion_tardia (media, 10), activo=true.
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

_SEEDS = [
    (
        "recarga_pagina",
        "baja",
        2,
        "El estudiante recargo la pagina y volvio enseguida (reapertura benigna).",
    ),
    (
        "reanudacion_tardia",
        "media",
        11,
        "El estudiante reanudo la rendicion tras una ausencia prolongada.",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for tipo, severidad, peso, descripcion in _SEEDS:
        conn.execute(
            sa.text(
                "INSERT INTO evento_score_config "
                "(tipo_evento, severidad, peso, descripcion, activo) "
                "VALUES (:tipo, :sev, :peso, :desc, true) "
                "ON CONFLICT (tipo_evento) DO NOTHING"
            ),
            {"tipo": tipo, "sev": severidad, "peso": peso, "desc": descripcion},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM evento_score_config "
            "WHERE tipo_evento IN ('recarga_pagina', 'reanudacion_tardia')"
        )
    )
