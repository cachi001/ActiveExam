"""Adaptadores SQL slim para los puertos del dominio retention (c-19).

Implementa los Protocols definidos en ``app.domain.retention.ports`` contra
las tablas que existen en la rama slim (migraciones 0005-0012, postgres puro):

  - SqlSessionAgingRepository -> proctoring_session.creada_en
  - SqlSessionDeleter         -> DELETE proctoring_session (cascade a eventos)
  - SqlUserEgressRepository   -> usuario.eliminado_en + biometria asociada
  - SqlEmbeddingDeleter       -> DELETE embedding_referencia por usuario_id
  - SqlFotoDeleter            -> DELETE foto_referencia por usuario_id
  - SqlRetentionAuditor       -> append al audit_log via AuditLogSqlRepository

NO crea migracion nueva: usa tablas existentes en produccion Railway.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import AuditEntry
from app.domain.retention.ports import (
    EmbeddingDeleter,
    FotoDeleter,
    RetentionAuditor,
    SessionAgingRepository,
    SessionDeleter,
    UserEgressRepository,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.models.transactional import (
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository


class SqlSessionAgingRepository(SessionAgingRepository):
    """Devuelve ids de sesiones cuya ``creada_en`` < cutoff."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_older_than(self, cutoff: datetime) -> list[str]:
        stmt = select(ProctoringSessionModel.id).where(
            ProctoringSessionModel.creada_en < cutoff
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]


class SqlSessionDeleter(SessionDeleter):
    """DELETE proctoring_session por id. Cascade FK borra los eventos hijos."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete(self, session_id: str) -> None:
        stmt = delete(ProctoringSessionModel).where(
            ProctoringSessionModel.id == session_id
        )
        await self._session.execute(stmt)


class SqlUserEgressRepository(UserEgressRepository):
    """Lista usuarios con ``eliminado_en`` NOT NULL y biometria asociada.

    Filtro por existencia (NOT EXISTS evita iterar usuarios sin biometria).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_egressed_with_biometry(self) -> list[str]:
        has_embedding = exists().where(
            EmbeddingReferenciaModel.usuario_id == UsuarioModel.id
        )
        has_foto = exists().where(FotoReferenciaModel.usuario_id == UsuarioModel.id)
        stmt = (
            select(UsuarioModel.id)
            .where(UsuarioModel.eliminado_en.isnot(None))
            .where(has_embedding | has_foto)
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]


class SqlEmbeddingDeleter(EmbeddingDeleter):
    """DELETE embedding_referencia por usuario_id, devuelve filas borradas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_for_user(self, usuario_id: str) -> int:
        stmt = delete(EmbeddingReferenciaModel).where(
            EmbeddingReferenciaModel.usuario_id == usuario_id
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)


class SqlFotoDeleter(FotoDeleter):
    """DELETE foto_referencia por usuario_id, devuelve filas borradas.

    Slim: borra solo la fila en DB. La purga del binario en MinIO/S3 es
    responsabilidad de un job de object storage aparte (no implementado en
    slim porque no hay MinIO/S3 en Railway).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_for_user(self, usuario_id: str) -> int:
        stmt = delete(FotoReferenciaModel).where(
            FotoReferenciaModel.usuario_id == usuario_id
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)


class SqlRetentionAuditor(RetentionAuditor):
    """Escribe al audit_log via el repositorio append-only existente.

    Cada accion del motor (borrado de sesion / hold diferido / egreso de
    biometria) queda como una fila append-only con propopsito declarado y
    sin re-exponer PII. La cadena de hash la mantiene el trigger SQL.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditLogSqlRepository(session)

    async def log_session_deleted(
        self, session_id: str, *, actor: str, reason: str
    ) -> None:
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",  # trigger lo completa
                ip="",
                user_agent="",
                accion="retention.session.deleted",
                evidencia_id=session_id,
                proposito=f"slim retention: {reason}",
                hash_prev="",  # trigger lo completa
            )
        )

    async def log_hold_deferred(self, session_id: str, *, actor: str) -> None:
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",
                ip="",
                user_agent="",
                accion="retention.session.hold_deferred",
                evidencia_id=session_id,
                proposito="slim retention: hold detected, deletion deferred",
                hash_prev="",
            )
        )

    async def log_biometric_egress(
        self,
        usuario_id: str,
        *,
        actor: str,
        embeddings_deleted: int,
        fotos_deleted: int,
    ) -> None:
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",
                ip="",
                user_agent="",
                accion="retention.biometric.egress",
                evidencia_id=usuario_id,
                proposito=(
                    f"slim retention: usuario egresado, "
                    f"embeddings={embeddings_deleted}, fotos={fotos_deleted}"
                ),
                hash_prev="",
            )
        )
