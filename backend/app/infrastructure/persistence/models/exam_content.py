"""Modelos ORM para el contenido de examen (C-69, secciones 1-2; C-74).

Tablas: examen_contenido, pregunta_examen, opcion_respuesta, categoria_pregunta.
Aditivas — migración slim 0026 (base), 0053-0054 (C-74 categorías).

D3 (regla dura #6): es_correcta vive server-side, NUNCA viaja al cliente.
D11: comision_id es NULLABLE en examen_contenido (FK a comision se agrega en sección 6).
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class CategoriaPreguntaModel(Base):
    """Categoría del banco de preguntas (C-74, migración 0053).

    Estructura autoreferencial: materia → categoría → subcategoría (anidamiento
    arbitrario). ON DELETE CASCADE en ambas FKs: borrar la materia borra sus
    categorías; borrar una categoría borra sus subcategorías en cascada.
    Las preguntas de una categoría borrada quedan con categoria_id=NULL (SET NULL
    en 0054), agrupadas bajo "Sin clasificar".
    """

    __tablename__ = "categoria_pregunta"

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
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    categoria_padre_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categoria_pregunta.id", ondelete="CASCADE"),
        nullable=True,
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    subcategorias: Mapped[list[CategoriaPreguntaModel]] = relationship(
        "CategoriaPreguntaModel",
        back_populates="categoria_padre",
        cascade="all, delete-orphan",
    )
    categoria_padre: Mapped[CategoriaPreguntaModel | None] = relationship(
        "CategoriaPreguntaModel",
        back_populates="subcategorias",
        remote_side="CategoriaPreguntaModel.id",
    )

    __table_args__ = (
        Index("ix_categoria_pregunta_materia_padre", "materia_id", "categoria_padre_id"),
    )


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
    # C-72 §17: estado de la materia. false = "congelada" (sin inscripciones nuevas,
    # sin iniciar exámenes). DEFAULT true por la migración 0041 (aditiva).
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )


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
    # C-70 (modelo enrolment-key de Moodle): código único global con el que el
    # alumno se auto-matricula. Autogenerado ({materia.codigo}-{sufijo}) o provisto
    # por el docente; único entre TODAS las comisiones (no por materia). Se guarda
    # EXACTAMENTE como se tipeó (solo strip externo): unicidad case-sensitive.
    codigo_matriculacion: Mapped[str] = mapped_column(String(80), nullable=False)
    # C-72 §17 (nivel comisión): estado de la comisión. false = "congelada" (sin
    # inscripciones nuevas, sin iniciar exámenes de ESA comisión; la materia sigue
    # activa). DEFAULT true por la migración 0043 (aditiva).
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # C-73 §9 (migración 0049): docente a cargo de la comisión. Es el eslabón que
    # vuelve DERIVABLE quién devuelve la nota (examen.comision_id → comision.docente_id)
    # y contra qué se valida "lo suyo" del rol DOCENTE. NULL = comisión sin docente
    # asignado: no rompe nada, el write-back cae a la cuenta de servicio institucional.
    docente_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("materia_id", "codigo", name="uq_comision_materia_codigo"),
        UniqueConstraint(
            "codigo_matriculacion", name="uq_comision_codigo_matriculacion"
        ),
        Index("ix_comision_materia_id", "materia_id"),
        Index("ix_comision_docente_id", "docente_id"),
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
    # D12 (parte B): destino del write-back de nota POR EXAMEN. NULLABLE — si es
    # NULL, el write-back cae al valor global de config_slim (compat con exámenes
    # importados antes de la migración 0030). cmid = course-module de calificación.
    moodle_courseid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="D12: curso destino en Moodle por examen; NULL = fallback global.",
    )
    moodle_cmid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="D12: course-module de calificación por examen; NULL = fallback global.",
    )
    # C-73: módulo de la actividad destino ('mod_assign' | 'mod_quiz'). NULL = fallback
    # global (config.moodle_component, default 'mod_assign'). Los cuestionarios requieren
    # 'mod_quiz'; las tareas 'mod_assign' (validado E2E en campustest).
    moodle_component: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="C-73: 'mod_assign'|'mod_quiz' del destino por examen; NULL = fallback global.",
    )

    # Configuración del examen POR EXAMEN (migración 0032). ActiveExam la opera;
    # el alumno rinde con estos parámetros (timer/ventana/intentos/shuffle/nota).
    tiempo_limite_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Límite de tiempo en minutos; NULL = sin límite.",
    )
    intentos_permitidos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )
    apertura: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Inicio de la ventana de rendición; NULL = sin apertura.",
    )
    cierre: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fin de la ventana de rendición; NULL = sin cierre.",
    )
    nota_maxima: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="10",
    )
    nota_aprobacion: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="6",
    )
    # Siempre true (migracion 0046): el orden aleatorio por alumno es integridad de
    # la rendicion, no una preferencia del docente. Se conserva la columna para no
    # romper lecturas ni el historial, pero ya no se edita.
    mezclar_preguntas: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    # Tope de preguntas del examen (migracion 0046). None = sin tope.
    limite_preguntas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Visibilidad de resultados (migración 0036, gate estilo Moodle "Review options").
    mostrar_nota: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="al_cerrar",
        comment="Cuándo se muestra la nota: 'al_cerrar' | 'inmediata'.",
    )
    revision_habilitada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Si el alumno puede ver la corrección (solo después del cierre).",
    )
    # C-73: política de calificación cuando el alumno tiene múltiples intentos.
    # 'mas_alta' | 'ultimo' | 'primero' | 'manual'. Default: 'mas_alta'.
    politica_intentos: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="mas_alta",
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
    # Opción B (pool de preguntas): el docente elige cuáles preguntas del pool
    # forman el examen. La rendición y la nota respetan SOLO seleccionada=true.
    # DEFAULT true (migración 0031): exámenes previos quedan con todas seleccionadas.
    seleccionada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Opción B: la pregunta forma parte del examen (pool seleccionable).",
    )
    # C-74 (migración 0054): categoría del banco de preguntas. NULL = Sin clasificar.
    categoria_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categoria_pregunta.id", ondelete="SET NULL"),
        nullable=True,
        comment="C-74: categoría del banco. NULL = Sin clasificar.",
    )
    # C-74 D8 (migración 0054): ID de la pregunta en Moodle para sync idempotente.
    moodle_question_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="C-74 D8: ID en Moodle. Permite re-sync sin duplicar.",
    )

    examen: Mapped[ExamenContenidoModel] = relationship(
        "ExamenContenidoModel", back_populates="preguntas"
    )
    opciones: Mapped[list[OpcionRespuestaModel]] = relationship(
        "OpcionRespuestaModel",
        back_populates="pregunta",
        cascade="all, delete-orphan",
        order_by="OpcionRespuestaModel.orden",
    )
    categoria: Mapped[CategoriaPreguntaModel | None] = relationship(
        "CategoriaPreguntaModel",
        foreign_keys=[categoria_id],
        lazy="select",
    )
    blanks_cloze: Mapped[list["PreguntaClozeBlankModel"]] = relationship(
        "PreguntaClozeBlankModel",
        back_populates="pregunta",
        cascade="all, delete-orphan",
        order_by="PreguntaClozeBlankModel.orden",
    )

    __table_args__ = (
        Index("ix_pregunta_examen_examen_id", "examen_id"),
        Index("ix_pregunta_examen_categoria_id", "categoria_id"),
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


class PreguntaClozeBlankModel(Base):
    """Hueco (blank) de una pregunta cloze (C-74 §5, migración 0055).

    Cada blank corresponde a un {N:TYPE:...} del questiontext de Moodle.
    orden: posición de aparición en el texto (0-indexed).
    tipo: 'multichoice' o 'shortanswer'.
    texto_antes/texto_despues: fragmentos del enunciado que rodean al blank.
    """

    __tablename__ = "pregunta_cloze_blank"

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
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    texto_antes: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_despues: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pregunta: Mapped[PreguntaExamenModel] = relationship(
        "PreguntaExamenModel", back_populates="blanks_cloze"
    )
    opciones_cloze: Mapped[list["OpcionClozeBlancoModel"]] = relationship(
        "OpcionClozeBlancoModel", back_populates="blank", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_pregunta_cloze_blank_pregunta_orden", "pregunta_id", "orden"),
    )


class OpcionClozeBlancoModel(Base):
    """Opción de respuesta de un blank cloze (C-74 §5, migración 0055)."""

    __tablename__ = "opcion_cloze_blank"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    blank_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_cloze_blank.id", ondelete="CASCADE"),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    es_correcta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    peso: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    blank: Mapped[PreguntaClozeBlankModel] = relationship(
        "PreguntaClozeBlankModel", back_populates="opciones_cloze"
    )

    __table_args__ = (
        Index("ix_opcion_cloze_blank_blank_id", "blank_id"),
    )
