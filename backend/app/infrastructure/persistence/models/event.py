"""Modelo ORM del Evento -> HYPERTABLE TimescaleDB (`04` Evento, DD-05, SU-06).

El Evento es series temporales a escala (~5.000 inserts/s). La migracion 002 lo
convierte en hypertable particionada por dia con ``create_hypertable``, define los
indices ``(session_id, timestamp)`` y ``(exam_id, timestamp)``, la politica de
compresion (7d/>7d) y los continuous aggregates base. El modelo aqui describe las
columnas; la DDL de TimescaleDB la lleva la 002 a mano (no la autogenera Alembic).

NOTA hypertable: la PK incluye la columna de particionado ``timestamp`` porque
TimescaleDB exige que toda clave unica contenga la columna de particionado.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class EventModel(Base):
    """Evento de telemetria (`04` Evento). Hypertable particionada por dia (002)."""

    __tablename__ = "evento"
    __table_args__ = (
        # La columna de particionado (``timestamp``) debe formar parte de la PK
        # en una hypertable TimescaleDB.
        PrimaryKeyConstraint("id", "timestamp", name="evento"),
        # Indices obligatorios del modelo (`04` Evento, capability event-hypertable).
        Index("ix_evento_session_ts", "session_id", "timestamp"),
        Index("ix_evento_exam_ts", "exam_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    # ``timestamp`` = timestamp de particionado (== timestamp_backend de ingesta).
    timestamp: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    exam_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    tipo: Mapped[str] = mapped_column(String(64), nullable=False)
    severidad: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp_cliente: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    timestamp_backend: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Firma HMAC-SHA256 con la clave de sesion. La VALIDACION de produccion es
    # C-10; aqui solo la columna (no se valida ni se hardcodea clave alguna).
    firma: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
