"""Tests del RBAC CONTEXTUAL puro (C-06 + C-50, capability contextual-rbac).

Verifica las garantias de aislamiento por contexto (no solo por rol):
- proctor con MFA satisfecho -> acceso global a cualquier examen (C-50).
- proctor sin MFA -> MfaRequiredError antes de evaluar el examen.
- revisor fuera de su jurisdiccion -> ForbiddenError (403); dentro -> OK.
- el sistema solo controla acceso; no decide sancion (L2.5).

Dominio puro -> corre sin DB ni red ni libs externas.
"""

from __future__ import annotations

import pytest

from app.domain.auth import authorization
from app.domain.auth.errors import ForbiddenError, MfaRequiredError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol


def _proctor(mfa: bool = True) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id_institucional="proctor-1",
        email="p@uni.edu",
        roles=(Rol.PROCTOR,),
        mfa_satisfecho=mfa,
    )


def _revisor(jurisdiccion: str, mfa: bool = True) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        id_institucional="revisor-1",
        email="r@uni.edu",
        roles=(Rol.REVISOR,),
        mfa_satisfecho=mfa,
        jurisdiccion=jurisdiccion,
    )


# ---------------------------------------------------------------------------
# Proctor — alcance global (C-50)
# ---------------------------------------------------------------------------

def test_proctor_global_autorizado_sin_asignacion() -> None:
    """Proctor con MFA sobre cualquier exam_id -> no levanta excepcion (alcance global)."""
    # No levanta -> autorizado sobre cualquier examen, sin necesidad de asignacion.
    authorization.autorizar_proctor(_proctor())


def test_proctor_sin_mfa_rechazado() -> None:
    """Proctor sin MFA satisfecho -> MfaRequiredError antes de conceder acceso."""
    with pytest.raises(MfaRequiredError):
        authorization.autorizar_proctor(_proctor(mfa=False))


# ---------------------------------------------------------------------------
# Revisor — scoped a jurisdiccion (sin cambios por C-50)
# ---------------------------------------------------------------------------

def test_revisor_fuera_de_jurisdiccion_rechazado() -> None:
    with pytest.raises(ForbiddenError):
        authorization.autorizar_revisor_sobre_jurisdiccion(
            _revisor("FAC-DERECHO"), jurisdiccion_recurso="FAC-INGENIERIA"
        )


def test_revisor_dentro_de_jurisdiccion_autorizado() -> None:
    authorization.autorizar_revisor_sobre_jurisdiccion(
        _revisor("FAC-DERECHO"), jurisdiccion_recurso="FAC-DERECHO"
    )


# ---------------------------------------------------------------------------
# Admin — no limitado (sin cambios por C-50)
# ---------------------------------------------------------------------------

def test_admin_examenes_no_limitado_por_asignacion() -> None:
    admin = AuthenticatedPrincipal(
        id_institucional="admin-1",
        email="a@uni.edu",
        roles=(Rol.ADMIN_EXAMENES,),
        mfa_satisfecho=True,
    )
    # Admin ve cualquier examen — usa la nueva firma sin examenes_asignados.
    authorization.autorizar_proctor(admin)


# ---------------------------------------------------------------------------
# Evidencia — gate sin cambios
# ---------------------------------------------------------------------------

def test_acceso_evidencia_sin_mfa_rechazado() -> None:
    with pytest.raises(MfaRequiredError):
        authorization.puede_acceder_a_evidencia(_proctor(mfa=False))


def test_acceso_evidencia_rol_sin_permiso_rechazado() -> None:
    estudiante = AuthenticatedPrincipal(
        id_institucional="alu-1", email="e@uni.edu", roles=(Rol.ESTUDIANTE,)
    )
    with pytest.raises(ForbiddenError):
        authorization.puede_acceder_a_evidencia(estudiante)
