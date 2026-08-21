"""RBAC CONTEXTUAL y MFA enforcement como funciones puras (PURO, C-06 D3+D4).

Estas son las reglas de autorizacion del proctoring. NO son RBAC plano: tener el
rol no basta, se evalua el CONTEXTO (`03` §RBAC):

- **Proctor** -> alcance GLOBAL: puede observar TODOS los exámenes activos (C-50).
  El parámetro ``examenes_asignados`` fue eliminado (D1-C50); basta con el rol
  PROCTOR y MFA satisfecho. Un rol superior (admin) también pasa.
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

from app.domain.auth.capabilities import tiene_capacidad
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


def exigir_capacidad(principal: AuthenticatedPrincipal, capacidad: str) -> None:
    """Exige que el principal tenga la ``capacidad`` (c-71 slice 2, D8).

    Config-driven: la capacidad se resuelve contra ``CAPABILITY_ROLES``
    (dominio de ``capabilities``), no contra una lista de roles hardcodeada
    en el endpoint. Reasignar la capacidad a otro rol es un cambio de ese
    mapa, no de este guard."""
    if not any(tiene_capacidad(rol, capacidad) for rol in principal.roles):
        raise ForbiddenError(
            f"El principal no posee la capacidad {capacidad!r}."
        )


def autorizar_proctor(
    principal: AuthenticatedPrincipal,
) -> None:
    """RBAC de supervision GLOBAL en vivo (C-50, D1).

    c-76: el rol PROCTOR fue eliminado; el COORDINADOR absorbe la supervision
    global. Basta con el rol COORDINADOR y MFA satisfecho. Un rol superior
    (ADMIN_SISTEMA) tambien pasa sin requerir MFA adicional.

    NOTA (c-76): esta funcion NO esta cableada a ningun endpoint vivo — la
    supervision se gatea por capacidad (`supervisar_vivo`) en el router de
    proctoring. Se conserva por el contrato C-50 (dominio + servicio + tests).
    El rol se remapeo PROCTOR -> COORDINADOR por el default aprobado de c-76.

    La relajacion del minimo privilegio queda justificada en el DPIA (C-01).
    El sistema NUNCA sanciona (L2.5): esta funcion solo controla acceso."""
    if principal.tiene_rol(Rol.ADMIN_SISTEMA):
        return
    if not principal.tiene_rol(Rol.COORDINADOR):
        raise ForbiddenError("Se requiere rol coordinador (o admin) para observar el examen.")
    verificar_mfa(principal)


def puede_acceder_a_evidencia(principal: AuthenticatedPrincipal) -> None:
    """Gate de acceso a EVIDENCIA: exige rol con acceso + MFA satisfecho (D4).

    El registro del proposito declarado en el audit log lo hace la capa de
    aplicacion (C-05 ``AuditLogRepository``); aqui solo se decide el acceso. El
    sistema no sanciona (L2.5): esto controla acceso, no decide el caso."""
    # c-76: PROCTOR y REVISOR eliminados; el COORDINADOR (ya presente) cubre el
    # acceso a evidencia que tenian ambos. c-76-2: AUDITOR eliminado, absorbido
    # por ADMIN_SISTEMA. Sin duplicado — el set solo se achica.
    roles_evidencia = {
        Rol.COORDINADOR,
        Rol.ADMIN_SISTEMA,
    }
    if not principal.tiene_algun_rol(roles_evidencia):
        raise ForbiddenError("El rol no tiene acceso a evidencia (`03`).")
    if not principal.mfa_satisfecho:
        raise MfaRequiredError("El acceso a evidencia exige MFA (`03`/`08`).")


# Roles con alcance institucional: NO estan limitados por la pertenencia a una
# comision. Un coordinador o un admin operan sobre cualquier examen por diseno
# (escala/operacion global); el docente, no.
_ROLES_SIN_LIMITE_DE_PERTENENCIA: frozenset[Rol] = frozenset(
    {Rol.ADMIN_SISTEMA, Rol.COORDINADOR}
)


def autorizar_docente_sobre_examen(
    principal: AuthenticatedPrincipal,
    docente_id_del_examen: str | None,
) -> None:
    """Pertenencia del DOCENTE sobre un examen (C-73 §9).

    El rol DOCENTE administra "lo suyo": los examenes de las comisiones que tiene a
    cargo. Hasta C-73 esa regla estaba ESCRITA (ver el comentario de ``Rol.DOCENTE``
    en ``roles.py``) pero no se aplicaba, porque los guards eran por CAPACIDAD
    (``gestionar_academico``) y no habia contra que validar la propiedad: la comision
    no tenia docente. Con ``comision.docente_id`` ya se puede.

    Por que importa: sin esta validacion, un docente puede fijar el destino Moodle del
    examen de OTRA comision y mandar esa nota a la libreta que quiera. No es un
    permiso de mas; es escribir en la libreta de una materia ajena.

    ``docente_id_del_examen`` es la derivacion examen -> comision -> docente. ``None``
    (examen sin comision, o comision sin docente) NO habilita al docente: si no hay
    dueno, no puede reclamarlo — solo pasan los roles de alcance institucional.

    No decide nada sobre integridad academica (L2.5): esto es control de acceso."""
    if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
        return
    if not principal.tiene_rol(Rol.TUTOR):
        raise ForbiddenError("Se requiere rol tutor (o alcance institucional).")
    if docente_id_del_examen is None:
        raise ForbiddenError(
            "El examen no tiene docente a cargo: solo un rol institucional puede operarlo."
        )
    if principal.subject != docente_id_del_examen:
        raise ForbiddenError("El examen pertenece a la comision de otro docente.")


def autorizar_docente_sobre_materia(
    principal: AuthenticatedPrincipal,
    es_docente_de_alguna_comision_de_la_materia: bool,
) -> None:
    """Pertenencia del DOCENTE sobre el banco de preguntas de una MATERIA (C-74).

    El banco es compartido por TODAS las comisiones de la materia (no se re-sube
    por comisión) — por diseño, cualquier docente que dicte AL MENOS una comisión
    de la materia puede operar su banco. La membresía se resuelve consultando
    "¿el principal dicta alguna comisión de esta materia?" (booleano, ya evaluado
    por el caller contra la DB) — NUNCA comparando contra un docente arbitrario de
    la materia como hacía ``docente_de_materia`` + comparación por igualdad: eso
    rechazaba con falso negativo a un docente real que solo dicta una comisión
    distinta de la que la query devolvía primero (bug real, C-74 post-cierre)."""
    if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
        return
    if not principal.tiene_rol(Rol.TUTOR):
        raise ForbiddenError("Se requiere rol tutor (o alcance institucional).")
    if not es_docente_de_alguna_comision_de_la_materia:
        raise ForbiddenError("La materia no tiene ninguna comisión a cargo de este docente.")


def autorizar_supervision_vivo_sobre_sesion(
    principal: AuthenticatedPrincipal,
    docente_id_de_la_sesion: str | None,
) -> None:
    """Pertenencia del TUTOR sobre la supervision en vivo de una sesion (C-76 D2).

    ``supervisar_vivo`` habilita el ROL (COORDINADOR/ADMIN_SISTEMA/TUTOR, tras
    eliminarse tambien REVISOR — c-76), pero el TUTOR queda ademas ACOTADO por
    pertenencia: solo ve/opera sesiones de examenes cuya comision tiene a SU
    usuario como ``docente_id`` (asignar_docente, C-73 §9).
    COORDINADOR/ADMIN_SISTEMA son de alcance institucional (Q5 del design c-76:
    el coordinador es global) y no se acotan.

    ``docente_id_de_la_sesion`` es la derivacion sesion -> examen_contenido ->
    comision -> docente_id. ``None`` (sesion 'test' sin examen vinculado, examen
    sin comision, o comision sin docente) NO habilita al tutor: sin dueño
    identificable, solo pasan los roles institucionales.

    No decide nada sobre integridad academica (L2.5): esto es control de acceso."""
    if principal.tiene_algun_rol({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}):
        return
    if not principal.tiene_rol(Rol.TUTOR):
        # Capability gate ya exige supervisar_vivo antes de llegar acá; este caso
        # es defensivo (rol desconocido con la capacidad de otra forma).
        raise ForbiddenError("Se requiere rol tutor (o alcance institucional).")
    if docente_id_de_la_sesion is None:
        raise ForbiddenError(
            "La sesion no tiene un docente a cargo identificable: "
            "solo un rol institucional puede operarla."
        )
    if principal.subject != docente_id_de_la_sesion:
        raise ForbiddenError("La sesion pertenece a la comision de otro docente.")


def autorizar_docente_sobre_comision(
    principal: AuthenticatedPrincipal,
    docente_id_de_la_comision: str | None,
) -> None:
    """Pertenencia del DOCENTE sobre una COMISIÓN puntual (C-74 post-cierre).

    Distinto de ``autorizar_docente_sobre_materia``: el banco es materia-wide,
    pero crear un examen APUNTA a una comisión concreta — un docente que dicta la
    Comisión 2 de una materia no puede crear un examen para la Comisión 1 de esa
    misma materia (comisión de otro docente) solo porque comparten materia y banco.
    Sin este chequeo, ``crear-desde-banco`` solo validaba pertenencia a la MATERIA
    y dejaba pasar cualquier ``comision_id`` de esa materia (bug real)."""
    if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
        return
    if not principal.tiene_rol(Rol.TUTOR):
        raise ForbiddenError("Se requiere rol tutor (o alcance institucional).")
    if docente_id_de_la_comision is None:
        raise ForbiddenError(
            "La comisión no tiene docente a cargo: solo un rol institucional puede operarla."
        )
    if principal.subject != docente_id_de_la_comision:
        raise ForbiddenError("La comisión pertenece a otro docente.")


def principal_es_dueno_de_sesion(
    principal: AuthenticatedPrincipal,
    alumno_idnumber: str | None,
    alumno_email: str | None,
) -> bool:
    """True si la sesion pertenece al ALUMNO autenticado (H1, IDOR).

    Los endpoints propios del alumno durante su examen (biometria, eventos,
    chat, pausas, respuestas, finalizar) son suyos: solo el dueño de la sesion
    puede operarla. La identidad del alumno se persiste server-side al CREAR
    la sesion (``alumno_idnumber``/``alumno_email`` desde el JWT), asi que aca
    se compara contra el principal del request en vez de confiar en el
    ``session_id`` del path (que cualquiera con el UUID puede adivinar/repetir).

    - Coincide por ``username`` O por ``email`` -> es el dueño.
    - Sesion SIN identidad almacenada (legacy/modo 'test' previo a la
      persistencia de identidad) -> se permite: no hay a quien atribuirla y no
      expone datos de nadie. Toda sesion nueva guarda identidad, asi que este
      caso no aplica al flujo normal de examen.

    Recibe los campos primitivos (no el modelo ORM) para mantener este modulo
    puro (D1) — el caller (repositorio/servicio) hace la traduccion.
    """
    if not alumno_idnumber and not alumno_email:
        return True
    if alumno_idnumber and principal.username and alumno_idnumber == principal.username:
        return True
    if alumno_email and principal.email and alumno_email == principal.email:
        return True
    return False


def autorizar_dueno_o_supervision_vivo_sobre_sesion(
    principal: AuthenticatedPrincipal,
    alumno_idnumber: str | None,
    alumno_email: str | None,
    docente_id_de_la_sesion: str | None,
) -> None:
    """Acceso a un recurso de sesion (chat, pausas) para el DUEÑO o quien supervisa.

    A diferencia de ``autorizar_supervision_vivo_sobre_sesion`` (que exige rol de
    supervision), este guard tambien deja pasar al alumno dueño de la sesion —
    varios recursos (chat, listado de pausas) son compartidos entre el alumno que
    rinde y el tutor/coordinador que lo supervisa. Si el principal NO es ni el
    dueño ni tiene supervision valida sobre esa sesion puntual, se rechaza (H1,
    IDOR): sin esto, cualquier alumno autenticado podia leer/escribir en la
    sesion de OTRO alumno con solo conocer el ``session_id``.
    """
    if principal_es_dueno_de_sesion(principal, alumno_idnumber, alumno_email):
        return
    autorizar_supervision_vivo_sobre_sesion(principal, docente_id_de_la_sesion)
