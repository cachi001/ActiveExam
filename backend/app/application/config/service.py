"""ConfigService: carga la configuracion EFECTIVA autoritativa server-side.

Combina dos fuentes persistidas en una sola lectura coherente:
- ``configuracion_sistema`` (singleton): umbrales, umbral de cola, detectores,
  retencion, version de consentimiento, y la ``version`` monotonica (ETag).
- ``evento_score_config`` (por tipo de evento): los pesos de scoring, solo los
  activos.

Cachea el resultado en memoria e invalida por ``version`` (o explicitamente via
``invalidate()`` tras una edicion). TEST DETECCION y los examenes leen ESTO en vez
de constantes hardcodeadas (cierra GAP #1). El score PRIORIZA, nunca sanciona (L2.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
    EventoScoreConfigModel,
)
from app.infrastructure.persistence.repositories.config_sistema import (
    ConfiguracionSistemaSqlRepository,
)


@dataclass(frozen=True, slots=True)
class ConfigEfectiva:
    """Objeto autoritativo completo de configuracion (lo que consume el cliente)."""

    version: int
    face_absent_ms: int
    multiple_faces_frames: int
    gaze_deviation_threshold: float
    gaze_sustained_ms: int
    gaze_fixation_tolerance: float
    umbral_cola_revision: int
    retencion_dias_default: int
    consent_version_vigente: str
    detectores_activos: tuple[str, ...]
    # Pesos de scoring por tipo de evento (solo tipos activos).
    scoring_weights: dict[str, int] = field(default_factory=dict)
    # Severidad configurada por tipo de evento (solo tipos activos). El cliente la usa
    # para mostrar la severidad VIGENTE (no la del catalogo hardcodeado).
    scoring_severidades: dict[str, str] = field(default_factory=dict)


class ConfigService:
    """Servicio de lectura de la config efectiva con cache invalidable por version."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory
        self._cache: ConfigEfectiva | None = None

    def invalidate(self) -> None:
        """Invalida el cache; la proxima lectura recarga desde la BD."""
        self._cache = None

    async def get_efectiva(self) -> ConfigEfectiva:
        """Devuelve la config efectiva. Usa cache salvo que este invalidado."""
        if self._cache is not None:
            return self._cache
        async with self._factory() as session:
            efectiva = await self._cargar(session)
        self._cache = efectiva
        return efectiva

    async def _cargar(self, session: AsyncSession) -> ConfigEfectiva:
        repo = ConfiguracionSistemaSqlRepository(session)
        cfg = await repo.get()
        if cfg is None:
            cfg = await repo.ensure_singleton()
            await session.commit()
        pesos, severidades = await self._scoring_activos(session)
        return ConfigEfectiva(
            version=cfg.version,
            face_absent_ms=cfg.face_absent_ms,
            multiple_faces_frames=cfg.multiple_faces_frames,
            gaze_deviation_threshold=float(cfg.gaze_deviation_threshold),
            gaze_sustained_ms=cfg.gaze_sustained_ms,
            gaze_fixation_tolerance=float(cfg.gaze_fixation_tolerance),
            umbral_cola_revision=cfg.umbral_cola_revision,
            retencion_dias_default=cfg.retencion_dias_default,
            consent_version_vigente=cfg.consent_version_vigente,
            detectores_activos=tuple(cfg.detectores_activos or ()),
            scoring_weights=pesos,
            scoring_severidades=severidades,
        )

    async def _scoring_activos(
        self, session: AsyncSession
    ) -> tuple[dict[str, int], dict[str, str]]:
        """Pesos y severidades configurados por tipo de evento (solo tipos activos)."""
        result = await session.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
                EventoScoreConfigModel.severidad,
            ).where(EventoScoreConfigModel.activo.is_(True))
        )
        rows = result.all()
        pesos = {row.tipo_evento: row.peso for row in rows}
        severidades = {row.tipo_evento: row.severidad for row in rows}
        return pesos, severidades
