"""Los 7 roles funcionales del sistema y su politica de MFA (PURO).

Fuente: `03` §RBAC. Codifica como dato de dominio (no como string suelto):
- el conjunto canonico de roles validos,
- cuales exigen MFA obligatorio (acceso a evidencia / administracion, `03`/`08`),
- el rol "estudiante", unico sin MFA (solo accede a su propia sesion / sus datos).

Sin framework ni infraestructura (D1). Estos son enums/constantes de negocio.
"""

from __future__ import annotations

import enum


class Rol(str, enum.Enum):
    """Rol funcional del sistema (`03` §RBAC). Hereda de ``str`` para serializar
    directo en claims/JSON sin perder el control de los valores validos."""

    ESTUDIANTE = "estudiante"
    PROCTOR = "proctor"
    REVISOR = "revisor"
    COORDINADOR = "coordinador"
    ADMIN_EXAMENES = "admin_examenes"
    ADMIN_SISTEMA = "admin_sistema"
    AUDITOR = "auditor"


# Roles que EXIGEN MFA: todo el que accede a evidencia o administracion (`03`,
# `08` §Seguridad). El estudiante es el unico exento (solo su propia sesion/datos).
ROLES_CON_MFA: frozenset[Rol] = frozenset(
    {
        Rol.PROCTOR,
        Rol.REVISOR,
        Rol.COORDINADOR,
        Rol.ADMIN_EXAMENES,
        Rol.ADMIN_SISTEMA,
        Rol.AUDITOR,
    }
)

# Roles administrativos de examen (admin-only para CRUD de Examen, usado por C-07).
ROLES_ADMIN_EXAMEN: frozenset[Rol] = frozenset({Rol.ADMIN_EXAMENES, Rol.ADMIN_SISTEMA})


def parse_rol(valor: str) -> Rol | None:
    """Convierte un string de claim a ``Rol``, o ``None`` si no es un rol valido.

    Tolerante a roles desconocidos en el token (p. ej. roles internos de Keycloak):
    se descartan sin romper, no se mapean a un rol del dominio."""
    try:
        return Rol(valor)
    except ValueError:
        return None


def rol_exige_mfa(rol: Rol) -> bool:
    """``True`` si el rol exige segundo factor para operar (`03`/`08`)."""
    return rol in ROLES_CON_MFA
