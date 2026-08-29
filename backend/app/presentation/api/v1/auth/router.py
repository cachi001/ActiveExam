"""Router de auth (C-06 + C-55).

Endpoints:
- ``POST /auth/login``: autenticacion con usuario+password (C-55, PUBLICA).
  Emite access token JWT propio (HS256) + refresh persistente en DB.
- ``POST /auth/refresh``: rota el refresh token (C-06 D2 + C-55 DbStore).
- ``GET  /auth/me``: devuelve el principal autenticado (Bearer requerido).

Mensajes de error GENERICOS en login (timing-safe): no revelan si el usuario
existe o si la password es incorrecta — mismo mensaje para ambos casos (RN-AU).

Pydantic con ``extra='forbid'`` (regla dura de codigo).
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.password_policy import PasswordDebilError, validar_password_fuerte
from app.infrastructure.auth.db_refresh_store import DbRefreshTokenStore
from app.infrastructure.auth.hashing import (
    hashear_password_async,
    verificar_password,
    verificar_password_dummy,
)
from app.infrastructure.auth.own_issuer import emitir_jwt_propio
from app.infrastructure.auth.refresh_store import RefreshTokenError, RefreshTokenStore
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.auth.dependencies import get_current_principal

router = APIRouter()

# Mensaje generico para todos los fallos de login (no revela si usuario existe).
_MSG_LOGIN_INVALIDO = "Credenciales inválidas."

# Lockout (pentest 2026-08-21, H-bruteforce): sin esto, POST /auth/login no
# tenia NINGUN limite de intentos fallidos. Mismos valores que el patron ya
# usado en otro proyecto del dueño (Sistema-de-Reserva-Salon): 5 intentos,
# 15 minutos de bloqueo. El mensaje de bloqueo SI informa el tiempo restante
# (lo necesita el usuario legitimo) pero el 401 de credenciales invalidas
# NUNCA revela cuantos intentos quedan ni el maximo configurado — eso le
# regalaria al atacante el umbral exacto para no activar el bloqueo.
_LOGIN_MAX_INTENTOS = 5
_LOGIN_BLOQUEO_MINUTOS = 15


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class RefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class PrincipalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    email: str
    roles: list[str]
    mfa_satisfecho: bool
    jurisdiccion: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    creado_en: datetime | None = None
    ultimo_acceso_en: datetime | None = None
    # True → el usuario entró con clave temporal y debe definir su contraseña.
    debe_cambiar_password: bool = False
    # Origen de la credencial: "local" | "lti" | "keycloak". El frontend lo usa
    # para el gate de "definí tu contraseña": un usuario LTI en su primer ingreso
    # no tiene contraseña temporal que pedirle (C-75).
    auth_provider: str | None = None


# ---------------------------------------------------------------------------
# Helpers de dependencias
# ---------------------------------------------------------------------------


def _get_refresh_store(request: Request) -> RefreshTokenStore:
    store = getattr(request.app.state, "refresh_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Store de refresh no inicializado.",
        )
    return store


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession] | None:
    return getattr(request.app.state, "session_factory", None)


# ---------------------------------------------------------------------------
# POST /auth/login (PUBLICA — sin require_roles)
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
) -> LoginResponse:
    """Login con credenciales propias (usuario + password) — C-55.

    Busca el usuario por email O username. Verifica bcrypt.
    Emite JWT propio (HS256) + refresh persistente.

    Responde 401 con mensaje GENERICO en todos los casos de fallo:
    usuario no existe, password incorrecto, sin password_hash — mismo mensaje
    para no revelar informacion al atacante.

    Timing-safe tambien a nivel de LATENCIA (pentest 2026-08-21): antes, la
    rama "usuario no existe" cortaba camino sin llamar a bcrypt y respondia
    ~40x mas rapido que la rama "usuario existe, password incorrecta" —
    permitia enumerar usernames validos midiendo el tiempo de respuesta pese
    a que el mensaje fuera identico. Ahora esa rama llama a
    ``verificar_password_dummy`` para gastar el mismo tiempo.

    Lockout: 5 intentos fallidos seguidos bloquean la cuenta 15 minutos
    (mismo patron que Sistema-de-Reserva-Salon). El contador vive en
    ``usuario.intentos_fallidos``/``bloqueado_hasta`` y se resetea en cada
    login exitoso.
    """
    settings = request.app.state.settings
    session_factory = _get_session_factory(request)

    # jwt_own_secret es obligatorio para este endpoint.
    if not settings.jwt_own_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_OWN_SECRET no configurado. El provider JWT propio no esta activo.",
        )

    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )

    async with session_factory() as session:
        # Buscar por email O username (ambos son formas validas de login).
        # C-61 D3: filtrar eliminado_en IS NULL — usuarios dados de baja no pueden loguear.
        result = await session.execute(
            select(UsuarioModel).where(
                or_(
                    UsuarioModel.email == body.username,
                    UsuarioModel.username == body.username,
                ),
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        try:
            usuario = result.scalar_one_or_none()
        except MultipleResultsFound:
            # Defensivo: con `email` y `username` UNIQUE (c-76-4) esto no
            # debería ser alcanzable, pero si algún dato viejo/importado lo
            # viola, fallar con el MISMO 401 genérico en vez de un 500 que
            # confirmaría la colisión al atacante.
            usuario = None

        # Verificar: usuario debe existir, tener password_hash y credencial local.
        # Mensaje GENERICO: no revela si el usuario existe, si fue dado de baja,
        # o si el password es incorrecto (timing-safe a nivel de mensaje).
        if usuario is None or not usuario.password_hash:
            # H-timing (pentest 2026-08-21): gastar el MISMO tiempo que la rama
            # "usuario existe" gastaria verificando password, para que medir la
            # latencia no permita distinguir username valido de invalido pese a
            # que el mensaje de error sea identico.
            verificar_password_dummy(body.password)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_MSG_LOGIN_INVALIDO,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Lockout (H-bruteforce, pentest 2026-08-21): si la cuenta ya esta
        # bloqueada, cortar ANTES de intentar verificar el password — un
        # intento mas no debe extender el bloqueo ni gastar el costo de bcrypt.
        ahora = datetime.now(timezone.utc)
        if usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora:
            segundos_restantes = max(
                1, int((usuario.bloqueado_hasta - ahora).total_seconds())
            )
            minutos_restantes = max(1, segundos_restantes // 60 + 1)
            # Se devuelven los SEGUNDOS (no la marca de tiempo del desbloqueo) para
            # que el cliente pueda mostrar una cuenta regresiva exacta sin depender
            # de que su reloj coincida con el del servidor. `mensaje` se conserva
            # para quien solo muestre texto.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "cuenta_bloqueada",
                    "mensaje": (
                        f"Cuenta bloqueada temporalmente por intentos fallidos. "
                        f"Volvé a intentar en {minutos_restantes} min."
                    ),
                    "segundos_restantes": segundos_restantes,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verificar_password(body.password, usuario.password_hash):
            # Registrar el intento fallido y, si alcanza el maximo, bloquear.
            # El mensaje NUNCA revela cuantos intentos quedan ni el maximo
            # configurado (le regalaria al atacante el umbral del bloqueo).
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= _LOGIN_MAX_INTENTOS:
                usuario.bloqueado_hasta = ahora + timedelta(minutes=_LOGIN_BLOQUEO_MINUTOS)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_MSG_LOGIN_INVALIDO,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Emitir access token JWT propio.
        access_token = emitir_jwt_propio(
            usuario,
            secret=settings.jwt_own_secret,
            issuer=settings.jwt_own_issuer,
            audience=settings.jwt_audience,
            ttl_seconds=settings.access_token_ttl_seconds,
        )

        # Login exitoso: resetear el contador de lockout y registrar último acceso.
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        usuario.ultimo_acceso_en = datetime.now(timezone.utc)

        # Emitir refresh token persistente en DB.
        db_store = DbRefreshTokenStore(session, ttl_seconds=settings.refresh_token_ttl_seconds)
        refresh_jti = await db_store.issue_para_usuario(str(usuario.id))
        await session.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_jti,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh (rota el refresh token — C-06 D2 + C-55 DbStore)
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
) -> RefreshResponse:
    """Rota el refresh token: invalida el usado y emite uno nuevo (D2 + C-55).

    Con provider 'jwt': usa DbRefreshTokenStore (persistente) cuando hay
    session_factory disponible. En modo legacy (Keycloak) o sin DB: InMemory.

    Un refresh ya rotado o invalido -> 401 (rotacion: no se reusa).
    """
    settings = request.app.state.settings
    session_factory = _get_session_factory(request)

    # Si el provider es jwt y hay DB disponible: usar DbRefreshTokenStore.
    if settings.auth_provider == "jwt" and session_factory is not None and settings.jwt_own_secret:
        async with session_factory() as session:
            db_store = DbRefreshTokenStore(session, ttl_seconds=settings.refresh_token_ttl_seconds)
            try:
                # Para el refresh necesitamos el usuario_id del token viejo.
                # Buscamos el registro en DB para obtenerlo.
                from sqlalchemy import select as sa_select  # noqa: PLC0415
                from app.infrastructure.persistence.models.transactional import RefreshTokenModel  # noqa: PLC0415
                from datetime import UTC, datetime  # noqa: PLC0415
                result = await session.execute(
                    sa_select(RefreshTokenModel).where(
                        RefreshTokenModel.jti == body.refresh_token,
                        RefreshTokenModel.rotado_en.is_(None),
                        RefreshTokenModel.expires_at > datetime.now(UTC),
                    )
                )
                registro = result.scalar_one_or_none()
                if registro is None:
                    raise RefreshTokenError("Refresh token invalido, expirado o ya rotado.")

                nuevo_jti = await db_store.rotate_async(body.refresh_token, registro.usuario_id)

                # Re-emitir el access token para el mismo usuario.
                usuario_result = await session.execute(
                    sa_select(UsuarioModel).where(UsuarioModel.id == registro.usuario_id)
                )
                usuario = usuario_result.scalar_one_or_none()
                if usuario is None:
                    raise RefreshTokenError("Usuario del refresh no encontrado.")

                access_token = emitir_jwt_propio(
                    usuario,
                    secret=settings.jwt_own_secret,
                    issuer=settings.jwt_own_issuer,
                    audience=settings.jwt_audience,
                    ttl_seconds=settings.access_token_ttl_seconds,
                )
                await session.commit()
            except RefreshTokenError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(exc),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc

        return RefreshResponse(access_token=access_token, refresh_token=nuevo_jti)

    # Modo legacy (Keycloak / InMemory): comportamiento C-06 original.
    store = _get_refresh_store(request)
    try:
        nuevo_refresh = store.rotate(body.refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    access = getattr(request.app.state, "issue_access_token", lambda: nuevo_refresh)()
    return RefreshResponse(access_token=access, refresh_token=nuevo_refresh)


# ---------------------------------------------------------------------------
# GET /auth/me (requiere Bearer valido)
# ---------------------------------------------------------------------------


@router.get("/me", response_model=PrincipalResponse)
async def me(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PrincipalResponse:
    """Devuelve el principal autenticado (Bearer requerido).

    Si hay DB disponible, hace lookup por ``principal.subject`` (= UsuarioModel.id)
    para incluir ``username``, ``nombre`` y ``apellido``. Si la DB no está
    disponible o el usuario no se encuentra, los campos caen a los del token o a
    ``None`` (degradación graceful).

    c-78: ``username`` sale de la FILA, no del token — ver el comentario abajo.
    """
    nombre: str | None = None
    apellido: str | None = None
    creado_en: datetime | None = None
    ultimo_acceso_en: datetime | None = None
    debe_cambiar_password: bool = False
    auth_provider: str | None = None
    # c-78: el username SALE DE LA BASE, no del token.
    #
    # Bug real: el alumno que entra por LTI arranca con un username sintético
    # (`lti:{deployment}:{sub}`), elige el suyo, la fila se renombra... y el
    # token que tiene en la mano sigue diciendo `lti:1:7`. Como este endpoint
    # devolvía `principal.username` (del token), el Perfil le mostraba ESE
    # nombre. Leyéndolo de la fila, el Perfil dice la verdad aunque el token
    # esté viejo. Cae al del token si no hay DB (degradación graceful).
    username: str = principal.username

    session_factory = _get_session_factory(request)
    if session_factory is not None and principal.subject is not None:
        try:
            async with session_factory() as session:
                from sqlalchemy import select as sa_select  # noqa: PLC0415
                result = await session.execute(
                    sa_select(UsuarioModel).where(UsuarioModel.id == principal.subject)
                )
                usuario = result.scalar_one_or_none()
                if usuario is not None:
                    username = usuario.username
                    nombre = usuario.nombre
                    apellido = usuario.apellido
                    creado_en = usuario.creado_en
                    ultimo_acceso_en = usuario.ultimo_acceso_en
                    debe_cambiar_password = bool(usuario.debe_cambiar_password)
                    auth_provider = usuario.auth_provider
        except Exception:  # noqa: BLE001
            pass

    return PrincipalResponse(
        username=username,
        email=principal.email,
        roles=[r.value for r in principal.roles],
        mfa_satisfecho=principal.mfa_satisfecho,
        jurisdiccion=principal.jurisdiccion,
        nombre=nombre,
        apellido=apellido,
        creado_en=creado_en,
        ultimo_acceso_en=ultimo_acceso_en,
        debe_cambiar_password=debe_cambiar_password,
        auth_provider=auth_provider,
    )


# ---------------------------------------------------------------------------
# POST /auth/register (PUBLICA — C-61, D4)
# ---------------------------------------------------------------------------

# Auto-registro público de estudiantes (RegistroRequest/RegistroResponse,
# POST /auth/register) fue ELIMINADO (c-76-4): toda alta de usuario pasa a
# ser interna (admin panel via POST /users/, o LTI JIT provisioning). Ver
# tasks.md — decisión del dueño de sacar la superficie pública de auto-alta.


# ---------------------------------------------------------------------------
# PUT /auth/change-password — cambio de contraseña propio (cualquier usuario local)
# ---------------------------------------------------------------------------


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


class CambiarContrasenaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Opcional: en el PRIMER set de un usuario LTI no hay contraseña temporal que
    # informar (nunca la recibió). Para usuarios local o cambios posteriores es
    # obligatoria y se verifica.
    contrasena_actual: str | None = None
    contrasena_nueva: str = Field(min_length=8, max_length=512)
    # Opcional, SOLO válido en el primer set (debe_cambiar_password=True): el
    # usuario (LTI o alta manual) elige su propio username legible en vez de
    # quedarse con el autogenerado (lti:{deployment}:{sub} o el prefijo+random
    # del alta manual). Reglas de formato inspiradas en el patrón validado del
    # sistema de referencia (Active-IA): alfanumérico + . _ -, 3-50 caracteres.
    nuevo_username: str | None = Field(default=None, min_length=3, max_length=50)

    @field_validator("contrasena_nueva")
    @classmethod
    def nueva_fuerte(cls, v: str) -> str:
        # Política Media: 8+ con mayúscula, minúscula y dígito (RN-AU).
        try:
            validar_password_fuerte(v)
        except PasswordDebilError as exc:
            raise ValueError(str(exc)) from exc
        return v

    @field_validator("nuevo_username")
    @classmethod
    def username_formato_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "El username solo puede tener letras, números, puntos, guiones y guiones bajos."
            )
        return v


class CambiarContrasenaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool
    # c-78 E-13: cuando el usuario ELIGE su username en el primer set, el access
    # token que tiene en la mano sigue llevando el `preferred_username` viejo
    # (`lti:1:7`), así que la app le muestra ese nombre hasta que expire o cierre
    # sesión. Se re-emite acá para que el cambio sea inmediato. Null cuando no
    # hubo cambio de username (nada que actualizar).
    access_token: str | None = None


@router.put("/change-password", response_model=CambiarContrasenaResponse)
async def cambiar_contrasena(
    body: CambiarContrasenaRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> CambiarContrasenaResponse:
    """Cambia (o define por primera vez) la contraseña propia.

    Dos caminos:
    - **Primer set de un usuario LTI** (``auth_provider='lti'`` + ``debe_cambiar_password``):
      define su contraseña SIN pedir la actual — nunca recibió una temporal; el
      Bearer de la sesión (emitida tras un launch LTI válido) ya prueba identidad.
    - **Cualquier otro caso** (usuarios ``local``, o LTI cambiando una clave ya
      definida): exige y verifica ``contrasena_actual`` (no se puede resetear con
      un token robado sin saber la clave). Mensaje genérico para no filtrar info.

    ``nuevo_username`` (opcional): SOLO en el primer set (``debe_cambiar_password``
    True, LTI o alta manual) el usuario puede elegir su propio username legible,
    reemplazando el autogenerado (``lti:{deployment}:{sub}`` o el prefijo+random
    del alta manual). 400 si se intenta fuera del primer set; 409 si ya está en
    uso (como username o como email de otro usuario — c-76-4).

    Cuentas ``keycloak`` u otras no gestionan su contraseña acá (403).
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )

    async with session_factory() as session:
        result = await session.execute(
            select(UsuarioModel).where(UsuarioModel.id == principal.subject)
        )
        usuario = result.scalar_one_or_none()

        if not usuario or usuario.auth_provider not in ("local", "lti", "jwt"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No podés cambiar la contraseña de esta cuenta.",
            )

        # Primer set (LTI o alta manual): todavía no definió su propia contraseña.
        primer_set = bool(usuario.debe_cambiar_password)
        # ¿Es el primer set de un usuario LTI? En ese caso no hay contraseña actual.
        lti_primer_set = usuario.auth_provider == "lti" and primer_set

        # Regla dura #6 (cliente no confiable): el frontend ya exige elegir
        # username en el primer set LTI (la cuenta arranca con la clave sintética
        # del campus, lti:{deployment}:{sub}, que no sirve para loguearse directo)
        # — el backend lo re-valida en vez de confiar en que el cliente lo mandó.
        if lti_primer_set and not body.nuevo_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Elegí un nombre de usuario para poder ingresar directo la próxima vez.",
            )

        if body.nuevo_username is not None:
            if not primer_set:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo podés elegir tu username la primera vez que fijás la contraseña.",
                )
            # Validación CRUZADA (c-76-4): no puede coincidir con el username NI
            # el email de otro usuario — el login matchea por "email OR username".
            cruce = await session.execute(
                select(UsuarioModel.id).where(
                    or_(
                        UsuarioModel.username == body.nuevo_username,
                        UsuarioModel.email == body.nuevo_username,
                    ),
                    UsuarioModel.id != usuario.id,
                )
            )
            if cruce.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ese username ya está en uso.",
                )
            usuario.username = body.nuevo_username

        if not lti_primer_set:
            # Camino normal: exige y verifica la contraseña actual.
            if not usuario.password_hash:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No podés cambiar la contraseña de esta cuenta.",
                )
            if not body.contrasena_actual or not verificar_password(
                body.contrasena_actual, usuario.password_hash
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La contraseña actual es incorrecta.",
                )
            # La nueva no puede ser igual a la actual.
            if verificar_password(body.contrasena_nueva, usuario.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La nueva contraseña debe ser distinta de la actual.",
                )

        # En thread aparte (ver hashear_password_async): es el camino del PRIMER
        # ingreso, donde una comision entera cambia su clave junta.
        usuario.password_hash = await hashear_password_async(body.contrasena_nueva)
        # Primer login resuelto: ya definió su propia contraseña.
        usuario.debe_cambiar_password = False
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese username ya está en uso.",
            ) from exc

        # c-78 E-13: el username cambió → el access token en poder del cliente
        # quedó desactualizado (sigue diciendo `lti:{deployment}:{sub}`) y la app
        # muestra ESE nombre hasta que el token expire. Se re-emite con los claims
        # nuevos. Mismos parámetros que `/auth/login`: un solo lugar decide cómo se
        # arma un token de sesión.
        #
        # Solo se re-emite el ACCESS token: el refresh vigente sigue siendo válido
        # (no cambió la identidad del usuario, solo su nombre visible) y rotarlo acá
        # obligaría al cliente a manejar dos rotaciones distintas en el mismo flujo.
        access_token_nuevo: str | None = None
        if body.nuevo_username is not None:
            settings = getattr(request.app.state, "settings", None)
            secreto = getattr(settings, "jwt_own_secret", None) if settings else None
            if secreto:
                await session.refresh(usuario)
                access_token_nuevo = emitir_jwt_propio(
                    usuario,
                    secret=secreto,
                    issuer=settings.jwt_own_issuer,
                    audience=settings.jwt_audience,
                    ttl_seconds=settings.access_token_ttl_seconds,
                )

    return CambiarContrasenaResponse(ok=True, access_token=access_token_nuevo)
