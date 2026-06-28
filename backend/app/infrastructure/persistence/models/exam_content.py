"""Modelos ORM para el contenido de examen (C-69, secciones 1-2).

Tablas: examen_contenido, pregunta_examen, opcion_respuesta.
Aditivas — migración slim 0026.

D3 (regla dura #6): es_correcta vive server-side, NUNCA viaja al cliente.
D11: comision_id es NULLABLE en examen_contenido (FK a comision se agrega en sección 6).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class MateriaModel(Base):
    """Materia académica (C-69 sección 6, D11). codigo único."""

    __tablename__ = "materia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    codigo: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)


class ComisionModel(Base):
    """Comisión de una materia (C-69 sección 6, D11).

    FK obligatoria a materia (ON DELETE CASCADE: borrar la materia borra sus
    comisiones). Único (materia_id, codigo). período/anio opcionales.
    """

    __tablename__ = "comision"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    materia_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    periodo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("materia_id", "codigo", name="uq_comision_materia_codigo"),
        Index("ix_comision_materia_id", "materia_id"),
    )


class ExamenContenidoModel(Base):
    """Examen de contenido importado desde Moodle XML."""

    __tablename__ = "examen_contenido"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    comision_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        comment="FK a comision se agrega en sección 6 (D11: nullable).",
    )

    preguntas: Mapped[list[PreguntaExamenModel]] = relationship(
        "PreguntaExamenModel",
        back_populates="examen",
        cascade="all, delete-orphan",
        order_by="PreguntaExamenModel.orden",
    )


class PreguntaExamenModel(Base):
    """Pregunta de un examen de contenido."""

    __tablename__ = "pregunta_examen"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    examen_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("examen_contenido.id", ondelete="CASCADE"),
        nullable=False,
    )
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    examen: Mapped[ExamenContenidoModel] = relationship(
        "ExamenContenidoModel", back_populates="preguntas"
    )
    opciones: Mapped[list[OpcionRespuestaModel]] = relationship(
        "OpcionRespuestaModel",
        back_populates="pregunta",
        cascade="all, delete-orphan",
        order_by="OpcionRespuestaModel.orden",
    )

    __table_args__ = (
        Index("ix_pregunta_examen_examen_id", "examen_id"),
    )


class OpcionRespuestaModel(Base):
    """Opción de respuesta de una pregunta.

    D3: es_correcta vive server-side, NUNCA viaja al cliente.
    """

    __tablename__ = "opcion_respuesta"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    pregunta_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_examen.id", ondelete="CASCADE"),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    es_correcta: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="D3: solo server-side, NUNCA al cliente.",
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    pregunta: Mapped[PreguntaExamenModel] = relationship(
        "PreguntaExamenModel", back_populates="opciones"
    )

    __table_args__ = (
        Index("ix_opcion_respuesta_pregunta_id", "pregunta_id"),
    )
