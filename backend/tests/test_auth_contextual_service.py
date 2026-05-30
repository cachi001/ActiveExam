"""Tests del servicio de autorizacion contextual con repositorios (C-06, D3).

Verifica que el RBAC del proctor resuelve la ``Asignacion`` (C-05) contra el
repositorio y delega la decision al dominio: proctor sobre examen no asignado ->
403; y que el acceso a evidencia registra el PROPOSITO en el audit log (sin
sancionar — L2.5).

Repositorios EN MEMORIA que implementan los puertos reales (sin mock de DB).
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.auth.authorization_service import ContextualAuthorizationService
from app.domain.audit_chain import AuditEntry, construir_cadena, verificar_cadena
from app.domain.auth.errors import ForbiddenError, MfaRequiredError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.entities.assignment import Asignacion
from app.domain.repositories.ports import AssignmentRepository, AuditLogRepository


class InMemoryAssignmentRepo(AssignmentRepository):
    def __init__(self, asignaciones: list[Asignacion]) -> None:
        self._items = list(asignaciones)

    async def add(self, entity: Asignacion) -> Asignacion:
        self._items.append(entity)
        return entity

    async def get(self, entity_id: str) -> Asignacion | None:
        return next((a for a in self._items if a.id == entity_id), None)

    async def list(self) -> list[Asignacion]:
        return list(self._items)

    async def update(self, entity: Asignacion) -> Asignacion:
        return entity


class InMemoryAuditRepo(AuditLogRepository):
    def __init__(self) -> None:
        self._items: list[AuditEntry] = []

    async def append(self, entity: AuditEntry) -> AuditEntry:
        encadenada = construir_cadena(self._items + [entity])[-1]
        self._items.append(encadenada)
        return encadenada

    async def get(self, entity_id: str) -> AuditEntry | None:
        return None

    async def list(self) -> list[AuditEntry]:
        return list(self._items)

    async def verificar_cadena(self) -> bool:
        return verificar_cadena(self._items)


def _proctor() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id_institucional="proctor-1",
        email="p@uni.edu",
        roles=(Rol.PROCTOR,),
        mfa_satisfecho=True,
    )


def test_proctor_no_asignado_rechazado_por_servicio() -> None:
    async def run() -> None:
        repo = InMemoryAssignmentRepo([Asignacion(proctor_id="user-99", exam_id="EX-1")])
        audit = InMemoryAuditRepo()
        svc = ContextualAuthorizationService(repo, audit)
        with pytest.raises(ForbiddenError):
            await svc.autorizar_proctor(_proctor(), proctor_id="user-1", exam_id="EX-1")

    asyncio.run(run())


def test_proctor_asignado_autorizado_por_servicio() -> None:
    async def run() -> None:
        repo = InMemoryAssignmentRepo([Asignacion(proctor_id="user-1", exam_id="EX-1")])
        audit = InMemoryAuditRepo()
        svc = ContextualAuthorizationService(repo, audit)
        await svc.autorizar_proctor(_proctor(), proctor_id="user-1", exam_id="EX-1")

    asyncio.run(run())


def test_acceso_evidencia_registra_proposito_en_audit() -> None:
    async def run() -> None:
        repo = InMemoryAssignmentRepo([])
        audit = InMemoryAuditRepo()
        svc = ContextualAuthorizationService(repo, audit)
        await svc.acceder_a_evidencia(
            _proctor(),
            evidencia_id=None,
            proposito="revision de sesion flaggeada",
            ip="10.0.0.5",
            user_agent="pytest",
            timestamp="2026-05-30T10:00:00Z",
        )
        entradas = await audit.list()
        assert len(entradas) == 1
        assert entradas[0].proposito == "revision de sesion flaggeada"
        assert entradas[0].accion == "acceso_evidencia"
        assert await audit.verificar_cadena() is True

    asyncio.run(run())


def test_acceso_evidencia_sin_mfa_no_audita() -> None:
    async def run() -> None:
        sin_mfa = AuthenticatedPrincipal(
            id_institucional="p", email="p@uni.edu", roles=(Rol.PROCTOR,)
        )
        audit = InMemoryAuditRepo()
        svc = ContextualAuthorizationService(InMemoryAssignmentRepo([]), audit)
        with pytest.raises(MfaRequiredError):
            await svc.acceder_a_evidencia(
                sin_mfa,
                evidencia_id=None,
                proposito="x",
                ip="1.1.1.1",
                user_agent="ua",
                timestamp="2026-05-30T10:00:00Z",
            )
        assert await audit.list() == []  # rechazo antes de auditar

    asyncio.run(run())
