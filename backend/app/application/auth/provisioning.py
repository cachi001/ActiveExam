"""JIT provisioning del Usuario al primer login federado (aplicacion, C-06 D1).

Al primer login federado se crea la entidad ``Usuario`` (C-05) tomando id
institucional, roles y atributos del principal ya autenticado; logins posteriores
REUTILIZAN/ACTUALIZAN el Usuario existente sin duplicar (idempotencia).

Depende del PUERTO ``UserRepository`` (dominio), no del adaptador SQLAlchemy
(Hexagonal): el caso de uso es agnostico de la persistencia y se testea con un
repositorio en memoria o con la base real (regla dura: sin mock de DB).
"""

from __future__ import annotations

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.entities.user import Usuario
from app.domain.repositories.ports import UserRepository


class JitProvisioningService:
    """Crea o actualiza el Usuario (C-05) a partir del principal federado."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def provision(self, principal: AuthenticatedPrincipal) -> Usuario:
        """Devuelve el Usuario provisionado JIT (idempotente por id institucional).

        - Primer login: crea el Usuario con sus atributos federados.
        - Logins posteriores: actualiza roles/email/atributos del Usuario existente,
          sin crear duplicados (clave: ``id_institucional``)."""
        roles = tuple(r.value for r in principal.roles)
        existente = await self._users.get_by_id_institucional(principal.id_institucional)
        if existente is None:
            nuevo = Usuario(
                id_institucional=principal.id_institucional,
                email=principal.email,
                roles=roles,
                attrs_federados=dict(principal.attrs_federados),
            )
            return await self._users.add(nuevo)

        # Login posterior: reutiliza el Usuario, refrescando los datos federados.
        actualizado = Usuario(
            id=existente.id,
            id_institucional=existente.id_institucional,
            email=principal.email or existente.email,
            roles=roles or existente.roles,
            attrs_federados=dict(principal.attrs_federados) or existente.attrs_federados,
        )
        return await self._users.update(actualizado)
