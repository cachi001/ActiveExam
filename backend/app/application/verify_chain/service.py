"""Servicio de verificación de cadena de custodia (c-18 slim).

Re-calcula SHA-256 del screenshot guardado y lo compara con el hash
registrado al ingerir el evento. Cada llamada queda en el audit log con
propósito declarado.

Slim: 1 sola etapa (`screenshot_recorded`) — full agrega 3 etapas más en c-68.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.domain.verify_chain.certificate import (
    ChainStageResult,
    ChainVerificationStatus,
    CustodyChainCertificate,
)
from app.domain.verify_chain.ports import (
    ChainVerificationAuditor,
    EventMaterialRepository,
)


_PURPOSE_BY_STATUS = {
    ChainVerificationStatus.INTACT: "verify-chain: cadena integra",
    ChainVerificationStatus.BROKEN: (
        "verify-chain: cadena rota — evidencia no sostenida"
    ),
    ChainVerificationStatus.MATERIAL_MISSING: (
        "verify-chain: material faltante (screenshot/hash null)"
    ),
}


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class VerifyChainService:
    """Verifica la integridad de la cadena de custodia de un evento.

    Inyecta puertos: el repo de material (lee `proctoring_event`) y el
    auditor (escribe `audit_log` con triggers de cadena hash).
    """

    event_repo: EventMaterialRepository
    auditor: ChainVerificationAuditor
    now: Callable[[], datetime] = _default_now

    async def verify(
        self, event_id: str, *, actor: str
    ) -> CustodyChainCertificate:
        material = await self.event_repo.get_event_material(event_id)
        if material is None:
            raise ValueError(f"Evento {event_id!r} no encontrado")

        screenshot, registered_hash = material

        if screenshot is None or registered_hash is None:
            cert = CustodyChainCertificate(
                event_id=event_id,
                status=ChainVerificationStatus.MATERIAL_MISSING,
                algorithm="sha256",
                stages=[
                    ChainStageResult(
                        stage="screenshot_recorded",
                        expected=registered_hash or "",
                        actual=_sha256(screenshot) if screenshot else "",
                        match=False,
                    ),
                ],
                verified_at=self.now().isoformat(),
            )
            await self.auditor.log_chain_verification(
                event_id,
                actor=actor,
                status=cert.status.value,
                proposito=_PURPOSE_BY_STATUS[cert.status],
            )
            return cert

        recomputed = _sha256(screenshot)
        match = recomputed == registered_hash
        status = (
            ChainVerificationStatus.INTACT if match else ChainVerificationStatus.BROKEN
        )

        cert = CustodyChainCertificate(
            event_id=event_id,
            status=status,
            algorithm="sha256",
            stages=[
                ChainStageResult(
                    stage="screenshot_recorded",
                    expected=registered_hash,
                    actual=recomputed,
                    match=match,
                ),
            ],
            verified_at=self.now().isoformat(),
        )
        await self.auditor.log_chain_verification(
            event_id,
            actor=actor,
            status=status.value,
            proposito=_PURPOSE_BY_STATUS[status],
        )
        return cert
