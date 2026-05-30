"""Gates de autorizacion contextual que necesitan el repositorio (aplicacion, D3).

El RBAC del proctor exige conocer sus exámenes asignados (entidad ``Asignacion``,
C-05). El dominio decide con ese dato (``autorizar_proctor_sobre_examen``); este
servicio lo RESUELVE contra el ``AssignmentRepository`` y delega la decision al
dominio puro. Asi la regla queda en dominio y el lookup en aplicacion.

Para el acceso a evidencia, ademas de decidir el acceso (dominio), registra el
PROPOSITO declarado en el audit log (C-05 ``AuditLogRepository``) — sin sancionar
(L2.5): solo controla acceso y deja traza.
"""

from __future__ import annotations

from app.domain.auth import authorization
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.audit_chain import AuditEntry
from app.domain.repositories.ports import AssignmentRepository, AuditLogRepository


class ContextualAuthorizationService:
    """Resuelve el contexto (asignacion/jurisdiccion) y delega la decision al dominio."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        audit_log: AuditLogRepository,
    ) -> None:
        self._assignments = assignments
        self._audit = audit_log

    async def _examenes_asignados(self, proctor_id: str) -> set[str]:
        """Exámenes en la Asignacion del proctor (C-05)."""
        todas = await self._assignments.list()
        return {a.exam_id for a in todas if a.proctor_id == proctor_id}

    async def autorizar_proctor(
        self,
        principal: AuthenticatedPrincipal,
        *,
        proctor_id: str,
        exam_id: str,
    ) -> None:
        """Autoriza al proctor sobre un examen SOLO si esta en su Asignacion (D3).

        Levanta ``ForbiddenError`` (-> 403) si el examen no esta asignado."""
        asignados = await self._examenes_asignados(proctor_id)
        authorization.autorizar_proctor_sobre_examen(principal, exam_id, asignados)

    def autorizar_revisor(
        self,
        principal: AuthenticatedPrincipal,
        *,
        jurisdiccion_recurso: str,
    ) -> None:
        """Autoriza al revisor solo dentro de su jurisdiccion (D3)."""
        authorization.autorizar_revisor_sobre_jurisdiccion(principal, jurisdiccion_recurso)

    async def acceder_a_evidencia(
        self,
        principal: AuthenticatedPrincipal,
        *,
        evidencia_id: str | None,
        proposito: str,
        ip: str,
        user_agent: str,
        timestamp: str,
    ) -> None:
        """Gate de acceso a evidencia + traza de auditoria con PROPOSITO (D3).

        1. Decide el acceso (dominio: rol con acceso + MFA).
        2. Registra en el audit log (C-05) actor/recurso/proposito (sin sancionar)."""
        authorization.puede_acceder_a_evidencia(principal)
        entrada = AuditEntry(
            actor=principal.id_institucional,
            timestamp=timestamp,
            ip=ip,
            user_agent=user_agent,
            accion="acceso_evidencia",
            evidencia_id=evidencia_id,
            proposito=proposito,
        )
        await self._audit.append(entrada)
