"""Verify-chain activeexam (c-18): re-verifica integridad SHA-256 de screenshots.

Modulo separado del router de evidencia full (que depende de la tabla
``evidencia`` que no existe en activeexam). Solo expone el endpoint que necesita
el activeexam: POST /api/v1/evidence/{event_id}/verify-chain.

Cuando llegue la rama full con tabla `evidencia` (c-68 sucesor), se
reemplaza este router por el de full sin tocar este modulo (queda como
historico).
"""

from app.presentation.api.v1.verify_chain.router import router as verify_chain_activeexam_router

__all__ = ["verify_chain_activeexam_router"]
