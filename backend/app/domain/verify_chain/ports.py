"""Puertos del verify-chain (Protocols).

Hexagonal: el dominio define los contratos, infraestructura los implementa
contra slim DB.
"""

from __future__ import annotations

from typing import Protocol


class EventMaterialRepository(Protocol):
    """Lee el material verificable de un evento: el binario + el hash registrado."""

    async def get_event_material(
        self, event_id: str
    ) -> tuple[str | None, str | None] | None:
        """Devuelve (screenshot_b64, sha256_registrado).

        - None si el event_id no existe.
        - (None, ...) si el evento existe pero no tiene screenshot.
        - (..., None) si no hay hash registrado.
        """
        ...


class ChainVerificationAuditor(Protocol):
    """Asienta cada verify-chain en el audit log append-only."""

    async def log_chain_verification(
        self, event_id: str, *, actor: str, status: str, proposito: str
    ) -> None: ...
