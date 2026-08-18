"""Repositorio de consentimiento ACTIVEEXAM (C-63).

En el modulo activeexam (Railway) la tabla ``consentimiento`` no existe — el schema
activeexam no incluye la historia de migraciones de la rama principal. Este adaptador
provee una implementacion no-operativa del ``ConsentRepository`` que siempre
retorna lista vacia (el consentimiento full se gestiona en el modulo completo).

Esto permite que el ``ConsentService`` corra en activeexam para el flujo de via
alternativa (C-63) sin necesitar la tabla ``consentimiento``.
"""

from __future__ import annotations

from app.domain.entities.consent import Consentimiento
from app.domain.repositories.ports import ConsentRepository


class NoOpConsentRepository(ConsentRepository):
    """Repositorio de consentimiento sin-operacion para el modulo activeexam.

    La tabla ``consentimiento`` no existe en activeexam (es parte del schema full).
    Este repositorio retorna lista vacia en ``list()`` y ``None`` en ``get()``,
    haciendo que ``resolve()`` caiga al flujo de via alternativa / audit log.

    ``add`` nunca deberia llamarse en activeexam — levanta RuntimeError si se llama.
    """

    async def add(self, entity: Consentimiento) -> Consentimiento:
        raise RuntimeError(
            "NoOpConsentRepository: no se puede registrar consentimiento en el modulo activeexam. "
            "Use el modulo completo para el acuse de consentimiento."
        )

    async def get(self, entity_id: str) -> Consentimiento | None:
        return None

    async def list(self) -> list[Consentimiento]:
        return []
