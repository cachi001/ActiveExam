"""Dependencias de la API de biometria: arma el VerifyIdentityService (C-09).

Compone, por request, el pipeline de verificacion sobre una sesion async:
- repos SQLAlchemy de Embedding/Evento/Sesion (adaptadores de C-05).
- ConsentService (gate C-08) y ExamConfigService (gate de referencia C-07).
- motor de vision server-side (re-inferencia, DD-17) — cableado desde app.state.
- KMS cipher + secret provider (Vault) — cableados desde app.state.
- cola (default A4) desde app.state.

Si la persistencia o el motor de vision no estan cableados (entorno sin stack),
la dependencia devuelve 500 explicito en vez de fingir. Los tests inyectan
overrides con puertos en memoria.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.biometrics.service import VerifyIdentityService
from app.application.consent.service import ConsentService
from app.application.exam_config.service import ExamConfigService
from app.infrastructure.biometrics.reference import (
    EncryptedReferenceReader,
    EncryptingEmbeddingRepository,
)
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository
from app.infrastructure.persistence.repositories.consent import ConsentSqlRepository
from app.infrastructure.persistence.repositories.event import EventSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    AssignmentSqlRepository,
    EmbeddingSqlRepository,
    ExamSqlRepository,
    SessionSqlRepository,
)


def _require(request: Request, attr: str):
    value = getattr(request.app.state, attr, None)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Subsistema de biometria no inicializado ({attr}).",
        )
    return value


async def get_verify_service(request: Request) -> AsyncIterator[VerifyIdentityService]:
    """Provee el ``VerifyIdentityService`` ligado a una sesion async por request."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    vision = _require(request, "vision_engine")
    cipher = _require(request, "kms_cipher")
    secrets = _require(request, "secret_provider")
    queue = _require(request, "message_queue")

    async with factory() as session:
        embeddings = EncryptingEmbeddingRepository(
            EmbeddingSqlRepository(session), cipher
        )
        referencias = EncryptedReferenceReader(EmbeddingSqlRepository(session), cipher)
        consent = ConsentService(
            ConsentSqlRepository(session), AuditLogSqlRepository(session), queue
        )
        exam_cfg = ExamConfigService(
            ExamSqlRepository(session), AssignmentSqlRepository(session)
        )
        service = VerifyIdentityService(
            vision=vision,
            referencias=referencias,
            secretos=secrets,
            embeddings=embeddings,
            eventos=EventSqlRepository(session),
            sesiones=SessionSqlRepository(session),
            consent=consent,
            exam_config=exam_cfg,
            queue=queue,
        )
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise
