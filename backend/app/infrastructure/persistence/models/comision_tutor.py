"""Modelos ORM de pertenencia N:M (c-79): tutor↔comisión y coordinador↔materia.

`ComisionTutorModel`: M:N entre usuario (tutor) y comision. Reemplaza el antiguo
`comision.docente_id` (1:1) — un tutor puede estar a cargo de varias comisiones,
una comisión puede tener varios tutores (co-dictado, cobertura de licencias).

`MateriaCoordinadorModel`: M:N entre usuario (coordinador) y materia. El
coordinador deja de tener alcance global (bypass total) — queda acotado a SUS
materias, igual que el tutor queda acotado a SUS comisiones.

Mismo patrón que `InscripcionModel` (usuario↔comision): tabla puente aditiva,
UNIQUE(a, b), índices en ambas direcciones, ON DELETE CASCADE en ambas FKs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class ComisionTutorModel(Base):
    """Tutor a cargo de una comisión (c-79). Una comisión puede tener varios."""

    __tablename__ = "comision_tutor"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    comision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("comision.id", ondelete="CASCADE"),
        nullable=False,
    )
    tutor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("comision_id", "tutor_id", name="uq_comision_tutor_comision_tutor"),
        Index("ix_comision_tutor_comision_id", "comision_id"),
        Index("ix_comision_tutor_tutor_id", "tutor_id"),
    )


class MateriaCoordinadorModel(Base):
    """Coordinador a cargo de una materia (c-79). Una materia puede tener varios."""

    __tablename__ = "materia_coordinador"

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
    coordinador_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "materia_id", "coordinador_id", name="uq_materia_coordinador_materia_coordinador"
        ),
        Index("ix_materia_coordinador_materia_id", "materia_id"),
        Index("ix_materia_coordinador_coordinador_id", "coordinador_id"),
    )


class MateriaProfesorModel(Base):
    """Profesor a cargo de una materia (c-78 E-04). Una materia puede tener varios.

    Espeja exactamente a ``MateriaCoordinadorModel``: el PROFESOR es un rol de
    MATERIA (arma los exámenes y el banco de toda la materia), no de comisión.

    Es una tabla propia y NO se reusa `materia_coordinador` a propósito: las dos
    membresías otorgan cosas distintas — el coordinador emite el VEREDICTO de
    integridad y el profesor no (D11). Colapsarlas en una sola tabla haría que
    asignar a alguien como profesor le diera, de hecho, el poder de anular notas.
    """

    __tablename__ = "materia_profesor"

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
    profesor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "materia_id", "profesor_id", name="uq_materia_profesor_materia_profesor"
        ),
        Index("ix_materia_profesor_materia_id", "materia_id"),
        Index("ix_materia_profesor_profesor_id", "profesor_id"),
    )
