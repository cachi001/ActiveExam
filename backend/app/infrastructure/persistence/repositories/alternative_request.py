"""Adaptador SQLAlchemy del repositorio de solicitudes de via alternativa (C-63).

Implementa ``AlternativeRequestRepository`` usando la tabla
``solicitudes_via_alternativa`` (ORM: ``SolicitudViaAlternativaModel``).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.alternative_request import (
    EstadoViaAlternativa,
    SolicitudViaAlternativa,
)
from app.domain.repositories.ports import AlternativeRequestRepository
from app.infrastructure.persistence.models.alternative_request import (
    EstadoViaAlternativaDB,
    SolicitudViaAlternativaModel,
)


def _to_domain(m: SolicitudViaAlternativaModel) -> SolicitudViaAlternativa:
    """Convierte el modelo ORM a la entidad de dominio."""
    return SolicitudViaAlternativa(
        id=m.id,
        user_id=m.user_id,
        exam_id=m.exam_id,
        estado=EstadoViaAlternativa(m.estado.value),
        timestamp_solicitud=str(m.timestamp_solicitud),
        timestamp_habilitacion=(
            str(m.timestamp_habilitacion) if m.timestamp_habilitacion is not None else None
        ),
        habilitado_por=m.habilitado_por,
    )


class AlternativeRequestSqlRepository(AlternativeRequestRepository):
    """Repositorio SQLAlchemy para solicitudes de via alternativa."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, solicitud: SolicitudViaAlternativa) -> SolicitudViaAlternativa:
        """Persiste una nueva solicitud con estado pendiente_proctor."""
        row = SolicitudViaAlternativaModel(
            user_id=solicitud.user_id,
            exam_id=solicitud.exam_id,
            estado=EstadoViaAlternativaDB(solicitud.estado.value),
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_user_exam(
        self, user_id: str, exam_id: str
    ) -> SolicitudViaAlternativa | None:
        """Busca la solicitud activa para el par (user_id, exam_id)."""
        result = await self._session.execute(
            select(SolicitudViaAlternativaModel).where(
                SolicitudViaAlternativaModel.user_id == user_id,
                SolicitudViaAlternativaModel.exam_id == exam_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def list_pending(self) -> list[SolicitudViaAlternativa]:
        """Lista todas las solicitudes con estado pendiente_proctor."""
        result = await self._session.execute(
            select(SolicitudViaAlternativaModel).where(
                SolicitudViaAlternativaModel.estado
                == EstadoViaAlternativaDB.PENDIENTE_PROCTOR
            )
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def update_estado(
        self,
        solicitud_id: str,
        estado: EstadoViaAlternativa,
        habilitado_por: str | None,
        timestamp: str | None,
    ) -> SolicitudViaAlternativa:
        """Actualiza el estado y registra quién habilitó y cuándo."""
        row = await self._session.get(SolicitudViaAlternativaModel, solicitud_id)
        if row is None:
            raise ValueError(f"Solicitud {solicitud_id!r} no encontrada.")
        row.estado = EstadoViaAlternativaDB(estado.value)
        if habilitado_por is not None:
            row.habilitado_por = habilitado_por
        if timestamp is not None:
            # Almacenar como datetime si viene como ISO string
            try:
                row.timestamp_habilitacion = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                row.timestamp_habilitacion = datetime.now(timezone.utc)
        await self._session.flush()
        return _to_domain(row)
