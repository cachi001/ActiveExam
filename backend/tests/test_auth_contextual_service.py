"""Tests del servicio de autorizacion contextual con repositorios (C-06 + C-50, D3).

Verifica que el proctor tiene alcance global (C-50): ``autorizar_proctor`` ya no
resuelve asignaciones y el proctor con MFA es autorizado sin necesidad de datos
en repositorio. El acceso a evidencia sigue registrando el PROPOSITO en el audit
log (sin sancionar — L2.5).

Repositorios EN MEMORIA que implementan los puertos reales (sin mock de DB).
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.auth.authorization_service import ContextualAuthorizationService
from app.domain.audit_chain import AuditEntry, construir_cadena, verificar_cadena
from app.domain.auth.errors import MfaRequiredError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.repositories.ports import AuditLogRepository


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


# ---------------------------------------------------------------------------
# Proctor — alcance global (C-50)
# ---------------------------------------------------------------------------

def test_proctor_global_autorizado_por_servicio() -> None:
    """Proctor con MFA -> servicio no levanta excepcion sin necesitar repositorio de asignaciones."""
    audit = InMemoryAuditRepo()
    svc = ContextualAuthorizationService(audit)
    # Llamada sincrona — no levanta
    svc.autorizar_proctor(_proctor(), exam_id="EX-CUALQUIERA")


# ---------------------------------------------------------------------------
# Evidencia — gate con audit log (sin cambios por C-50)
# ---------------------------------------------------------------------------

def test_acceso_evidencia_registra_proposito_en_audit() -> None:
    async def run() -> None:
        audit = InMemoryAuditRepo()
        svc = ContextualAuthorizationService(audit)
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
        svc = ContextualAuthorizationService(audit)
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
