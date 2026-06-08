"""Repositorio de consentimiento SLIM (C-63).

En el modulo slim (Railway) la tabla ``consentimiento`` no existe — el schema
slim no incluye la historia de migraciones de la rama principal. Este adaptador
provee una implementacion no-operativa del ``ConsentRepository`` que siempre
retorna lista vacia (el consentimiento full se gestiona en el modulo completo).

Esto permite que el ``ConsentService`` corra en slim para el flujo de via
alternativa (C-63) sin necesitar la tabla ``consentimiento``.
"""

from __future__ import annotations

from app.domain.entities.consent import Consentimiento
from app.domain.repositories.ports import ConsentRepository


class NoOpConsentRepository(ConsentRepository):
    """Repositorio de consentimiento sin-operacion para el modulo slim.

    La tabla ``consentimiento`` no existe en slim (es parte del schema full).
    Este repositorio retorna lista vacia en ``list()`` y ``None`` en ``get()``,
    haciendo que ``resolve()`` caiga al flujo de via alternativa / audit log.

    ``add`` nunca deberia llamarse en slim — levanta RuntimeError si se llama.
    """

    async def add(self, entity: Consentimiento) -> Consentimiento:
        raise RuntimeError(
            "NoOpConsentRepository: no se puede registrar consentimiento en el modulo slim. "
            "Use el modulo completo para el acuse de consentimiento."
        )

    async def get(self, entity_id: str) -> Consentimiento | None:
        return None

    async def list(self) -> list[Consentimiento]:
        return []
