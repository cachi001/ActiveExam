"""0043 - audit_log: modulo + entidad + tipo_accion + entidad_id (C-73).

Revision ID: 0043
Revises: 0042 (branch slim)
Create Date: 2026-07-24

RAMA: slim
  down_revision = "0042"

PROPOSITO:
  Alinea audit_log con el modelo ActividadAuditoria del sistema de referencia.
  Agrega cuatro columnas que permiten filtrado real por módulo, entidad y tipo
  de acción desde la pantalla de Auditoría, sin romper la cadena de hash:

  - `modulo`      VARCHAR(64) NULL  — módulo de dominio (ModuloAuditoria enum)
  - `entidad`     VARCHAR(64) NULL  — tipo de entidad afectada (EntidadAuditoria enum)
  - `entidad_id`  VARCHAR(255) NULL — UUID de la entidad afectada (navegación al detalle)
  - `tipo_accion` VARCHAR(32) NULL  — acción simplificada (CREAR/EDITAR/ELIMINAR/CAMBIO_ESTADO)

  El campo `accion` dot-notation existente (user.create, materia.delete, etc.)
  SE MANTIENE intacto como campo de detalle/descripción. Las nuevas columnas son
  metadata de clasificación independiente del hash de la cadena de custodia.

  Sin backfill destructivo: filas históricas quedan con NULL en las 4 columnas.
  Llamadas futuras a registrar() deben proveer los cuatro campos.

ROLLBACK:
  alembic downgrade slim@0042 -> DROP los 4 índices + columnas.
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("modulo", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("entidad", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("entidad_id", sa.String(255), nullable=True))
    op.add_column("audit_log", sa.Column("tipo_accion", sa.String(32), nullable=True))
    op.create_index(
        "ix_audit_log_modulo",
        "audit_log",
        ["modulo"],
        postgresql_where=sa.text("modulo IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_log_entidad",
        "audit_log",
        ["entidad", "entidad_id"],
        postgresql_where=sa.text("entidad IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_log_tipo_accion",
        "audit_log",
        ["tipo_accion"],
        postgresql_where=sa.text("tipo_accion IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_tipo_accion", table_name="audit_log")
    op.drop_index("ix_audit_log_entidad", table_name="audit_log")
    op.drop_index("ix_audit_log_modulo", table_name="audit_log")
    op.drop_column("audit_log", "tipo_accion")
    op.drop_column("audit_log", "entidad_id")
    op.drop_column("audit_log", "entidad")
    op.drop_column("audit_log", "modulo")
