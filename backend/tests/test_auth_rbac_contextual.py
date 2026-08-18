"""Tests del RBAC CONTEXTUAL puro (C-06 + C-50, capability contextual-rbac).

Verifica las garantias de aislamiento por contexto (no solo por rol):
- proctor con MFA satisfecho -> acceso global a cualquier examen (C-50).
- proctor sin MFA -> MfaRequiredError antes de evaluar el examen.
- el sistema solo controla acceso; no decide sancion (L2.5).

c-76: el rol REVISOR fue eliminado del dominio. Los tests de
``autorizar_revisor_sobre_jurisdiccion`` (scoped a jurisdiccion) se eliminaron
junto con la funcion — ver ``test_c76_eliminacion_rol_revisor.py`` para la
cobertura de la eliminacion.

Dominio puro -> corre sin DB ni red ni libs externas.
"""

from __future__ import annotations

import pytest

from app.domain.auth import authorization
from app.domain.auth.errors import ForbiddenError, MfaRequiredError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol


def _proctor(mfa: bool = True) -> AuthenticatedPrincipal:
    # c-76: el rol PROCTOR fue eliminado; el COORDINADOR absorbe la supervision
    # global. El helper conserva el nombre por continuidad del contrato C-50.
    return AuthenticatedPrincipal(
        username="coordinador-1",
        email="p@uni.edu",
        roles=(Rol.COORDINADOR,),
        mfa_satisfecho=mfa,
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
# Admin — no limitado (sin cambios por C-50)
# ---------------------------------------------------------------------------

def test_admin_sistema_no_limitado_por_asignacion() -> None:
    admin = AuthenticatedPrincipal(
        username="admin-1",
        email="a@uni.edu",
        roles=(Rol.ADMIN_SISTEMA,),
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
        username="alu-1", email="e@uni.edu", roles=(Rol.ESTUDIANTE,)
    )
    with pytest.raises(ForbiddenError):
        authorization.puede_acceder_a_evidencia(estudiante)
