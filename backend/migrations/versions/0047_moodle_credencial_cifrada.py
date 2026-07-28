"""0047 - credencial de Moodle en DB, con el token CIFRADO.

Revision ID: 0047
Revises: 0046 (branch slim)
Create Date: 2026-07-28

RAMA: slim

PROPOSITO:
  Mueve la credencial de servicio de Moodle (base_url + token de Web Services +
  destino global) de variables de entorno a la base, con el token CIFRADO at-rest
  (Fernet, misma clave que embeddings y evidencia).

  POR QUE:
  - El token vivia en `.env` / variables de Railway: cambiarlo exigia un deploy y
    quedaba en manos de quien tuviera acceso a la infraestructura, no del admin
    del sistema. La institucion tiene UNA cuenta de servicio; rotarla es una tarea
    de administracion, no de infraestructura.
  - Es un secreto: en claro en la base seria un dato exfiltrable que permite
    escribir notas en el campus. Se guarda cifrado (nunca en claro, nunca en logs,
    nunca en la respuesta de la API).

  Tabla singleton (una sola fila, id=1): la credencial es institucional, NO por
  docente (decision del owner). Ver `MoodleCredencialModel`.

  `token_cifrado` es NULLABLE: la fila puede existir con el destino configurado y
  sin token todavia (estado "Moodle a medio configurar"), que es justamente lo que
  la pantalla de configuracion tiene que poder mostrar.

SIN BACKFILL:
  No se copia el token desde el entorno: hacerlo lo escribiria en la base desde un
  contexto de migracion, sin auditoria ni actor. El resolver cae al valor de
  entorno mientras la tabla este vacia, asi que nada se rompe; el admin carga el
  token desde la UI cuando quiera y a partir de ahi manda la base.
"""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moodle_credencial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_url", sa.String(500), nullable=False, server_default=""),
        # Token de Web Services CIFRADO (Fernet). NULL = todavia no cargado.
        sa.Column("token_cifrado", sa.Text(), nullable=True),
        # Ultimos 4 caracteres del token en claro, solo para que el admin reconozca
        # cual cargo. No permite reconstruirlo.
        sa.Column("token_pista", sa.String(8), nullable=True),
        sa.Column("courseid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cmid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "component", sa.String(50), nullable=False, server_default="mod_assign"
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actualizado_por", sa.String(255), nullable=True),
        # Singleton: una sola fila posible.
        sa.CheckConstraint("id = 1", name="ck_moodle_credencial_singleton"),
    )


def downgrade() -> None:
    op.drop_table("moodle_credencial")
