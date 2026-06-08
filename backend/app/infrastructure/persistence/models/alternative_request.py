"""Modelo ORM de la solicitud de via alternativa (C-63, D-01).

Tabla ``solicitudes_via_alternativa`` — estado mutable del ciclo de vida de
la solicitud de via alternativa del alumno. Esta tabla NO es el audit log
(que es append-only); su proposito es llevar el estado mutable
(pendiente_proctor -> habilitado_por_proctor).

Usada TANTO en el modulo slim (Railway) como en el full (si se implementa).
El ENUM ``estado_via_alternativa`` lo crea la migracion 0010 (create_type=False
aqui para que el DDL lo controle la migracion).
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class EstadoViaAlternativaDB(str, enum.Enum):
    """Replica del enum de dominio para el mapeo ORM.

    Los valores deben coincidir con ``EstadoViaAlternativa`` de la entidad de
    dominio. Se mantiene aqui en infraestructura para no acoplar el ORM al
    dominio.
    """

    PENDIENTE_PROCTOR = "pendiente_proctor"
    HABILITADO_POR_PROCTOR = "habilitado_por_proctor"


# ``create_type=False``: el CREATE TYPE lo hace la migracion 0010.
estado_via_alternativa_enum = SAEnum(
    EstadoViaAlternativaDB,
    name="estado_via_alternativa",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class SolicitudViaAlternativaModel(Base):
    """ORM: solicitudes de via alternativa (ciclo de vida mutable, C-63 D-01)."""

    __tablename__ = "solicitudes_via_alternativa"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("usuario.id_institucional", ondelete="CASCADE"),
        nullable=False,
    )
    exam_id: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[EstadoViaAlternativaDB] = mapped_column(
        estado_via_alternativa_enum,
        nullable=False,
        server_default="pendiente_proctor",
    )
    timestamp_solicitud: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    timestamp_habilitacion: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=None,
    )
    habilitado_por: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
