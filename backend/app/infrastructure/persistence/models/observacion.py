"""Modelo ORM slim de observaciones del proctor (C-15, tarea 3.2).

Tabla: observacion_proctor. Aditiva — migracion slim 0025.

INSUMO DE C-16 (revision humana): durante la supervision, el proctor registra
observaciones libres sobre una sesion. Son MULTIPLES por sesion (a diferencia del
campo terminal ``decision_observaciones`` del revisor, que es unico e inmutable).
La cola/revision de C-16 las consume como contexto.

CADENA DE CUSTODIA / L2.5 (regla dura #6 y #5):
- Cada observacion registra quien la escribio (``proctor_actor``) y cuando
  (``creada_en``). Nunca se borra ni se muta — append-only, audit trail persistente.
- Una observacion NO sanciona ni exime: es insumo para la decision HUMANA de C-16.
"""

from __future__ import annotations

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class ObservacionProctorModel(Base):
    """Observacion libre del proctor sobre una sesion (insumo de la revision C-16)."""

    __tablename__ = "observacion_proctor"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctoring_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    proctor_actor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Subject del JWT del proctor que escribio la observacion (audit trail).",
    )
    texto: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )
    creada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
