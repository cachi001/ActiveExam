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
    # Gestion academica SIN poder de supervision: carga y administra examenes,
    # materias y comisiones de lo suyo. NO revisa sesiones, NO resuelve casos, NO
    # toca la configuracion del sistema ni la auditoria. Es el rol de quien dicta
    # la materia, no el de quien juzga la integridad de la rendicion — mantener
    # esa separacion es lo que evita que quien pone la nota decida el fraude.
    DOCENTE = "docente"


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
        # El docente administra contenido academico (examenes con sus preguntas y
        # respuestas correctas): es acceso de administracion, exige MFA.
        Rol.DOCENTE,
    }
)

# Roles administrativos de examen (CRUD de Examen, usado por C-07). El docente
# entra aca: cargar y configurar los examenes de su materia es exactamente su
# trabajo. Lo que NO gana por estar aca es supervision ni configuracion del
# sistema — eso vive en CAPABILITY_ROLES, no en esta lista.
ROLES_ADMIN_EXAMEN: frozenset[Rol] = frozenset(
    {Rol.ADMIN_EXAMENES, Rol.ADMIN_SISTEMA, Rol.DOCENTE}
)


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
