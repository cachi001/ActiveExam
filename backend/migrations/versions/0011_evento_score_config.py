"""011 - tabla de configuracion de score por tipo de evento (rama slim).

Revision ID: 0011
Revises: 0010 (branch slim)
Create Date: 2026-06-08

RAMA: slim
  down_revision = "0010"
  branch_labels = None
  depends_on    = None

PROPOSITO:
  Permite a admin_sistema configurar el peso (0-100) que aporta cada tipo de evento
  al score acumulado del examen, sin redeploy. Hoy los pesos viven hardcoded en
  frontend/src/proctoring/riskWeights.ts (PESO_SCORE por severidad). Esta tabla
  abre la puerta a granularidad por tipo (no solo por severidad) y a ajuste en
  caliente desde una pantalla admin.

  Diseno:
    - tipo_evento TEXT PK -- coincide con TipoEvento del catalogo (rostro_ausente,
      multiples_rostros, mirada_desviada_sostenida, perdida_de_foco, cambio_pestana,
      monitor_adicional, salida_pantalla_completa, copiar_pegar).
    - severidad TEXT NOT NULL CHECK -- baseline | baja | media | alta | critica.
    - peso INTEGER NOT NULL CHECK (peso >= 0 AND peso <= 100) -- contribucion al score.
    - descripcion TEXT -- texto para la UI admin (opcional).
    - activo BOOLEAN NOT NULL DEFAULT TRUE -- desactivar un tipo de evento sin borrarlo.
    - created_at / updated_at TIMESTAMPTZ.

  Seed inicial: 8 tipos del catalogo (suspiciousActivityCatalog) con pesos default
  por severidad (baja=5, media=20, alta=50, critica=100) — mismos numeros que
  riskWeights.ts para que el comportamiento NO cambie hasta que admin lo ajuste.

ROLLBACK:
  alembic downgrade slim@0010  -> dropea la tabla. Es destructivo si admin ya edito
  pesos, pero recuperable corriendo upgrade de nuevo (re-seed con defaults).

VERIFICACION:
  alembic upgrade slim@head   -> aplica 0010 -> 0011 contra postgres:16-alpine.
  Espera 8 filas en evento_score_config tras el upgrade.
"""

import sqlalchemy as sa

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TIMESTAMPTZ = sa.TIMESTAMP(timezone=True)

_SEEDS: list[tuple[str, str, int, str]] = [
    ("rostro_ausente", "media", 20, "No se detecto rostro en el encuadre por mas de 3 segundos."),
    ("multiples_rostros", "alta", 50, "Se detectaron multiples rostros simultaneos en camara."),
    ("mirada_desviada_sostenida", "media", 20, "Patron de mirada sostenido hacia un punto fijo fuera de pantalla."),
    ("perdida_de_foco", "baja", 5, "La ventana del examen perdio el foco del sistema operativo."),
    ("cambio_pestana", "media", 20, "El estudiante cambio o abrio otra pestana durante el examen."),
    ("monitor_adicional", "alta", 50, "Se detecto un segundo monitor conectado al equipo."),
    ("salida_pantalla_completa", "media", 20, "El estudiante salio del modo de pantalla completa."),
    ("copiar_pegar", "media", 20, "Se detecto una accion de copiar o pegar (sin capturar contenido)."),
]


def upgrade() -> None:
    op.create_table(
        "evento_score_config",
        sa.Column("tipo_evento", sa.Text, primary_key=True, nullable=False),
        sa.Column("severidad", sa.Text, nullable=False),
        sa.Column("peso", sa.Integer, nullable=False),
        sa.Column("descripcion", sa.Text, nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMPTZ,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "severidad IN ('baseline', 'baja', 'media', 'alta', 'critica')",
            name="ck_evento_score_config_severidad_valida",
        ),
        sa.CheckConstraint(
            "peso >= 0 AND peso <= 100",
            name="ck_evento_score_config_peso_rango",
        ),
    )

    # Trigger para auto-actualizar updated_at en cada UPDATE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_evento_score_config_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_evento_score_config_updated_at
          BEFORE UPDATE ON evento_score_config
          FOR EACH ROW
          EXECUTE FUNCTION set_evento_score_config_updated_at();
        """
    )

    # Seed los 8 tipos del catalogo con sus defaults (mismos pesos que riskWeights.ts).
    conn = op.get_bind()
    for tipo, severidad, peso, descripcion in _SEEDS:
        conn.execute(
            sa.text(
                "INSERT INTO evento_score_config (tipo_evento, severidad, peso, descripcion) "
                "VALUES (:tipo, :sev, :peso, :desc) "
                "ON CONFLICT (tipo_evento) DO NOTHING"
            ),
            {"tipo": tipo, "sev": severidad, "peso": peso, "desc": descripcion},
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evento_score_config_updated_at ON evento_score_config")
    op.execute("DROP FUNCTION IF EXISTS set_evento_score_config_updated_at()")
    op.drop_table("evento_score_config")
