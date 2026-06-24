"""Modelos ORM slim de chat bidireccional y pausa autorizada (C-15, tareas 6.x).

Tablas: mensaje_chat, pausa_autorizada. Aditivas — migracion slim 0023.

CADENA DE CUSTODIA / L2.5 (regla dura #6 y #5):
- ``pausa_autorizada`` es el rastro de auditoria PERSISTENTE de la pausa: registra
  quien la aprobo/rechazo (``proctor_actor``) y los timestamps (``solicitada_en``,
  ``resuelta_en``, ``inicio_en``, ``fin_en``). Nunca se borra ni se muta una pausa
  resuelta. La pausa solo CONTEXTUALIZA el score (excluye eventos dentro de la
  ventana del puntaje), NUNCA sanciona ni exime automaticamente.
- En el slim NO hay middleware de audit_log por-request cableado: la tabla
  ``audit_log`` (migracion 0012) existe pero solo la escriben servicios puntuales
  (review, enrollment). Por eso la propia tabla ``pausa_autorizada`` ES el audit
  trail persistente de la resolucion de pausas. Decision documentada aqui.
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


class MensajeChatModel(Base):
    """Mensaje del chat bidireccional proctor<->alumno de una sesion de proctoring."""

    __tablename__ = "mensaje_chat"

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
    autor: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'alumno' | 'proctor'",
    )
    actor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Subject del JWT del proctor; NULL para el alumno (demo sin auth).",
    )
    texto: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )
    creado_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PausaAutorizadaModel(Base):
    """Pausa autorizada de una sesion de proctoring (solicitud del alumno + resolucion del proctor).

    L2.5: la pausa solo CONTEXTUALIZA el score (los eventos dentro de la ventana
    [inicio_en, fin_en or now] se EXCLUYEN del puntaje, no se borran). Esta tabla,
    con ``proctor_actor`` + timestamps, ES el rastro de auditoria persistente.
    """

    __tablename__ = "pausa_autorizada"

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
    motivo: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'solicitada' | 'aprobada' | 'rechazada' | 'finalizada'",
    )
    solicitada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resuelta_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp en que el proctor aprobo/rechazo la pausa.",
    )
    proctor_actor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Subject del JWT del proctor que resolvio la pausa (audit trail).",
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Motivo que el proctor da al RECHAZAR (se muestra al alumno). NULL si se aprobo.",
    )
    inicio_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Inicio de la ventana de pausa aprobada (= resuelta_en al aprobar).",
    )
    fin_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fin de la ventana de pausa (al finalizar). NULL = ventana activa.",
    )
