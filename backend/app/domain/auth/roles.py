"""Los 4 roles funcionales del sistema y su politica de MFA (PURO).

c-76: "proctor" y "revisor" fueron ELIMINADOS del dominio (absorbidos por
COORDINADOR/TUTOR — ver comentarios inline debajo). c-76-2: "admin_examenes"
y "auditor" fueron ELIMINADOS del dominio (absorbidos por ADMIN_SISTEMA — el
dueño del producto decidio que solo debe existir un rol "Admin"). El conteo
de roles vivos bajo de 8 a 6 (c-76) y de 6 a 4 (c-76-2).

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
    # (Rol "proctor" ELIMINADO en c-76: el COORDINADOR absorbe la supervision
    # global en vivo + el veredicto. Los usuarios con rol "proctor" fueron
    # remapeados a "coordinador" por la migracion 0068. Un claim de token con
    # "proctor" ya no mapea a ningun Rol de dominio: se descarta en silencio,
    # igual que cualquier rol desconocido — ver parse_rol y Q1 del design c-76.)
    # (Rol "revisor" ELIMINADO en c-76: el TUTOR ya supervisa/observa en vivo
    # dentro de su comision y el COORDINADOR absorbe el veredicto terminal
    # (`revisar_sesion`). Los usuarios con rol "revisor" fueron remapeados a
    # "coordinador" por la migracion 0071. Un claim de token con "revisor" ya
    # no mapea a ningun Rol de dominio: se descarta en silencio, igual que
    # cualquier rol desconocido — mismo precedente que "proctor".)
    COORDINADOR = "coordinador"
    # (Rol "admin_examenes" ELIMINADO en c-76-2: la gestion academica que
    # tenia — examenes/materias/comisiones sin poder de supervision — pasa a
    # ser exclusiva de ADMIN_SISTEMA. Los usuarios con rol "admin_examenes"
    # fueron remapeados a "admin_sistema" por la migracion 0074. Un claim de
    # token con "admin_examenes" ya no mapea a ningun Rol de dominio: se
    # descarta en silencio, mismo precedente que "proctor"/"revisor".)
    ADMIN_SISTEMA = "admin_sistema"
    # (Rol "auditor" ELIMINADO en c-76-2: la capacidad ver_auditoria (solo
    # lectura del registro de auditoria) queda exclusiva de ADMIN_SISTEMA —
    # nunca hubo un endpoint real conectado a la capacidad para "auditor"
    # (require_roles(ADMIN_SISTEMA) hardcodeado en audit_router.py), asi que
    # esta eliminacion no le saca acceso real a nadie. Los usuarios con rol
    # "auditor" fueron remapeados a "admin_sistema" por la migracion 0075.
    # Un claim de token con "auditor" ya no mapea a ningun Rol de dominio: se
    # descarta en silencio, mismo precedente que "proctor"/"revisor".)
    # Gestion academica SIN poder de supervision: carga y administra examenes,
    # materias y comisiones de lo suyo. NO revisa sesiones, NO resuelve casos, NO
    # toca la configuracion del sistema ni la auditoria. Es el rol de quien dicta
    # la materia, no el de quien juzga la integridad de la rendicion — mantener
    # esa separacion es lo que evita que quien pone la nota decida el fraude.
    # (Rol "tutor" — antes llamado "docente"; renombrado en migracion 0060.)
    TUTOR = "tutor"


# Roles que EXIGEN MFA: todo el que accede a evidencia o administracion (`03`,
# `08` §Seguridad). El estudiante es el unico exento (solo su propia sesion/datos).
ROLES_CON_MFA: frozenset[Rol] = frozenset(
    {
        Rol.COORDINADOR,
        Rol.ADMIN_SISTEMA,
        # El tutor administra contenido academico (examenes con sus preguntas y
        # respuestas correctas): es acceso de administracion, exige MFA.
        Rol.TUTOR,
    }
)

# Roles administrativos de examen (CRUD de Examen, usado por C-07). El tutor
# entra aca: cargar y configurar los examenes de su materia es exactamente su
# trabajo. Lo que NO gana por estar aca es supervision ni configuracion del
# sistema — eso vive en CAPABILITY_ROLES, no en esta lista.
ROLES_ADMIN_EXAMEN: frozenset[Rol] = frozenset(
    {Rol.ADMIN_SISTEMA, Rol.TUTOR}
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
