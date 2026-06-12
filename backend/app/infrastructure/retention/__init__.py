"""Implementaciones default de los puertos de dominio retention.

Slim (sin tabla ``caso_disciplinario``): ``NullHoldVerifier`` es el default
de produccion. Cuando llegue c-69 sobre tabla ``caso_disciplinario`` se
reemplaza por ``SqlHoldVerifier`` SIN tocar dominio ni application
(hexagonal: ports/adapters).
"""

from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier

__all__ = ["NullHoldVerifier"]
