"""Gates de autorizacion contextual que necesitan el repositorio (aplicacion, D3).

El proctor tiene alcance GLOBAL sobre todos los exámenes activos (C-50): el metodo
``autorizar_proctor`` ya no resuelve asignaciones y delega directamente al dominio
puro. El revisor sigue scoped a su jurisdiccion.

Para el acceso a evidencia, ademas de decidir el acceso (dominio), registra el
PROPOSITO declarado en el audit log (C-05 ``AuditLogRepository``) — sin sancionar
(L2.5): solo controla acceso y deja traza.
"""

from __future__ import annotations

from app.domain.auth import authorization
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.audit_chain import AuditEntry
from app.domain.repositories.ports import AuditLogRepository


class ContextualAuthorizationService:
    """Resuelve el contexto (jurisdiccion/evidencia) y delega la decision al dominio."""

    def __init__(
        self,
        audit_log: AuditLogRepository,
    ) -> None:
        self._audit = audit_log

    def autorizar_proctor(
        self,
        principal: AuthenticatedPrincipal,
        *,
        exam_id: str,
    ) -> None:
        """Autoriza al proctor sobre cualquier examen activo (alcance global, C-50).

        El proctor con MFA satisfecho accede a todos los exámenes sin necesidad de
        asignacion previa. La relajacion del minimo privilegio queda justificada en
        el DPIA (C-01). No levanta excepcion si el acceso es valido."""
        authorization.autorizar_proctor(principal)

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
