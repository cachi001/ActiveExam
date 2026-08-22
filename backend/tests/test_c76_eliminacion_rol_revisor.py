"""Tests RBAC de la eliminacion del rol REVISOR (c-76, post-Tarea 7 — CRITICO).

El rol ``revisor`` fue ELIMINADO del dominio: el TUTOR ya supervisa/observa
la sesion en vivo dentro de su comision (``supervisar_vivo``, C-76 bloques
6/8) y el COORDINADOR absorbe el veredicto terminal (``revisar_sesion`` —
aprobar/anular). Un rol REVISOR separado quedaba redundante: coordinador ya
cubria exactamente el mismo acto, sin el acotamiento por jurisdiccion que
distinguia al revisor.

Garantias que este modulo bloquea (dominio puro — sin DB ni red), mirror del
precedente exacto de ``test_c76_eliminacion_rol_proctor.py``:

1. ``Rol`` ya no expone ``REVISOR``; ``parse_rol("revisor")`` -> ``None``.
2. ``revisar_sesion`` = {COORDINADOR, ADMIN_SISTEMA}, sin revisor.
3. ``supervisar_vivo`` = {TUTOR, COORDINADOR, ADMIN_SISTEMA}, sin revisor.
4. Un claim de token con rol ``"revisor"`` NO mapea a ningun ``Rol`` de
   dominio: se descarta en silencio, igual que "proctor" (mismo precedente).
5. ``autorizar_supervision_vivo_sobre_sesion`` ya no exime a REVISOR: el
   exemption set quedo en {COORDINADOR, ADMIN_SISTEMA}.
"""

from __future__ import annotations

import pytest

from app.domain.auth.authorization import autorizar_supervision_vivo_sobre_sesion
from app.domain.auth.capabilities import CAPABILITY_ROLES, tiene_capacidad
from app.domain.auth.errors import ForbiddenError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol, parse_rol
from app.domain.auth.token import TokenPolicy

_ISSUER = "activeexam-auth"
_AUD = "proctoring-api"


def _policy() -> TokenPolicy:
    return TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)


