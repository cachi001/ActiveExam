"""Modelos ORM para el write-back de nota a Moodle (C-69 sección 7, D10).

Tablas:
- respuesta_alumno: respuestas del alumno por sesión/pregunta (para calcular nota server-side)
- moodle_writeback_estado: estado del envío de nota (idempotencia + reintentos)
- moodle_writeback_audit: audit log de cada intento (sin token)

Migración aditiva slim: 0029_c69_moodle_writeback_slim.py
"""

from __future__ import annotations

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class RespuestaAlumnoModel(Base):
    """Respuesta del alumno por pregunta en una sesión de examen.

    UNIQUE(session_id, pregunta_id): una respuesta por pregunta por sesión.
    ON DELETE CASCADE desde proctoring_session: borrar la sesión borra sus respuestas.
    """

    __tablename__ = "respuesta_alumno"

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
    pregunta_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
        nullable=False,
    )
    opcion_elegida_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("opcion_respuesta.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("session_id", "pregunta_id", name="uq_respuesta_alumno_sesion_pregunta"),
        Index("ix_respuesta_alumno_session_id", "session_id"),
    )


class MoodleWritebackEstadoModel(Base):
    """Estado del envío de nota a Moodle por sesión (D10: idempotencia + reintentos).

    UNIQUE(session_id): una entrada por sesión — la idempotencia se garantiza acá.
    estado: 'pendiente' | 'enviado' | 'fallido'
    El token NUNCA se almacena en esta tabla.
    """

    __tablename__ = "moodle_writeback_estado"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctoring_session.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    alumno_idnumber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alumno_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    nota: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pendiente",
        comment="pendiente | enviado | fallido",
    )
    intento: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    moodle_courseid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_cmid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # C-73: 'mod_assign'|'mod_quiz' del destino; se persiste para el envío manual del
    # admin (ejecutar_writeback lo pasa a write_grade). NULL = fallback global.
    moodle_component: Mapped[str | None] = mapped_column(String(32), nullable=True)
    moodle_userid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MoodleWritebackAuditModel(Base):
    """Audit log de cada intento de envío de nota a Moodle (D10, sin token).

    Append-only — no se actualiza, solo se inserta.
    El token NUNCA aparece en esta tabla ni en logs.
    """

    __tablename__ = "moodle_writeback_audit"

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
    alumno_idnumber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nota: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    moodle_courseid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_cmid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_userid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resultado: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="'ok' o 'error'",
    )
    error_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_moodle_writeback_audit_session_id", "session_id"),
    )
