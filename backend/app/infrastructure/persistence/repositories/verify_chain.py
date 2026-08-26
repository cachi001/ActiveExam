"""Adaptadores SQL activeexam para c-18 verify-chain.

- SqlEventMaterialRepository: lee proctoring_event.screenshot_b64 + screenshot_sha256
- SqlChainVerificationAuditor: escribe al audit_log via AuditLogSqlRepository
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from app.infrastructure.crypto.evidence_encryption import EvidenceCipher
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.acciones import EntidadAuditoria, ModuloAuditoria
from app.application.proctoring.captura_almacenada import leer_captura
from app.domain.audit_chain import AuditEntry
from app.domain.verify_chain.ports import (
    ChainVerificationAuditor,
    EventMaterialRepository,
)
from app.infrastructure.persistence.models.proctoring import ProctoringEventModel
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository


class SqlEventMaterialRepository(EventMaterialRepository):
    """Lee `screenshot_b64` + `screenshot_sha256` de proctoring_event.

    DESCIFRA la captura antes de devolverla (c-78). Es obligatorio, no una
    optimizacion: `screenshot_sha256` se calcula sobre el screenshot EN CLARO,
    antes de cifrar (`event_service`, paso 2), y esta columna guarda el token
    Fernet. Devolver el token hacia `VerifyChainService` lo hacia re-hashear el
    CIFRADO y compararlo contra el hash del CLARO — nunca coinciden.

    Con el cifrado activo (lo esta: `main_activeexam` construye el
    `EvidenceCipher` con `EMBEDDING_ENCRYPTION_KEY`) eso daba `broken`, o sea
    "evidencia manipulada", para TODOS los eventos. Y no es un endpoint de
    perito: `informe_service` corre este mismo servicio sobre CADA captura del
    informe de devolucion que ve el alumno.

    Sin cipher (tests, despliegue sin clave) se comporta como antes. El
    `decrypt` ademas devuelve tal cual lo que no es un token Fernet, asi que las
    filas legacy en claro se siguen verificando con el mismo camino.
    """

    def __init__(
        self, session: AsyncSession, *, cipher: "EvidenceCipher | None" = None
    ) -> None:
        self._session = session
        self._cipher = cipher

    async def get_event_material(
        self, event_id: str
    ) -> tuple[str | None, str | None] | None:
        stmt = select(
            ProctoringEventModel.screenshot_b64,
            ProctoringEventModel.screenshot_sha256,
            ProctoringEventModel.screenshot_bin,
            ProctoringEventModel.screenshot_prefijo,
        ).where(ProctoringEventModel.id == event_id)
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        # `leer_captura` reconstruye el data URL EXACTO que se hasheo al ingestar,
        # venga de la columna binaria nueva (c-78) o de la base64 legacy. Si la
        # reconstruccion no fuera byte a byte, verify-chain marcaria toda la
        # evidencia como manipulada.
        return (
            leer_captura(
                screenshot_bin=row[2],
                screenshot_prefijo=row[3],
                screenshot_b64_legacy=row[0],
                cipher=self._cipher,
            ),
            row[1],
        )


class SqlChainVerificationAuditor(ChainVerificationAuditor):
    """Escribe cada verify-chain al audit_log con propósito declarado."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditLogSqlRepository(session)

    async def log_chain_verification(
        self, event_id: str, *, actor: str, status: str, proposito: str
    ) -> None:
        # Resolver la sesión dueña del evento para poder linkear "Ver detalle"
        # a su página de proctoring en vez de caer al listado genérico.
        session_id = (
            await self._session.execute(
                select(ProctoringEventModel.session_id).where(
                    ProctoringEventModel.id == event_id
                )
            )
        ).scalar_one_or_none()
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",  # trigger lo completa
                ip="",
                user_agent="",
                accion=f"verify_chain.{status}",
                evidencia_id=event_id,
                proposito=proposito,
                hash_prev="",  # trigger lo completa
                modulo=ModuloAuditoria.EVIDENCIA,
                entidad=EntidadAuditoria.SESION if session_id else None,
                entidad_id=session_id,
            )
        )
