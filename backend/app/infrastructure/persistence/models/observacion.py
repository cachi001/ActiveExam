"""Modelo ORM activeexam de observaciones del tutor (C-15, tarea 3.2; renombrado C-76).

Tabla: observacion_tutor (renombrada de observacion_proctor por c-76 — el rol
PROCTOR fue eliminado del dominio, ver migracion 0072_c76_rename_observacion_proctor_a_tutor).
Aditiva originalmente — migracion activeexam 0025.

INSUMO DE C-16 (revision humana): durante la supervision, el tutor registra
observaciones libres sobre una sesion. Son MULTIPLES por sesion (a diferencia del
campo terminal ``decision_observaciones`` del revisor, que es unico e inmutable).
La cola/revision de C-16 las consume como contexto.

CADENA DE CUSTODIA / L2.5 (regla dura #6 y #5):
- Cada observacion registra quien la escribio (``tutor_actor``) y cuando
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


class ObservacionTutorModel(Base):
    """Observacion libre del tutor sobre una sesion (insumo de la revision C-16)."""

    __tablename__ = "observacion_tutor"

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
    tutor_actor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Subject del JWT del tutor que escribio la observacion (audit trail).",
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
