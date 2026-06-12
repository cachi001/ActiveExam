"""Motor de retencion: orquesta los puertos del dominio.

Slim (Postgres puro, produccion Railway):
- ``apply_session_retention``: borra sesiones cuya creada_en es anterior al
  cutoff (now - policy.session_max_age_days), excepto las que el
  ``HoldVerifier`` marca como HOLD. Cada accion queda en el audit log.
- ``apply_embedding_egress``: para cada usuario con eliminado_en NOT NULL,
  borra sus embeddings de referencia y fotos de perfil. El egreso es
  independiente de holds de sesion (Ley 25.326 minimizacion).

Sin Parquet, sin compresion TimescaleDB — eso es c-67 cuando se migre a VPS.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

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
from app.domain.retention.report import RetentionDeletion, RetentionRunReport


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RetentionEngine:
    """Orquestador puro del motor de retencion.

    Inyecta puertos del dominio: el motor no conoce SQL ni HTTP. Las
    implementaciones SQL se cablean en composition root (router de admin).
    """

    aging_repo: SessionAgingRepository
    egress_repo: UserEgressRepository
    hold_verifier: HoldVerifier
    session_deleter: SessionDeleter
    embedding_deleter: EmbeddingDeleter
    foto_deleter: FotoDeleter
    auditor: RetentionAuditor
    now: Callable[[], datetime] = _default_now

    async def apply_session_retention(
        self, policy: RetentionPolicy, *, actor: str
    ) -> RetentionRunReport:
        """Borra sesiones aged segun ``policy.session_max_age_days``.

        Para cada sesion encontrada por el ``aging_repo``:
          - Si el ``hold_verifier`` reporta HOLD -> NO se borra, se registra
            como diferida en el reporte y en el audit log.
          - Si reporta NO_HOLD -> se borra (cascade a eventos via FK) y se
            registra en el audit log con razon ``age_exceeded``.
        """
        run_at = self.now()
        cutoff = run_at - timedelta(days=policy.session_max_age_days)

        aged_ids = await self.aging_repo.find_older_than(cutoff)

        deletions: list[RetentionDeletion] = []
        holds_deferred: list[str] = []
        for session_id in aged_ids:
            decision = await self.hold_verifier.verify(session_id)
            if decision == HoldDecision.HOLD:
                holds_deferred.append(session_id)
                await self.auditor.log_hold_deferred(session_id, actor=actor)
                continue

            await self.session_deleter.delete(session_id)
            deletions.append(
                RetentionDeletion(
                    target_id=session_id,
                    target_kind="session",
                    reason="age_exceeded",
                    at=run_at,
                )
            )
            await self.auditor.log_session_deleted(
                session_id, actor=actor, reason="age_exceeded"
            )

        return RetentionRunReport(
            policy_applied=policy,
            deletions=deletions,
            holds_deferred=holds_deferred,
            run_at=run_at,
        )

    async def apply_embedding_egress(self, *, actor: str) -> RetentionRunReport:
        """Borra embeddings + fotos de usuarios egresados.

        El egreso (``usuario.eliminado_en`` NOT NULL) elimina la base legal
        para conservar la biometria del titular. Holds de sesion NO aplican
        aca (RN-DSR-02: el egreso es evento legal independiente).
        """
        run_at = self.now()
        usuarios = await self.egress_repo.find_egressed_with_biometry()

        deletions: list[RetentionDeletion] = []
        for usuario_id in usuarios:
            embeddings_deleted = await self.embedding_deleter.delete_for_user(usuario_id)
            fotos_deleted = await self.foto_deleter.delete_for_user(usuario_id)
            if embeddings_deleted > 0:
                deletions.append(
                    RetentionDeletion(
                        target_id=usuario_id,
                        target_kind="embedding_referencia",
                        reason="user_egress",
                        at=run_at,
                    )
                )
            if fotos_deleted > 0:
                deletions.append(
                    RetentionDeletion(
                        target_id=usuario_id,
                        target_kind="foto_referencia",
                        reason="user_egress",
                        at=run_at,
                    )
                )
            await self.auditor.log_biometric_egress(
                usuario_id,
                actor=actor,
                embeddings_deleted=embeddings_deleted,
                fotos_deleted=fotos_deleted,
            )

        return RetentionRunReport(
            policy_applied=RetentionPolicy.default(),
            deletions=deletions,
            holds_deferred=[],
            run_at=run_at,
        )
