"""Modelo ORM de la inscripción de un alumno a una comisión (C-69).

Tabla ``inscripcion``: M:N entre ``usuario`` (alumno) y ``comision``. Una fila por
(alumno, comisión); el UNIQUE(usuario_id, comision_id) impide inscribir dos veces.

ON DELETE CASCADE en ambas FKs: borrar el usuario o la comisión elimina la
inscripción (la inscripción no tiene sentido sin sus dos extremos). Tabla aditiva
activeexam (migración 0035): no toca usuario ni comision, solo agrega la tabla puente.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class InscripcionModel(Base):
    """Inscripción de un alumno (usuario) a una comisión (C-69)."""

    __tablename__ = "inscripcion"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
    )
    comision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("comision.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("usuario_id", "comision_id", name="uq_inscripcion_usuario_comision"),
        Index("ix_inscripcion_comision_id", "comision_id"),
        Index("ix_inscripcion_usuario_id", "usuario_id"),
    )
