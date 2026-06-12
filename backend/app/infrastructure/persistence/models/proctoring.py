"""Modelos ORM del modulo slim de proctoring (SQLAlchemy).

Tablas: proctoring_session, proctoring_event, proctoring_biometria.
Migración: 0005_proctoring_slim.py (branch 'slim', depends_on=None).

PRODUCCION:
- screenshot_b64: dato sensible (Ley 25.326). Mover a MinIO/S3 WORM con cifrado
  at-rest y politica de retencion automatica (90 dias o fin de hold disciplinario).
- embedding: dato sensible (Ley 25.326); cifrar con KMS antes de persistir; purgar
  al egreso del estudiante (DD-13, DSR).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class ProctoringSessionModel(Base):
    """Sesion de proctoring slim. Aditiva — no reemplaza SesionModel de produccion."""

    __tablename__ = "proctoring_session"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="UUID generado por Postgres (gen_random_uuid)",
    )
    modo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'test' o 'examen'",
    )
    exam_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="ID del examen (referencia externa, no FK a tabla de produccion)",
    )
    etiqueta: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Etiqueta libre para identificar la sesion",
    )
    creada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finalizada_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # c-16: decision terminal del revisor (slim, migration 0013). NULLABLE
    # — None = sin revisar todavia. Una vez seteada, es INMUTABLE (RN-RV-07).
    decision: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="'pendiente' | 'descartada' | 'escalada' | 'derivada' | NULL"
    )
    decision_actor: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Subject del JWT del revisor al momento de decidir"
    )
    decision_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decision_observaciones: Mapped[str | None] = mapped_column(
        String(1024), nullable=True,
    )

    eventos: Mapped[list[ProctoringEventModel]] = relationship(
        back_populates="sesion",
        cascade="all, delete-orphan",
        order_by="ProctoringEventModel.ts_backend",
    )
    biometria: Mapped[ProctoringBiometriaModel | None] = relationship(
        back_populates="sesion",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ProctoringEventModel(Base):
    """Evento de deteccion con screenshot e informacion de re-inferencia server-side.

    PRODUCCION:
    - screenshot_b64: dato sensible (Ley 25.326). Almacenado en texto plano solo
      en demo. Para produccion: MinIO/S3 WORM + cifrado at-rest + retencion 90d.
    - screenshot_sha256: integridad liviana (SHA-256 del contenido base64).
      PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada).
    - face_count_servidor / veredicto_reinferencia: producidos por MediaPipe server-side
      (mismo motor que el cliente, D8). L2.5: el veredicto NO sanciona; solo enriquece
      la evidencia que ve el revisor humano.
    """

    __tablename__ = "proctoring_event"

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
    tipo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ej: 'FACE_ABSENT', 'MULTIPLE_FACES', 'GAZE_DEVIATION'",
    )
    severidad: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'bajo' | 'medio' | 'alto' | 'critico'",
    )
    ts_cliente: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp reportado por el cliente (no confiable, sensor no verificado)",
    )
    ts_backend: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp del servidor (autoritativo)",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Datos adicionales del evento (libre)",
    )
    screenshot_b64: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Screenshot en base64. "
            "PRODUCCION: dato sensible Ley 25.326 — mover a MinIO/S3 WORM con "
            "cifrado at-rest y politica de retencion automatica."
        ),
    )
    # PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)
    screenshot_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hex del screenshot (integridad liviana, D9). NULL si no hay screenshot.",
    )
    face_count_cliente: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Conteo de rostros reportado por el cliente (campo explicito del body)",
    )
    face_count_servidor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Conteo de rostros re-detectado server-side con MediaPipe (mismo motor "
            "que el cliente, D8). NULL si veredicto es 'no_evaluado'."
        ),
    )
    veredicto_reinferencia: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="no_evaluado",
        comment="'coincide' | 'discrepancia' | 'no_evaluado'. L2.5: nunca sanciona.",
    )

    sesion: Mapped[ProctoringSessionModel] = relationship(back_populates="eventos")


class ProctoringBiometriaModel(Base):
    """Resultado biometrico de la sesion de proctoring slim.

    PRODUCCION:
    - embedding: dato sensible (Ley 25.326, ISO 30107-3). En demo se persiste en
      texto plano solo si el cliente lo envia (campo nullable). Para produccion:
      cifrar con KMS antes de persistir; purgar al egreso del estudiante (DD-13, DSR).
    """

    __tablename__ = "proctoring_biometria"

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
    liveness_ok: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True si el liveness challenge paso",
    )
    retos_resueltos: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Lista de retos de liveness resueltos",
    )
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Embedding facial. PRODUCCION: dato sensible (Ley 25.326); "
            "cifrar con KMS antes de persistir; purgar al egreso (DD-13, DSR)."
        ),
    )
    resultado: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'verificado' | 'rechazado' | 'pendiente'",
    )
    registrada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sesion: Mapped[ProctoringSessionModel] = relationship(back_populates="biometria")
