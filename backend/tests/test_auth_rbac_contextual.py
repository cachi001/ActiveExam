"""Tests del RBAC CONTEXTUAL puro (C-06, capability contextual-rbac).

Verifica las garantias de aislamiento por contexto (no solo por rol):
- proctor sobre examen NO asignado -> ForbiddenError (403); asignado -> OK.
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


def test_proctor_sobre_examen_no_asignado_rechazado() -> None:
    with pytest.raises(ForbiddenError):
        authorization.autorizar_proctor_sobre_examen(
            _proctor(), exam_id="EX-OTRO", examenes_asignados={"EX-MIO"}
        )


def test_proctor_sobre_examen_asignado_autorizado() -> None:
    # No levanta -> autorizado.
    authorization.autorizar_proctor_sobre_examen(
        _proctor(), exam_id="EX-MIO", examenes_asignados={"EX-MIO", "EX-2"}
    )


def test_revisor_fuera_de_jurisdiccion_rechazado() -> None:
    with pytest.raises(ForbiddenError):
        authorization.autorizar_revisor_sobre_jurisdiccion(
            _revisor("FAC-DERECHO"), jurisdiccion_recurso="FAC-INGENIERIA"
        )


def test_revisor_dentro_de_jurisdiccion_autorizado() -> None:
    authorization.autorizar_revisor_sobre_jurisdiccion(
        _revisor("FAC-DERECHO"), jurisdiccion_recurso="FAC-DERECHO"
    )


def test_proctor_sin_mfa_rechazado_antes_de_contexto() -> None:
    with pytest.raises(MfaRequiredError):
        authorization.autorizar_proctor_sobre_examen(
            _proctor(mfa=False), exam_id="EX-MIO", examenes_asignados={"EX-MIO"}
        )


def test_admin_examenes_no_limitado_por_asignacion() -> None:
    admin = AuthenticatedPrincipal(
        id_institucional="admin-1",
        email="a@uni.edu",
        roles=(Rol.ADMIN_EXAMENES,),
        mfa_satisfecho=True,
    )
    # Admin ve cualquier examen sin estar en una asignacion.
    authorization.autorizar_proctor_sobre_examen(
        admin, exam_id="EX-CUALQUIERA", examenes_asignados=set()
    )


def test_acceso_evidencia_sin_mfa_rechazado() -> None:
    with pytest.raises(MfaRequiredError):
        authorization.puede_acceder_a_evidencia(_proctor(mfa=False))


def test_acceso_evidencia_rol_sin_permiso_rechazado() -> None:
    estudiante = AuthenticatedPrincipal(
        id_institucional="alu-1", email="e@uni.edu", roles=(Rol.ESTUDIANTE,)
    )
    with pytest.raises(ForbiddenError):
        authorization.puede_acceder_a_evidencia(estudiante)
