"""Router de usuarios: CRUD administrativo (C-61) + creacion minima (C-55, D8).

Endpoints:
- ``POST /``            : crea usuario con credencial local (solo admin_sistema, C-55).
- ``GET /``             : lista paginada, solo admin_sistema, excluye dados de baja (C-61).
- ``PUT /{usuario_id}`` : edita email/nombre/apellido/roles (solo admin_sistema, C-61).
- ``DELETE /{usuario_id}`` : baja logica soft-delete (solo admin_sistema, C-61).

Reglas duras:
- ``extra='forbid'`` en todos los schemas.
- El PUT rechaza modificar ``password_hash`` y ``auth_provider``.
- Anti-lockout: el admin no puede quitarse su propio rol ``admin_sistema``.
- El DELETE setea ``eliminado_en = now()`` y revoca refresh tokens vigentes.
- Los usuarios dados de baja (``eliminado_en IS NOT NULL``) no aparecen en el listado.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator  # noqa: F401
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.persistence.models.transactional import RefreshTokenModel, UsuarioModel
from app.presentation.api.v1.auth.dependencies import require_roles

router = APIRouter()

_require_admin = require_roles(Rol.ADMIN_SISTEMA)


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class CrearUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_institucional: str
    email: str
    password: str
    roles: list[str]
    nombre: str | None = None
    apellido: str | None = None

    @field_validator("password")
    @classmethod
    def password_minimo_8(cls, v: str) -> str:
        if len(v) < 8:  # noqa: PLR2004
            raise ValueError("El password debe tener al menos 8 caracteres.")
        return v

    @field_validator("roles")
    @classmethod
    def roles_validos(cls, v: list[str]) -> list[str]:
        roles_aceptados = {r.value for r in Rol}
        invalidos = [r for r in v if r not in roles_aceptados]
        if invalidos:
            raise ValueError(f"Roles invalidos: {invalidos}. Roles validos: {sorted(roles_aceptados)}")
        return v


class EditarUsuarioRequest(BaseModel):
    """Schema para PUT /users/{usuario_id}.

    INTENCIONALMENTE omite password_hash y auth_provider (extra='forbid' bloquea
    cualquier intento de enviarlos — no se permite cambiar credenciales por aqui).
    """

    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    roles: list[str] | None = None

    @field_validator("roles")
    @classmethod
    def roles_validos(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        roles_aceptados = {r.value for r in Rol}
        invalidos = [r for r in v if r not in roles_aceptados]
        if invalidos:
            raise ValueError(f"Roles invalidos: {invalidos}. Roles validos: {sorted(roles_aceptados)}")
        return v


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    auth_provider: str


class ListarUsuariosResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UsuarioResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _usuario_to_response(u: UsuarioModel) -> UsuarioResponse:
    return UsuarioResponse(
        id=str(u.id),
        id_institucional=u.id_institucional,
        email=u.email,
        nombre=u.nombre,
        apellido=u.apellido,
        roles=u.roles,
        auth_provider=u.auth_provider,
    )


# ---------------------------------------------------------------------------
# POST / — crear usuario con credencial local (C-55, D8)
# ---------------------------------------------------------------------------


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    body: CrearUsuarioRequest,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> UsuarioResponse:
    """Crea un usuario con credencial local (solo admin_sistema).

    Hashea el password con bcrypt 12r antes de persistir.
    409 si email o id_institucional ya existen.
    """
    session_factory = _get_session_factory(request)

    password_hash = hashear_password(body.password)
    usuario = UsuarioModel(
        id_institucional=body.id_institucional,
        email=body.email,
        roles=body.roles,
        nombre=body.nombre,
        apellido=body.apellido,
        password_hash=password_hash,
        auth_provider="local",
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

    return _usuario_to_response(usuario)


# ---------------------------------------------------------------------------
# GET / — listar usuarios paginado (C-61, D1)
# ---------------------------------------------------------------------------


@router.get("/", response_model=ListarUsuariosResponse)
async def listar_usuarios(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ListarUsuariosResponse:
    """Lista usuarios activos paginados (excluye dados de baja).

    Solo ``admin_sistema``. No incluye password_hash.
    """
    session_factory = _get_session_factory(request)

    async with session_factory() as session:
        # Filtrar eliminado_en IS NULL (solo activos).
        stmt = (
            select(UsuarioModel)
            .where(UsuarioModel.eliminado_en.is_(None))
            .order_by(UsuarioModel.id)
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        usuarios = result.scalars().all()

        # Contar total de activos.
        from sqlalchemy import func as sa_func  # noqa: PLC0415
        count_stmt = (
            select(sa_func.count(UsuarioModel.id))
            .where(UsuarioModel.eliminado_en.is_(None))
        )
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

    return ListarUsuariosResponse(
        items=[_usuario_to_response(u) for u in usuarios],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# PUT /{usuario_id} — editar email, nombre, apellido, roles (C-61, D1/D2)
# ---------------------------------------------------------------------------


@router.put("/{usuario_id}", response_model=UsuarioResponse)
async def editar_usuario(
    usuario_id: str,
    body: EditarUsuarioRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> UsuarioResponse:
    """Edita email, nombre, apellido y/o roles de un usuario.

    Regla anti-lockout (D2): el admin no puede quitarse su propio rol admin_sistema.
    No permite editar password_hash ni auth_provider (extra='forbid').
    404 si el usuario no existe.
    """
    session_factory = _get_session_factory(request)

    async with session_factory() as session:
        result = await session.execute(
            select(UsuarioModel).where(
                UsuarioModel.id == usuario_id,
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado.",
            )

        # Anti-lockout: el admin no puede quitarse a si mismo el rol admin_sistema.
        if body.roles is not None:
            es_el_mismo = str(usuario.id) == str(principal.subject)
            if es_el_mismo and Rol.ADMIN_SISTEMA.value not in body.roles:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "No podés quitarte el rol admin_sistema. "
                        "Asigná primero ese rol a otro administrador."
                    ),
                )
            usuario.roles = body.roles

        if body.email is not None:
            usuario.email = body.email
        if body.nombre is not None:
            usuario.nombre = body.nombre
        if body.apellido is not None:
            usuario.apellido = body.apellido

        try:
            await session.commit()
            await session.refresh(usuario)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email.",
            ) from exc

    return _usuario_to_response(usuario)


# ---------------------------------------------------------------------------
# DELETE /{usuario_id} — baja logica soft-delete (C-61, D3)
# ---------------------------------------------------------------------------


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def eliminar_usuario(
    usuario_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> None:
    """Baja logica del usuario (soft-delete).

    - Setea ``eliminado_en = now()`` (la fila no se borra fisicamente).
    - Revoca todos los refresh tokens vigentes del usuario.
    - El usuario dado de baja no puede loguear (filtro en auth/router.py).
    - La evidencia permanece intacta (cadena de custodia, regla #6/#7).

    Admin no puede darse de baja a si mismo (evita quedarse sin admin).
    404 si el usuario ya esta dado de baja o no existe.
    """
    # El admin no puede darse de baja a si mismo.
    if str(usuario_id) == str(principal.subject):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No podés darte de baja a vos mismo.",
        )

    session_factory = _get_session_factory(request)
    ahora = datetime.now(UTC)

    async with session_factory() as session:
        result = await session.execute(
            select(UsuarioModel).where(
                UsuarioModel.id == usuario_id,
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado o ya dado de baja.",
            )

        # Soft-delete via SQL directo (evita conflicto de tipos datetime/str en asyncpg).
        # El ORM mapea la columna como str | None pero asyncpg espera un datetime; usar
        # text() con TIMESTAMPTZ bypasea el problema de coercion y pasa el timestamp
        # como literal parametrizado que asyncpg convierte correctamente.
        await session.execute(
            text(
                "UPDATE usuario SET eliminado_en = :ahora WHERE id = :id"
            ),
            {"ahora": ahora, "id": usuario_id},
        )

        # Revocar refresh tokens vigentes del usuario dado de baja.
        await session.execute(
            text(
                "UPDATE refresh_tokens SET rotado_en = :ahora "
                "WHERE usuario_id = :usuario_id AND rotado_en IS NULL"
            ),
            {"ahora": ahora, "usuario_id": usuario_id},
        )

        await session.commit()
