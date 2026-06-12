"""Decision de hold y puerto HoldVerifier.

Un "hold" extiende automaticamente la retencion de los datos de una sesion
mientras haya un caso disciplinario abierto o una revision pendiente. En
slim esto se simplifica: NO existe tabla ``caso_disciplinario``, asi que el
verificador por defecto (``NullHoldVerifier`` en infrastructure) siempre
reporta NO_HOLD. La implementacion SQL real es c-69 (sucesor planificado).
"""

from __future__ import annotations

import enum
from typing import Protocol


class HoldDecision(str, enum.Enum):
    """Decision del verificador de holds.

    Hereda de ``str`` para que se serialice directo en payloads de audit log
    y respuestas HTTP sin acoplar al cliente al enum.
    """

    HOLD = "hold"
    NO_HOLD = "no_hold"


class HoldVerifier(Protocol):
    """Puerto del verificador de holds.

    El motor de retencion (``RetentionEngine``) consulta este puerto para
    cada sesion candidata a ser borrada. Si reporta HOLD, la sesion NO se
    borra y queda registrada como "diferida" en el reporte de la corrida.

    Implementaciones:
        - ``NullHoldVerifier`` (slim default): siempre NO_HOLD.
        - ``SqlHoldVerifier`` (c-69 sucesor, no implementado todavia): consulta
          ``caso_disciplinario.hold`` cuando exista la tabla en full.
    """

    async def verify(self, session_id: str) -> HoldDecision:
        """Devuelve HoldDecision para una sesion. Nunca lanza excepciones
        por id desconocido — devuelve NO_HOLD por defecto."""
        ...
