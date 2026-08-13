"""JIT provisioning de cuentas alumno desde un launch LTI validado (C-75, sección 5).

Tras un launch LTI válido (ver ``launch_validation.validar_launch``), este módulo:

1. Construye la clave ``id_institucional`` = ``lti:{deployment_id}:{sub}`` (design D1).
   El namespacing por deployment evita colisiones entre Moodles que reutilicen el
   mismo ``sub`` numérico.

2. Si el ``id_institucional`` ya existe → devuelve el usuario existente (idempotente).

3. Si no existe → crea el usuario con:
   - ``roles=["estudiante"]``  (rol canónico del sistema — ver ``Rol.ESTUDIANTE``;
     la spec usa "alumno" como sinónimo informal pero el enum usa "estudiante")
   - ``auth_provider="lti"``
   - ``debe_cambiar_password=True``
   - ``nombre``/``email`` tomados EXCLUSIVAMENTE de los claims del ``id_token``
     ya validado (nunca de un body adicional que el cliente pudiera manipular;
     regla de dominio #6 + spec lti-jit-provisioning §"El cliente no puede
     inyectar datos de identidad").
   - ``password_hash`` aleatorio no comunicado (patrón de clave temporal de
     ``POST /users`` / C-61).

4. Si el deployment tiene ``comision_id`` configurado → matricula al alumno en
   esa comisión (idempotente: ``ON CONFLICT DO NOTHING`` vía UNIQUE constraint).
   Si no hay ``comision_id`` → crea/loguea igual pero sin matricular.

DOMINIO CRÍTICO (Auth): esta función es el núcleo de la superficie de auth pública.
Falla cerrado: cualquier claim malformado o ausente eleva excepción — NO crea
un usuario parcial. Solo se ejecuta DESPUÉS de que ``validar_launch`` haya
comprobado firma, nonce, aud y exp.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text as sa_text

from app.application.lti.launch_validation import (
    CLAIM_DEPLOYMENT_ID,
    LaunchInvalidoError,
    LaunchValidado,
)
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel
from app.infrastructure.persistence.models.transactional import UsuarioModel

# Prefijo de ``id_institucional`` para usuarios provisionados vía LTI (design D1).
_LTI_PREFIX = "lti"


def _id_institucional_lti(deployment_id: str, sub: str) -> str:
    """Construye la clave única del usuario en el espacio LTI.

    Formato: ``lti:{deployment_id}:{sub}``.
    El namespacing por deployment_id garantiza que dos Moodles diferentes que
    usen el mismo ``sub`` numérico no colisionen.
    """
    return f"{_LTI_PREFIX}:{deployment_id}:{sub}"


def _extraer_nombre(claims: dict) -> tuple[str | None, str | None]:
    """Deriva ``(nombre, apellido)`` de los claims OIDC del ``id_token``.

    Moodle emite los claims estándar OIDC ``given_name`` / ``family_name`` además
    del ``name`` (display name completo). Estrategia:

    - Si vienen ``given_name`` y/o ``family_name`` → se usan tal cual (fuente
      estructurada, es lo que Moodle manda por defecto).
    - Si sólo viene ``name`` → se guarda COMPLETO en ``nombre`` (no se parte
      heurísticamente: "Juan de la Cruz Pérez" no tiene un corte fiable), con
      ``apellido=None``.
    - Si no viene nada → ``(None, None)`` (ambos campos son nullable).
    """
    given = (claims.get("given_name") or "").strip() or None
    family = (claims.get("family_name") or "").strip() or None
    if given or family:
        return given, family
    name = (claims.get("name") or "").strip() or None
    return name, None


async def provisionar_o_recuperar_usuario(
    session: AsyncSession,
    *,
    claims: dict,
    deployment: LtiDeploymentConfiableModel,
) -> tuple[UsuarioModel, bool]:
    """Provisionamiento JIT: crea o recupera el usuario + matricula si hay mapeo.

    Args:
        session: sesión de base de datos (sin commit — el caller lo hace).
        claims: claims del ``id_token`` ya validado por ``validar_launch``.
                Son la ÚNICA fuente de identidad — ningún otro parámetro de
                nombre/email/rol se acepta en esta función.
        deployment: fila ``LtiDeploymentConfiableModel`` con ``activo=True``
                    (ya verificada por ``validar_launch``).

    Returns:
        Tupla ``(usuario, creado)``:
        - ``usuario``: instancia ORM del usuario (nueva o existente).
        - ``creado``: ``True`` si se creó ahora, ``False`` si ya existía.

    Raises:
        LaunchInvalidoError("claims_incompletos"): si ``sub`` no está en claims.
    """
    sub = claims.get("sub")
    if not sub:
        raise LaunchInvalidoError("claims_incompletos")

    deployment_id = claims.get(CLAIM_DEPLOYMENT_ID) or deployment.deployment_id
    id_inst = _id_institucional_lti(deployment_id, sub)

    # ---- Buscar usuario existente -------------------------------------------
    resultado = await session.execute(
        select(UsuarioModel).where(UsuarioModel.id_institucional == id_inst)
    )
    usuario = resultado.scalar_one_or_none()

    if usuario is not None:
        # Usuario ya existe: idempotente, nada que crear.
        # Si hay mapeo de comisión, asegurar la matrícula de todas formas
        # (puede ser un segundo launch luego de que el admin configuró el mapeo).
        await _asegurar_matricula(session, usuario=usuario, deployment=deployment)
        return usuario, False

    # ---- Crear usuario nuevo ------------------------------------------------
    email = claims.get("email") or ""
    nombre, apellido = _extraer_nombre(claims)

    # Password aleatorio, no comunicado (patrón "clave temporal" de C-61).
    # El alumno se autentica vía LTI — no necesita este password. Si quiere
    # loguearse directo (sin Moodle) deberá fijarlo desde el dashboard
    # ("Fijá tu contraseña" — debe_cambiar_password=True).
    password_aleatorio = secrets.token_urlsafe(32)
    password_hash = hashear_password(password_aleatorio)

    usuario = UsuarioModel(
        id_institucional=id_inst,
        email=email,
        # Rol canónico del sistema (``Rol.ESTUDIANTE = "estudiante"``). La spec usa
        # "alumno" como término informal — en el enum y en los tokens siempre es
        # "estudiante" para que ``TokenPolicy`` lo reconozca.
        roles=["estudiante"],
        auth_provider="lti",
        debe_cambiar_password=True,
        password_hash=password_hash,
        nombre=nombre,
        apellido=apellido,
        attrs_federados={
            # Contexto LTI mínimo para auditoría (Open Question del design.md).
            # No se persiste el roster completo — solo el contexto del launch.
            "lti_iss": claims.get("iss"),
            "lti_deployment_id": deployment_id,
        },
    )
    session.add(usuario)
    # flush para obtener el id antes del commit (necesario para la matriculación).
    await session.flush()

    await _asegurar_matricula(session, usuario=usuario, deployment=deployment)
    return usuario, True


async def _asegurar_matricula(
    session: AsyncSession,
    *,
    usuario: UsuarioModel,
    deployment: LtiDeploymentConfiableModel,
) -> None:
    """Matricula al alumno en la comisión mapeada si existe el mapeo.

    Idempotente: usa ``INSERT ... ON CONFLICT DO NOTHING`` para no fallar si el
    alumno ya estaba inscripto (el UNIQUE(usuario_id, comision_id) lo garantiza).
    Sin rollback: la sesión queda limpia para el flush/commit del caller.

    Si ``deployment.comision_id`` es None → no hace nada (spec 5.8: contexto
    sin mapeo → no matricular).
    """
    if deployment.comision_id is None:
        return

    # INSERT ... ON CONFLICT DO NOTHING: idempotente sin IntegrityError.
    await session.execute(
        sa_text(
            "INSERT INTO inscripcion (usuario_id, comision_id) "
            "VALUES (:uid, :cid) "
            "ON CONFLICT (usuario_id, comision_id) DO NOTHING"
        ),
        {"uid": usuario.id, "cid": deployment.comision_id},
    )
