"""Modelos ORM para el contenido de examen (C-69, secciones 1-2; C-74).

Tablas: examen_contenido, pregunta_examen, opcion_respuesta, categoria_pregunta.
Aditivas — migración activeexam 0026 (base), 0053-0054 (C-74 categorías).

D3 (regla dura #6): es_correcta vive server-side, NUNCA viaja al cliente.
D11: comision_id es NULLABLE en examen_contenido (FK a comision se agrega en sección 6).
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from app.infrastructure.persistence.base import Base


class PreguntaBancoModel(Base):
    """Pregunta del banco de preguntas — dueña de su contenido, ligada a materia (0057).

    Las preguntas del banco NO dependen de ningún examen. Los exámenes referencian
    preguntas del banco a través de pregunta_examen.pregunta_banco_id.
    """

    __tablename__ = "pregunta_banco"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    materia_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    categoria_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categoria_pregunta.id", ondelete="SET NULL"),
        nullable=True,
    )
    moodle_question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Nombre de la pregunta en Moodle (`<name><text>` del export XML). Es la única
    # clave estable que trae un XML: `moodle_question_id` solo se llena por el sync
    # vía API. Sin esto, el import resolvía "nueva vs actualizada" comparando el
    # ENUNCIADO, así que corregir el texto de una pregunta y volver a subir el banco
    # la daba de alta OTRA VEZ y dejaba viva la versión vieja — las dos elegibles
    # para el sorteo, y sin forma de borrar ninguna desde la aplicación.
    # NULL en las preguntas cargadas antes de la migración: ahí se sigue cayendo al
    # enunciado, que es como venía funcionando.
    nombre_moodle: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Nombre de la pregunta en Moodle; clave de reimport por XML.",
    )
    # 0058: true cuando el docente movió la pregunta de categoría a mano. Import
    # y sync respetan esa decisión y no vuelven a tocar categoria_id.
    categoria_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    # Baja LÓGICA de la pregunta (nunca borrado físico, mismo patrón que materia,
    # comisión, examen y usuario). NULL = vigente. Una pregunta dada de baja sale
    # del banco, no entra a exámenes nuevos ni al ampliar el pool de uno existente,
    # y se puede reactivar. No se borra porque los exámenes ya rendidos con esa
    # pregunta tienen que poder reconstruirse (regla dura #6, cadena de custodia).
    eliminada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Baja lógica: NULL = vigente, con timestamp = dada de baja.",
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opciones_banco: Mapped[list["OpcionBancoModel"]] = relationship(
        "OpcionBancoModel",
        back_populates="pregunta_banco",
        cascade="all, delete-orphan",
        order_by="OpcionBancoModel.orden",
    )
    blanks_banco: Mapped[list["BlankBancoModel"]] = relationship(
        "BlankBancoModel",
        back_populates="pregunta_banco",
        cascade="all, delete-orphan",
        order_by="BlankBancoModel.orden",
    )

    __table_args__ = (
        Index("ix_pregunta_banco_materia_id", "materia_id"),
        Index("ix_pregunta_banco_categoria_id", "categoria_id"),
        # Partial unique index creado en migración 0057 via raw SQL (postgresql_where
        # no es aceptado por UniqueConstraint en SA — usar Index con postgresql_where)
        Index(
            "uq_pregunta_banco_moodle_question",
            "materia_id", "moodle_question_id",
            unique=True,
            postgresql_where="moodle_question_id IS NOT NULL",
        ),
    )


class OpcionBancoModel(Base):
    """Opción de respuesta para una pregunta del banco (multichoice/truefalse)."""

    __tablename__ = "opcion_banco"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    pregunta_banco_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_banco.id", ondelete="CASCADE"),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    es_correcta: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    pregunta_banco: Mapped[PreguntaBancoModel] = relationship(
        "PreguntaBancoModel", back_populates="opciones_banco"
    )

    __table_args__ = (
        Index("ix_opcion_banco_pregunta_banco_id", "pregunta_banco_id"),
    )


class BlankBancoModel(Base):
    """Blank de una pregunta cloze del banco."""

    __tablename__ = "blank_banco"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    pregunta_banco_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_banco.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    texto_antes: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto_despues: Mapped[str | None] = mapped_column(Text, nullable=True)

    opciones_blank_banco: Mapped[list["OpcionBlankBancoModel"]] = relationship(
        "OpcionBlankBancoModel",
        back_populates="blank_banco",
        cascade="all, delete-orphan",
    )
    pregunta_banco: Mapped[PreguntaBancoModel] = relationship(
        "PreguntaBancoModel", back_populates="blanks_banco"
    )

    __table_args__ = (
        Index("ix_blank_banco_pregunta_banco_id", "pregunta_banco_id"),
    )


class OpcionBlankBancoModel(Base):
    """Opción de un blank cloze del banco."""

    __tablename__ = "opcion_blank_banco"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    blank_banco_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("blank_banco.id", ondelete="CASCADE"),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    es_correcta: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    peso: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    blank_banco: Mapped[BlankBancoModel] = relationship(
        "BlankBancoModel", back_populates="opciones_blank_banco"
    )

    __table_args__ = (
        Index("ix_opcion_blank_banco_blank_banco_id", "blank_banco_id"),
    )


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
    # 0058: identidad estable de la categoría en Moodle. Permite reconocerla en
    # el sync aunque el docente la haya renombrado localmente.
    moodle_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 0058: nombre con el que Moodle nombró la categoría. El XML no trae id, así
    # que el import se ancla acá para no duplicar cuando el docente renombró.
    moodle_nombre_origen: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # c-78 (migración 0093): `docente_id` (1:1, C-73 §9) se dropeó. Quién está a
    # cargo de la comisión vive en `comision_tutor` (N:M, migración 0086), y de ahí
    # sale también con qué credencial se firma la nota que va a Moodle.

    __table_args__ = (
        UniqueConstraint("materia_id", "codigo", name="uq_comision_materia_codigo"),
        UniqueConstraint(
            "codigo_matriculacion", name="uq_comision_codigo_matriculacion"
        ),
        Index("ix_comision_materia_id", "materia_id"),
    )


class ExamenContenidoModel(Base):
    """Examen de contenido importado desde Moodle XML."""

    __tablename__ = "examen_contenido"
    __table_args__ = (
        # Se consulta por lote completo ("las hermanas de este examen"). Parcial
        # porque la enorme mayoría de las filas tiene NULL (examen suelto).
        Index(
            "ix_examen_contenido_lote_replica",
            "lote_replica_id",
            postgresql_where=text("lote_replica_id IS NOT NULL"),
        ),
    )

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
    # c-78 E-06 (migración 0091): crear un examen para varias comisiones se
    # resuelve replicando (D12). Las N réplicas de una misma operación comparten
    # este id; un examen creado suelto lo tiene en NULL. Es identidad compartida,
    # no una FK: ninguna réplica es "la original", nacen todas en la misma
    # transacción.
    lote_replica_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        comment="c-78 E-06: lote de réplicas multi-comisión; NULL = examen suelto.",
    )
    # c-78 E-07 (migración 0092): el examen todavía no se habilitó. Invisible para
    # el alumno; el docente lo puede rendir en modo prueba para verlo entero antes
    # de soltarlo. Default false: todo lo que ya existe está habilitado.
    borrador: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="c-78 E-07: examen en borrador (invisible para el alumno).",
    )
    # c-78 E-07 (migración 0092): cómo se decide qué preguntas ve cada alumno.
    #   'fijo'               → las marcadas con seleccionada=True. Todos rinden lo mismo.
    #   'sorteo_por_intento' → se sortea al arrancar cada intento, según `tramos`,
    #                          contra el POOL COPIADO del examen (nunca el banco vivo).
    # Default 'fijo': los exámenes que ya existen y los importados de XML no cambian.
    modo_preguntas: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="fijo",
        comment="c-78 E-07: 'fijo' | 'sorteo_por_intento'.",
    )
    # D12 (parte B): destino del write-back de nota POR EXAMEN. NULLABLE — si es
    # NULL, el write-back cae al valor global de config_activeexam (compat con exámenes
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
        server_default="100",
    )
    nota_aprobacion: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="60",
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
    # c-78 D9 (migración 0089): el DEFAULT pasó a 'nunca'. La nota no se publica
    # sola al vencer el cierre — la publica una persona cuando terminó de revisar.
    # La transición es de ida: nunca → al_cerrar → inmediata.
    mostrar_nota: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="nunca",
        comment="Cuándo se muestra la nota: 'nunca' | 'al_cerrar' | 'inmediata'.",
    )
    # c-78 D9: quién publicó la nota y cuándo. NULL = todavía no se publicó. Se
    # muestra en el detalle del examen para que el estado no sea ambiguo
    # ("publicadas el {fecha} por {persona}" vs. "ocultas").
    notas_publicadas_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="c-78: cuándo se publicaron las notas. NULL = todavía ocultas.",
    )
    notas_publicadas_por: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="c-78: actor que publicó las notas (email). NULL = sin publicar.",
    )
    revision_habilitada: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Si el alumno puede ver la corrección (solo después del cierre).",
    )
    # c-78 D10 (E-02): si el alumno ve los eventos de proctoring MIENTRAS rinde.
    # Default NO — decisión del dueño. La contra que se acepta: mostrarlos disuade
    # y baja el reclamo posterior de "no sabía"; se compensa con el consentimiento,
    # que ya informa QUE se supervisa aunque no se muestre el detalle evento a evento.
    mostrar_eventos_alumno: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="c-78 D10: el alumno ve sus eventos de proctoring mientras rinde.",
    )
    # C-73: política de calificación cuando el alumno tiene múltiples intentos.
    # 'mas_alta' | 'ultimo' | 'primero' | 'manual'. Default: 'mas_alta'.
    politica_intentos: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="mas_alta",
    )
    # c-78 D1 (migración 0087): baja lógica del examen. NULL = activo; NOT NULL =
    # baja lógica. La fila nunca se borra físicamente: sus sesiones, eventos y
    # evidencia siguen existiendo y son consultables por id (D2, reglas duras #6/#7).
    eliminado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL = activo, NOT NULL = baja lógica.",
    )

    preguntas: Mapped[list[PreguntaExamenModel]] = relationship(
        "PreguntaExamenModel",
        back_populates="examen",
        cascade="all, delete-orphan",
        order_by="PreguntaExamenModel.orden",
    )
    # c-78 E-07: tramos del sorteo. Vacío con modo_preguntas='fijo'.
    tramos: Mapped[list["TramoSorteoExamenModel"]] = relationship(
        "TramoSorteoExamenModel",
        back_populates="examen",
        cascade="all, delete-orphan",
        order_by="TramoSorteoExamenModel.orden",
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
    # 0057: trazabilidad — pregunta del banco de la que proviene esta instancia de examen.
    pregunta_banco_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pregunta_banco.id", ondelete="SET NULL"),
        nullable=True,
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


class TramoSorteoExamenModel(Base):
    """Un tramo del sorteo del examen (c-78 E-07, migración 0092).

    Guarda la CONDICIÓN del sorteo ("10 preguntas de Unidad 1, opción múltiple"),
    no su resultado. El resultado se resuelve por intento, al arrancar cada alumno.

    El sorteo corre contra el POOL COPIADO del examen (`pregunta_examen`), NUNCA
    contra el banco vivo: por eso mover, ocultar o borrar preguntas del banco no
    puede dejar a un alumno sin examen. Es la misma protección que Moodle consigue
    con versionado de preguntas, pero acá sale gratis porque el examen ya copia.

    `categoria_id` es SET NULL a propósito: si la categoría del banco desaparece, el
    tramo sigue siendo válido — las preguntas ya están copiadas y `pregunta_examen`
    conserva de qué categoría vinieron.
    """

    __tablename__ = "tramo_sorteo_examen"

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
    # NULL = "Sin clasificar" (mismo criterio que SorteoCategoriaItem.categoria_id).
    categoria_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("categoria_pregunta.id", ondelete="SET NULL"),
        nullable=True,
        comment="Categoría del tramo. NULL = Sin clasificar.",
    )
    incluir_subcategorias: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # NULL = cualquier tipo. Con lista, solo esos ("multichoice", "cloze"…).
    tipos: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Tipos de pregunta admitidos. NULL = cualquiera.",
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    examen: Mapped[ExamenContenidoModel] = relationship(
        "ExamenContenidoModel", back_populates="tramos"
    )

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_tramo_sorteo_cantidad_positiva"),
        Index("ix_tramo_sorteo_examen_examen_id", "examen_id"),
    )


class PreguntaSesionModel(Base):
    """Las preguntas que le tocaron a UN intento (c-78 E-07, migración 0092).

    Con `modo_preguntas='sorteo_por_intento'` cada alumno recibe un set distinto, así
    que "qué preguntas tiene este examen" deja de ser un dato del examen y pasa a ser
    un dato del intento. La corrección, la revisión y el cálculo de nota leen de acá.

    Se persiste al arrancar el intento y no se vuelve a tocar: es lo que permite
    reconstruir exactamente qué rindió cada alumno (regla dura #6, cadena de custodia).

    ON DELETE CASCADE desde la sesión. Desde `pregunta_examen` también: si la pregunta
    se va, la fila no tiene sentido — pero el pool del examen no se borra nunca, así
    que en la práctica no pasa.
    """

    __tablename__ = "pregunta_sesion"

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
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id", "pregunta_id", name="uq_pregunta_sesion_sesion_pregunta"
        ),
        Index("ix_pregunta_sesion_session_id", "session_id"),
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
