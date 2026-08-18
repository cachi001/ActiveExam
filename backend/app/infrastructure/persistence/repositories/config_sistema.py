"""Repositorio SQLAlchemy de la Configuracion del Sistema (singleton versionado).

La tabla ``configuracion_sistema`` tiene UNA fila (id='global'). ``ensure_singleton``
la crea con los defaults si no existe (idempotente). ``get`` la lee. ``update`` aplica
los cambios y hace bump MONOTONICO de ``version`` (ETag) en la misma transaccion.

La auditoria (fila inmutable en audit_log con before/after) NO la hace el repo: la
orquesta el servicio/endpoint para tener el snapshot before completo. El repo solo
persiste la config y su version.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
)

# Id fijo de la fila singleton global.
SINGLETON_ID = "global"

# Campos editables (lo demas — id, version, updated_at — lo controla el repo).
CAMPOS_EDITABLES: frozenset[str] = frozenset(
    {
        "face_absent_ms",
        "multiple_faces_frames",
        "gaze_deviation_threshold",
        "gaze_sustained_ms",
        "gaze_fixation_tolerance",
        "umbral_cola_revision",
        "detectores_activos",
        "retencion_dias_default",
        "consent_version_vigente",
        "chat_habilitado",
        "pausas_habilitadas",
        "pausa_max_min",
        "pausas_max_por_sesion",
    }
)


class ConfiguracionSistemaSqlRepository:
    """Acceso a la fila singleton de configuracion global."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> ConfiguracionSistemaModel | None:
        return await self._session.get(ConfiguracionSistemaModel, SINGLETON_ID)

    async def ensure_singleton(self) -> ConfiguracionSistemaModel:
        """Crea la fila global con los defaults si no existe (idempotente)."""
        existente = await self.get()
        if existente is not None:
            return existente
        fila = ConfiguracionSistemaModel(id=SINGLETON_ID)
        self._session.add(fila)
        await self._session.flush()
        await self._session.refresh(fila)
        return fila

    async def update(self, cambios: dict[str, Any]) -> ConfiguracionSistemaModel:
        """Aplica ``cambios`` (solo CAMPOS_EDITABLES) y hace bump de version.

        Crea el singleton si no existe. Ignora claves no editables (la validacion
        de forma la hace el schema Pydantic antes de llegar aqui)."""
        fila = await self.ensure_singleton()
        for clave, valor in cambios.items():
            if clave in CAMPOS_EDITABLES:
                setattr(fila, clave, valor)
        fila.version = (fila.version or 0) + 1
        await self._session.flush()
        await self._session.refresh(fila)
        return fila
