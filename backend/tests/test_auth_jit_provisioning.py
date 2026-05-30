"""Tests del JIT provisioning del Usuario (C-06, keycloak-federation-jit).

Verifica D1: el primer login federado CREA el Usuario (C-05) sin alta previa; un
login posterior REUTILIZA/actualiza el mismo Usuario sin duplicar (idempotencia).

Usa un repositorio EN MEMORIA que implementa el puerto ``UserRepository`` (no
mockea la DB: implementa el contrato real del dominio). El adaptador SQLAlchemy se
prueba con la base real en ``@requires_stack``.
"""

from __future__ import annotations

import asyncio

from app.application.auth.provisioning import JitProvisioningService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.entities.user import Usuario
from app.domain.repositories.ports import UserRepository


class InMemoryUserRepo(UserRepository):
    """Implementacion en memoria del puerto (contrato real, sin mock de DB)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Usuario] = {}
        self._seq = 0

    async def add(self, entity: Usuario) -> Usuario:
        self._seq += 1
        persisted = Usuario(
            id=str(self._seq),
            id_institucional=entity.id_institucional,
            email=entity.email,
            roles=entity.roles,
            attrs_federados=entity.attrs_federados,
        )
        self._by_id[persisted.id] = persisted
        return persisted

    async def get(self, entity_id: str) -> Usuario | None:
        return self._by_id.get(entity_id)

    async def list(self) -> list[Usuario]:
        return list(self._by_id.values())

    async def update(self, entity: Usuario) -> Usuario:
        assert entity.id is not None
        self._by_id[entity.id] = entity
        return entity

    async def get_by_id_institucional(self, id_institucional: str) -> Usuario | None:
        for u in self._by_id.values():
            if u.id_institucional == id_institucional:
                return u
        return None


def _principal(roles=(Rol.PROCTOR,), email="p@uni.edu") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id_institucional="inst-42", email=email, roles=roles, mfa_satisfecho=True
    )


def test_primer_login_crea_usuario() -> None:
    async def run() -> None:
        repo = InMemoryUserRepo()
        svc = JitProvisioningService(repo)
        usuario = await svc.provision(_principal())
        assert usuario.id is not None
        assert usuario.id_institucional == "inst-42"
        assert len(await repo.list()) == 1

    asyncio.run(run())


def test_login_posterior_no_duplica() -> None:
    async def run() -> None:
        repo = InMemoryUserRepo()
        svc = JitProvisioningService(repo)
        primero = await svc.provision(_principal())
        # Segundo login: email/roles distintos -> actualiza, no crea otro.
        segundo = await svc.provision(_principal(email="nuevo@uni.edu"))
        assert primero.id == segundo.id
        assert segundo.email == "nuevo@uni.edu"
        assert len(await repo.list()) == 1

    asyncio.run(run())
