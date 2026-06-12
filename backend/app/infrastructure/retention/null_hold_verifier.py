"""Implementacion default del HoldVerifier para slim (Postgres puro).

En slim NO existe tabla ``caso_disciplinario``: esa vive en la rama full
(migracion 0002, no aplicada en produccion Railway). El NullHoldVerifier es
el default de slim — siempre devuelve NO_HOLD. Esto permite que el motor
de retencion funcione contra slim sin requerir conocimiento de holds; las
sesiones aged se borran por edad.

Cuando se proponga el sucesor c-69-dsr-caso-disciplinario (al migrar a VPS
con TimescaleDB y aplicar 0002), se reemplaza esta clase por una
``SqlHoldVerifier`` que consulta ``caso_disciplinario.hold`` — SIN tocar
dominio ni application.
"""

from __future__ import annotations

from app.domain.retention.hold import HoldDecision, HoldVerifier


class NullHoldVerifier(HoldVerifier):
    """Verificador de holds slim: siempre NO_HOLD.

    Justificacion: slim NO tiene tabla ``caso_disciplinario``, no hay forma
    de saber si una sesion esta en revision. La politica conservadora seria
    "todo es hold", pero eso bloquearia toda la retencion. La politica
    correcta en slim es "no hay holds" porque las decisiones del revisor
    viven solo en el store del frontend (c-46/c-47/c-48 archivados); cuando
    c-16 backend se implemente con persistencia real, este verifier se
    reemplaza.
    """

    async def verify(self, session_id: str) -> HoldDecision:
        # El id es opaco para slim: no consulto ninguna tabla.
        del session_id  # silencia warnings de linters sobre arg sin uso
        return HoldDecision.NO_HOLD
