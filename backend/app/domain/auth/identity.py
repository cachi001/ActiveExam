"""Principal autenticado: claims YA VALIDADOS como value object puro (PURO).

``AuthenticatedPrincipal`` es lo que el dominio recibe DESPUES de que la
infraestructura valido la firma/expiracion/audiencia del JWT (C-06 D2). Aqui no
hay criptografia: solo el resultado validado, en forma de dato de dominio sobre el
que se decide la autorizacion contextual.

Campos relevantes para el RBAC contextual (`03` §RBAC):
- ``id_institucional``: clave del JIT provisioning (`04` §Usuario).
- ``roles``: roles funcionales del principal (ya filtrados a ``Rol`` validos).
- ``mfa_satisfecho``: el token refleja el segundo factor (D4 MFA enforcement).
- ``jurisdiccion``: scope del revisor (atributo federado, `03`).
- ``examenes_asignados``: NO viaja en el token; el RBAC del proctor lo resuelve
  contra la entidad ``Asignacion`` (C-05) en la capa de aplicacion. Se modela
  como parametro de la decision de autorizacion, no como campo del principal.

Sin framework ni infraestructura (D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.auth.roles import Rol, rol_exige_mfa


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Identidad ya autenticada (claims validados). Inmutable."""

    id_institucional: str
    email: str
    roles: tuple[Rol, ...] = ()
    mfa_satisfecho: bool = False
    jurisdiccion: str | None = None
    subject: str | None = None  # ``sub`` del token (opaco del IdP)
    attrs_federados: dict[str, str] = field(default_factory=dict)

    def tiene_rol(self, rol: Rol) -> bool:
        """``True`` si el principal posee el rol indicado."""
        return rol in self.roles

    def tiene_algun_rol(self, roles: frozenset[Rol] | set[Rol] | tuple[Rol, ...]) -> bool:
        """``True`` si el principal posee al menos uno de los roles indicados."""
        return any(r in self.roles for r in roles)

    @property
    def exige_mfa(self) -> bool:
        """``True`` si ALGUNO de los roles del principal exige segundo factor.

        Si el principal porta un rol con acceso a evidencia/administracion, debe
        haber satisfecho MFA para operar (la verificacion concreta la hace
        ``authorization.verificar_mfa``)."""
        return any(rol_exige_mfa(r) for r in self.roles)
