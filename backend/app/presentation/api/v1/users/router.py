"""Router de usuarios: creacion minima protegida (C-55, D8).

Scope de este change: SOLO ``POST /`` para crear usuarios con credencial local.
El CRUD completo de usuarios (listado, edicion, baja, roles masivos) es el change
siguiente (out-of-scope aqui).

Solo ``admin_sistema`` puede crear usuarios. El password se hashea con bcrypt 12r
antes de persistir. Se rechaza con 409 si el email o id_institucional ya existen
(IntegrityError de Postgres).

Pydantic ``extra='forbid'`` (regla dura). snake_case (regla dura).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.auth.dependencies import require_roles

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class CrearUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_institucional: str
    email: str
    password: str
    roles: list[str]

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


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    id_institucional: str
    email: str
    roles: list[str]
    auth_provider: str


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


# ---------------------------------------------------------------------------
# POST / — crear usuario con credencial local
# ---------------------------------------------------------------------------


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    body: CrearUsuarioRequest,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(require_roles(Rol.ADMIN_SISTEMA)),
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

    return UsuarioResponse(
        id=str(usuario.id),
        id_institucional=usuario.id_institucional,
        email=usuario.email,
        roles=usuario.roles,
        auth_provider=usuario.auth_provider,
    )