def _claims(roles: list[str]) -> dict:
    return {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "sub-1",
        "preferred_username": "u1",
        "email": "u1@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }


def _principal(*roles: Rol) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(username="u1", email="u1@uni.edu", roles=roles)


# ---------------------------------------------------------------------------
# 1. El enum ya no tiene REVISOR
# ---------------------------------------------------------------------------

def test_rol_no_expone_revisor() -> None:
    """``Rol.REVISOR`` fue eliminado: acceder a el es AttributeError."""
    assert not hasattr(Rol, "REVISOR")


def test_valores_del_enum_no_incluyen_revisor() -> None:
    """El literal 'revisor' no es un valor valido del enum ``Rol``."""
    assert "revisor" not in {r.value for r in Rol}


@pytest.mark.parametrize("desconocido", ["revisor", "supervisor", "rol-inexistente"])
def test_parse_rol_descarta_revisor_y_desconocidos(desconocido: str) -> None:
    """``parse_rol`` devuelve None para 'revisor' y cualquier rol desconocido."""
    assert parse_rol(desconocido) is None


def test_parse_rol_sigue_mapeando_roles_vivos() -> None:
    """Triangulacion: los roles vivos siguen mapeando (no rompimos parse_rol)."""
    assert parse_rol("coordinador") is Rol.COORDINADOR
    assert parse_rol("tutor") is Rol.TUTOR
    assert parse_rol("admin_sistema") is Rol.ADMIN_SISTEMA


# ---------------------------------------------------------------------------
# 2. revisar_sesion remapeado (sin revisor)
# ---------------------------------------------------------------------------

def test_revisar_sesion_es_coordinador_admin_sin_revisor() -> None:
    """``revisar_sesion`` = {COORDINADOR, ADMIN_SISTEMA}."""
    assert CAPABILITY_ROLES["revisar_sesion"] == frozenset(
        {Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


@pytest.mark.parametrize("rol", [Rol.COORDINADOR, Rol.ADMIN_SISTEMA])
def test_roles_vivos_conservan_revisar_sesion(rol: Rol) -> None:
    assert tiene_capacidad(rol, "revisar_sesion") is True


@pytest.mark.parametrize("rol", [Rol.ESTUDIANTE, Rol.TUTOR])
def test_roles_sin_revisar_sesion_siguen_sin_ella(rol: Rol) -> None:
    """Triangulacion: quien nunca tuvo el veredicto sigue sin tenerlo."""
    assert tiene_capacidad(rol, "revisar_sesion") is False


# ---------------------------------------------------------------------------
# 3. supervisar_vivo remapeado (sin revisor)
# ---------------------------------------------------------------------------

def test_supervisar_vivo_es_tutor_coordinador_admin_sin_revisor() -> None:
    """``supervisar_vivo`` = {TUTOR, COORDINADOR, ADMIN_SISTEMA}."""
    assert CAPABILITY_ROLES["supervisar_vivo"] == frozenset(
        {Rol.TUTOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA}
    )


@pytest.mark.parametrize("rol", [Rol.TUTOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA])
def test_roles_supervisores_conservan_supervisar_vivo(rol: Rol) -> None:
    assert tiene_capacidad(rol, "supervisar_vivo") is True


# ---------------------------------------------------------------------------
# 4. Claim colgante 'revisor' en el token -> ningun Rol de dominio
# ---------------------------------------------------------------------------

def test_claim_revisor_no_mapea_a_ningun_rol() -> None:
    """Un token con rol 'revisor' produce un principal SIN roles de dominio."""
    principal = _policy().principal_desde_claims(_claims(["revisor"]))
    assert principal.roles == ()


def test_claim_revisor_junto_a_coordinador_solo_conserva_coordinador() -> None:
    """Triangulacion: 'revisor' se descarta pero los roles vivos del claim quedan."""
    principal = _policy().principal_desde_claims(_claims(["revisor", "coordinador"]))
    assert Rol.COORDINADOR in principal.roles
    assert principal.roles == (Rol.COORDINADOR,)


# ---------------------------------------------------------------------------
# 5. autorizar_supervision_vivo_sobre_sesion pierde la exencion de REVISOR
#    (c-79: y TAMBIEN la de COORDINADOR, que dejo de ser institucional)
# ---------------------------------------------------------------------------
#
# No existe forma de construir hoy un principal con Rol.REVISOR (el rol no
# existe mas en el dominio), asi que no hay ningun path de codigo vivo que
# pueda ejercer la vieja exencion. c-79: el COORDINADOR tambien dejo de estar
# exento — antes Q5 del design c-76 lo declaraba institucional; ahora queda
# acotado por pertenencia (materia_coordinador) igual que el TUTOR (comision_
# tutor), y el caller (router) resuelve cual de los dos chequear segun el rol.
# El exemption set en el dominio quedo reducido a {ADMIN_SISTEMA} solamente.

def test_coordinador_no_esta_exento_de_pertenencia_en_supervision_vivo() -> None:
    """c-79: el coordinador YA NO es institucional — sin pertenencia, se rechaza."""
    coordinador = _principal(Rol.COORDINADOR)
    with pytest.raises(ForbiddenError):
        autorizar_supervision_vivo_sobre_sesion(coordinador, tiene_pertenencia=False)


def test_coordinador_con_pertenencia_autorizado_en_supervision_vivo() -> None:
    """Triangulación: con pertenencia (coordina la materia), el coordinador pasa."""
    coordinador = _principal(Rol.COORDINADOR)
    autorizar_supervision_vivo_sobre_sesion(coordinador, tiene_pertenencia=True)


def test_admin_sistema_exento_de_pertenencia_en_supervision_vivo() -> None:
    admin = _principal(Rol.ADMIN_SISTEMA)
    autorizar_supervision_vivo_sobre_sesion(admin, tiene_pertenencia=False)


def test_tutor_sin_dueno_identificable_sigue_rechazado() -> None:
    """Triangulacion: el TUTOR sigue exactamente igual de acotado que antes."""
    tutor = _principal(Rol.TUTOR)
    with pytest.raises(ForbiddenError):
        autorizar_supervision_vivo_sobre_sesion(tutor, tiene_pertenencia=False)


def test_tutor_dueno_de_la_sesion_autorizado() -> None:
    tutor = AuthenticatedPrincipal(
        username="tutor-1", email="t@uni.edu", roles=(Rol.TUTOR,), subject="tutor-1"
    )
    # No levanta -> el tutor es dueño de la sesion (comision_tutor lo confirmó).
    autorizar_supervision_vivo_sobre_sesion(tutor, tiene_pertenencia=True)
