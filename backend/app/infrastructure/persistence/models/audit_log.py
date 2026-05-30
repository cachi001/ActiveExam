"""Modelo ORM del Audit log APPEND-ONLY (cadena de custodia, DD-07, `04`).

La tabla lleva la columna ``hash_prev`` (encadenamiento de hash) y, en la
migracion 002, un TRIGGER ``BEFORE UPDATE OR DELETE`` que aborta la operacion con
``RAISE EXCEPTION`` -> la inmutabilidad vive en el MOTOR, no en la aplicacion. El
modelo aqui solo describe las columnas; la garantia de inmutabilidad es DDL de la
002.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class AuditLogModel(Base):
    """Entrada del audit log (`04` Audit log). Append-only por trigger (002)."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[str] = mapped_column(server_default=func.now(), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    accion: Mapped[str] = mapped_column(String(255), nullable=False)
    evidencia_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("evidencia.id"), nullable=True
    )
    proposito: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Encadenamiento de hash: hash de la entrada anterior (64 hex de SHA-256).
    hash_prev: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hash de ESTA entrada, materializado al insertar para que la cadena sea
    # verificable sin recomputar (validacion diaria, `04`).
    hash_self: Mapped[str] = mapped_column(String(64), nullable=False)
