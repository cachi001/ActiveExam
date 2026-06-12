"""Dominio puro del motor de retencion (C-19).

Capa hexagonal con value objects, enums y puertos (Protocols) sin acoplarse
a la DB ni a SQLAlchemy. Las implementaciones SQL viven en
``app.infrastructure.persistence.repositories.retention`` y el orquestador en
``app.application.retention.engine``.

Slim (Postgres puro, produccion Railway): las features de TimescaleDB
(compresion nativa, archivado a Parquet, drop de chunks) NO se implementan;
quedan diferidas al change sucesor c-67-retencion-archival-timescaledb que
se propone cuando se migre el stack a VPS con TimescaleDB.
"""

from app.domain.retention.hold import HoldDecision, HoldVerifier
from app.domain.retention.policy import RetentionPolicy
from app.domain.retention.ports import (
    EmbeddingDeleter,
    FotoDeleter,
    RetentionAuditor,
    SessionAgingRepository,
    SessionDeleter,
    UserEgressRepository,
)
from app.domain.retention.report import (
    RetentionDeletion,
    RetentionRunReport,
)

__all__ = [
    "EmbeddingDeleter",
    "FotoDeleter",
    "HoldDecision",
    "HoldVerifier",
    "RetentionAuditor",
    "RetentionDeletion",
    "RetentionPolicy",
    "RetentionRunReport",
    "SessionAgingRepository",
    "SessionDeleter",
    "UserEgressRepository",
]
