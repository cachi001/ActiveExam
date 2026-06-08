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

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.auth.db_refresh_store import DbRefreshTokenStore
from app.infrastructure.auth.hashing import hashear_password, verificar_password
from app.infrastructure.auth.own_issuer import emitir_jwt_propio
from app.infrastructure.auth.refresh_store import RefreshTokenError, RefreshTokenStore
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.auth.dependencies import get_current_principal

router = APIRouter()

# Mensaje generico para todos los fallos de login (no revela si usuario existe).
_MSG_LOGIN_INVALIDO = "Credenciales inválidas."


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str  # email o id_institucional
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

    id_institucional: str
    email: str
    roles: list[str]
    mfa_satisfecho: bool
    jurisdiccion: str | None = None
    nombre: str | None = None
    apellido: str | None = None


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

    Busca el usuario por email O id_institucional. Verifica bcrypt.
    Emite JWT propio (HS256) + refresh persistente.

    Responde 401 con mensaje GENERICO en todos los casos de fallo:
    usuario no existe, password incorrecto, sin password_hash — mismo mensaje
    para no revelar informacion al atacante (timing-safe a nivel de mensaje;
    bcrypt ya protege el timing de la comparacion).
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
        # Buscar por email O id_institucional (ambos son formas validas de login).
        # C-61 D3: filtrar eliminado_en IS NULL — usuarios dados de baja no pueden loguear.
        result = await session.execute(
            select(UsuarioModel).where(
                or_(
                    UsuarioModel.email == body.username,
                    UsuarioModel.id_institucional == body.username,
                ),
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        usuario = result.scalar_one_or_none()

        # Verificar: usuario debe existir, tener password_hash y credencial local.
        # Mensaje GENERICO: no revela si el usuario existe, si fue dado de baja,
        # o si el password es incorrecto (timing-safe a nivel de mensaje).
        if usuario is None or not usuario.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_MSG_LOGIN_INVALIDO,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verificar_password(body.password, usuario.password_hash):
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
    para incluir ``nombre`` y ``apellido``. Si la DB no está disponible o el usuario
    no se encuentra, ambos campos quedan ``None`` (degradación graceful).
    """
    nombre: str | None = None
    apellido: str | None = None

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
                    nombre = usuario.nombre
                    apellido = usuario.apellido
        except Exception:  # noqa: BLE001
            # Degradación graceful: la DB no responde, devolvemos None en nombre/apellido.
            pass

    return PrincipalResponse(
        id_institucional=principal.id_institucional,
        email=principal.email,
        roles=[r.value for r in principal.roles],
        mfa_satisfecho=principal.mfa_satisfecho,
        jurisdiccion=principal.jurisdiccion,
        nombre=nombre,
        apellido=apellido,
    )


# ---------------------------------------------------------------------------
# POST /auth/register (PUBLICA — C-61, D4)
# ---------------------------------------------------------------------------

# Patron basico de email valido (el validador de Pydantic EmailStr hace la
# validacion profunda; este patron es una guarda extra para tests).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Dominio institucional aceptado (vacio = acepta cualquier dominio valido).
# Configurable via env INSTITUTION_EMAIL_DOMAIN (ej: "frm.utn.edu.ar").
# El dueno confirmo que el registro es ABIERTO a cualquier email valido (S1).
_INSTITUTION_DOMAIN = os.environ.get("INSTITUTION_EMAIL_DOMAIN", "").strip().lower()


class RegistroRequest(BaseModel):
    """Schema de auto-registro publico (C-61, D4).

    SEGURIDAD: ``extra='forbid'`` impide que el body incluya ``roles``.
    El rol se fuerza a ``["estudiante"]`` server-side; ningun estudiante puede
    auto-elevarse a admin o proctor enviando un campo extra.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str
    apellido: str
    id_institucional: str
    email: str
    password: str
    password_confirmacion: str

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("El email no tiene un formato valido.")
        # Validacion de dominio institucional (solo si INSTITUTION_EMAIL_DOMAIN esta configurado).
        if _INSTITUTION_DOMAIN:
            dominio = v.split("@", 1)[1]
            if dominio != _INSTITUTION_DOMAIN:
                raise ValueError(
                    f"El email debe pertenecer al dominio institucional {_INSTITUTION_DOMAIN}."
                )
        return v

    @field_validator("password")
    @classmethod
    def password_fuerte(cls, v: str) -> str:
        if len(v) < 8:  # noqa: PLR2004
            raise ValueError("El password debe tener al menos 8 caracteres.")
        return v

    @model_validator(mode="after")
    def passwords_coinciden(self) -> "RegistroRequest":
        if self.password != self.password_confirmacion:
            raise ValueError("El password y la confirmacion no coinciden.")
        return self


class RegistroResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    id_institucional: str
    email: str
    nombre: str
    apellido: str
    roles: list[str]


@router.post("/register", response_model=RegistroResponse, status_code=status.HTTP_201_CREATED)
async def registrar(
    body: RegistroRequest,
    request: Request,
) -> RegistroResponse:
    """Auto-registro PUBLICO de estudiantes (C-61, D4).

    - Rol forzado a ``["estudiante"]`` server-side (el body no acepta roles).
    - auth_provider = "local".
    - bcrypt 12r para el password.
    - 409 si email o id_institucional ya existen.
    - 201 sin token: el frontend redirige al login (S3 confirmado).

    El password NUNCA se loguea ni se persiste en claro.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )

    # El password_hash se calcula; el password en claro se descarta inmediatamente.
    password_hash = hashear_password(body.password)

    usuario = UsuarioModel(
        id_institucional=body.id_institucional,
        email=body.email,
        nombre=body.nombre,
        apellido=body.apellido,
        # Rol FORZADO server-side — defensa en profundidad contra auto-elevacion.
        roles=[Rol.ESTUDIANTE.value],
        auth_provider="local",
        password_hash=password_hash,
        attrs_federados={},
    )

    async with session_factory() as session:
        session.add(usuario)
        try:
            await session.commit()
            await session.refresh(usuario)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email o id_institucional.",
            ) from exc

    # 201 sin token — el frontend redirige al login (D4, S3).
    return RegistroResponse(
        id=str(usuario.id),
        id_institucional=usuario.id_institucional,
        email=usuario.email,
        nombre=usuario.nombre or "",
        apellido=usuario.apellido or "",
        roles=usuario.roles,
    )
