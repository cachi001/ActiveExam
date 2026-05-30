"""RBAC CONTEXTUAL y MFA enforcement como funciones puras (PURO, C-06 D3+D4).

Estas son las reglas de autorizacion del proctoring. NO son RBAC plano: tener el
rol no basta, se evalua el CONTEXTO (`03` §RBAC):

- **Proctor** -> solo exámenes en su ``Asignacion`` (C-05). El conjunto de
  exámenes asignados lo resuelve la capa de aplicacion contra el repositorio y se
  pasa como parametro; el dominio decide con ese dato (sin tocar infraestructura).
- **Revisor** -> solo sesiones de su ``jurisdiccion``.
- **MFA** -> un rol con acceso a evidencia/administracion debe haber satisfecho el
  segundo factor (D4); si no, se rechaza ANTES de evaluar el contexto.

El sistema NUNCA sanciona (L2.5): estas funciones solo CONTROLAN ACCESO; no
deciden casos disciplinarios. Cualquier violacion levanta un error de dominio
(``ForbiddenError``/``MfaRequiredError``/``UnauthenticatedError``), que la
presentacion traduce a 403/401.

Sin framework ni infraestructura (D1) -> testeable sin DB ni red.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.auth.errors import (
    ForbiddenError,
    MfaRequiredError,
    UnauthenticatedError,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol, rol_exige_mfa


def requiere_principal(principal: AuthenticatedPrincipal | None) -> AuthenticatedPrincipal:
    """Exige un principal autenticado; si es ``None`` levanta 401."""
    if principal is None:
        raise UnauthenticatedError("No hay un principal autenticado.")
    return principal


def verificar_mfa(principal: AuthenticatedPrincipal) -> None:
    """Exige el segundo factor si ALGUN rol del principal lo requiere (D4).

    Se evalua ANTES del contexto: un proctor sin MFA no debe siquiera llegar a la
    comprobacion de asignacion. El estudiante (sin rol con MFA) pasa de largo."""
    if principal.exige_mfa and not principal.mfa_satisfecho:
        raise MfaRequiredError(
            "El rol exige segundo factor (MFA) no satisfecho en el token."
        )


def exigir_roles(
    principal: AuthenticatedPrincipal,
    roles_permitidos: Iterable[Rol],
) -> None:
    """Exige que el principal tenga AL MENOS UNO de los roles permitidos (403)."""
    permitidos = frozenset(roles_permitidos)
    if not principal.tiene_algun_rol(permitidos):
        raise ForbiddenError(
            "El principal no posee ninguno de los roles requeridos."
        )


def autorizar_proctor_sobre_examen(
    principal: AuthenticatedPrincipal,
    exam_id: str,
    examenes_asignados: Iterable[str],
) -> None:
    """RBAC contextual del PROCTOR (D3): solo exámenes en su Asignacion (C-05).

    ``examenes_asignados`` lo provee la capa de aplicacion (lookup en el
    ``AssignmentRepository``); aqui solo se decide. Un proctor sobre un examen NO
    asignado -> 403, aunque el rol proctor sea valido.

    Un rol superior con vision global de exámenes (admin de exámenes / del sistema)
    no esta limitado por asignacion: se autoriza por rol."""
    if principal.tiene_algun_rol({Rol.ADMIN_EXAMENES, Rol.ADMIN_SISTEMA}):
        return
    if not principal.tiene_rol(Rol.PROCTOR):
        raise ForbiddenError("Se requiere rol proctor (o admin) para observar el examen.")
    verificar_mfa(principal)
    if exam_id not in set(examenes_asignados):
        raise ForbiddenError(
            "El proctor no tiene asignado este examen (aislamiento contextual, `03`)."
        )


def autorizar_revisor_sobre_jurisdiccion(
    principal: AuthenticatedPrincipal,
    jurisdiccion_recurso: str,
) -> None:
    """RBAC contextual del REVISOR (D3): solo su jurisdiccion.

    Un revisor cuya ``jurisdiccion`` no coincide con la del recurso -> 403. Un
    coordinador/admin no esta limitado por jurisdiccion (escala/operacion global)."""
    if principal.tiene_algun_rol({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}):
        verificar_mfa(principal)
        return
    if not principal.tiene_rol(Rol.REVISOR):
        raise ForbiddenError("Se requiere rol revisor para la cola de revision.")
    verificar_mfa(principal)
    if principal.jurisdiccion is None or principal.jurisdiccion != jurisdiccion_recurso:
        raise ForbiddenError(
            "El revisor no puede cruzar su jurisdiccion (aislamiento contextual, `03`)."
        )


def puede_acceder_a_evidencia(principal: AuthenticatedPrincipal) -> None:
    """Gate de acceso a EVIDENCIA: exige rol con acceso + MFA satisfecho (D4).

    El registro del proposito declarado en el audit log lo hace la capa de
    aplicacion (C-05 ``AuditLogRepository``); aqui solo se decide el acceso. El
    sistema no sanciona (L2.5): esto controla acceso, no decide el caso."""
    roles_evidencia = {
        Rol.PROCTOR,
        Rol.REVISOR,
        Rol.COORDINADOR,
        Rol.ADMIN_SISTEMA,
        Rol.AUDITOR,
    }
    if not principal.tiene_algun_rol(roles_evidencia):
        raise ForbiddenError("El rol no tiene acceso a evidencia (`03`).")
    if not principal.mfa_satisfecho:
        raise MfaRequiredError("El acceso a evidencia exige MFA (`03`/`08`).")
