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

import secrets
import string
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator  # noqa: F401
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.application.audit.acciones import AccionAuditoria, EntidadAuditoria, ModuloAuditoria, TipoAccionAuditoria
from app.domain.auth.roles import Rol
from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.persistence.models.transactional import (
    RefreshTokenModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.biometric_reference import (
    EmbeddingReferenciaRepository,
)
from app.infrastructure.persistence.repositories.consent_perfil import (
    ConsentimientoPerfilSqlRepository,
)
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
    password: str | None = None  # None → se genera automáticamente
    roles: list[str]
    nombre: str | None = None
    apellido: str | None = None

    @field_validator("password")
    @classmethod
    def password_minimo_8(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 8:  # noqa: PLR2004
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
    eliminado_en: str | None
    password_generada: str | None = None  # solo en POST cuando el admin no proveyó password
    creado_en: str | None = None
    ultimo_acceso_en: str | None = None


class ListarUsuariosResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UsuarioResponse]
    total: int
    limit: int
    offset: int


class UsuarioDetalleResponse(BaseModel):
    """Detalle completo de un usuario (admin).

    Incluye ``eliminado_en`` (ISO 8601 o null). NUNCA incluye password_hash
    ni embedding_cifrado (gobernanza critica).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    auth_provider: str
    eliminado_en: str | None
    creado_en: str | None = None
    ultimo_acceso_en: str | None = None


class ConsentProfileAdminResponse(BaseModel):
    """Estado vigente del consentimiento de perfil de un usuario (admin).

    Todos los campos son nullable: si no hay consentimiento registrado
    se devuelve 200 con todos en null (no 404).
    """

    model_config = ConfigDict(extra="forbid")

    estado: str | None = None
    version_texto: str | None = None
    hash_texto: str | None = None
    timestamp: str | None = None


class BiometriaReferenciaEstadoAdminResponse(BaseModel):
    """Estado de la captura de referencia biometrica de un usuario (admin).

    GOBERNANZA: NUNCA incluye embedding_cifrado ni el vector. Solo metadatos.
    """

    model_config = ConfigDict(extra="forbid")

    tiene_referencia_vigente: bool
    algoritmo: str | None = None
    fecha_expiracion: str | None = None
    created_at: str | None = None
    tiene_foto: bool
    foto_hash: str | None = None
    foto_created_at: str | None = None


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
        eliminado_en=str(u.eliminado_en) if u.eliminado_en is not None else None,
        creado_en=u.creado_en.isoformat() if getattr(u, "creado_en", None) is not None else None,
        ultimo_acceso_en=u.ultimo_acceso_en.isoformat() if getattr(u, "ultimo_acceso_en", None) is not None else None,
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

    # Si el admin no proveyó contraseña, generamos una segura aleatoria.
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password_plain = body.password or "".join(secrets.choice(alphabet) for _ in range(16))
    password_hash = hashear_password(password_plain)
    password_devolver = None if body.password else password_plain

    usuario = UsuarioModel(
        id_institucional=body.id_institucional,
        email=body.email,
        roles=body.roles,
        nombre=body.nombre,
        apellido=body.apellido,
        password_hash=password_hash,
        auth_provider="local",
        # Clave temporal: el usuario debe definir su propia contraseña en el
        # primer login (RN-AU). Se limpia al cambiarla (PUT /auth/change-password).
        debe_cambiar_password=True,
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

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=_principal.email,
        accion=AccionAuditoria.USUARIO_ALTA,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        tipo_accion=TipoAccionAuditoria.CREAR,
        entidad_id=str(usuario.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=f"Alta de usuario {usuario.email} (roles: {', '.join(body.roles)})",
    )

    resp = _usuario_to_response(usuario)
    return resp.model_copy(update={"password_generada": password_devolver})


# ---------------------------------------------------------------------------
# GET / — listar usuarios paginado (C-61, D1)
# ---------------------------------------------------------------------------


@router.get("/", response_model=ListarUsuariosResponse)
async def listar_usuarios(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    rol: str | None = None,
    estado: str | None = "activo",
    q: str | None = None,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ListarUsuariosResponse:
    """Lista usuarios paginados con filtros opcionales.

    Filtros:
    - ``rol``: filtra por rol exacto (JSONB contains).
    - ``estado``: ``"activo"`` (default) = solo activos; ``"inactivo"`` = solo dados de baja;
      ``"todos"`` = ambos.
    - ``q``: búsqueda ILIKE en nombre, apellido, email e id_institucional.

    Solo ``admin_sistema``. No incluye password_hash.
    """
    from sqlalchemy import func as sa_func  # noqa: PLC0415

    session_factory = _get_session_factory(request)

    async with session_factory() as session:
        # Clauses ORM y parámetros extra (para text() con CAST).
        base_where = []
        extra_params: dict = {}

        # Filtro de estado.
        if estado == "activo" or estado is None:
            base_where.append(UsuarioModel.eliminado_en.is_(None))
        elif estado == "inactivo":
            base_where.append(UsuarioModel.eliminado_en.isnot(None))
        # estado == "todos" → sin filtro de eliminado_en

        # Filtro de rol (JSONB contains).
        # asyncpg no acepta el valor como string sin CAST explícito.
        # Usamos text() con CAST(:param AS jsonb) y pasamos el param al execute().
        if rol is not None:
            import json  # noqa: PLC0415
            base_where.append(text("usuario.roles @> CAST(:rol_json AS jsonb)"))
            extra_params["rol_json"] = json.dumps([rol])

        # Filtro de búsqueda ILIKE.
        if q is not None:
            from sqlalchemy import or_  # noqa: PLC0415
            pattern = f"%{q}%"
            base_where.append(
                or_(
                    UsuarioModel.nombre.ilike(pattern),
                    UsuarioModel.apellido.ilike(pattern),
                    UsuarioModel.email.ilike(pattern),
                    UsuarioModel.id_institucional.ilike(pattern),
                )
            )

        stmt = (
            select(UsuarioModel)
            .where(*base_where)
            .order_by(UsuarioModel.id)
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt, extra_params if extra_params else None)
        usuarios = result.scalars().all()

        count_stmt = select(sa_func.count(UsuarioModel.id)).where(*base_where)
        count_result = await session.execute(count_stmt, extra_params if extra_params else None)
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

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_EDICION,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        tipo_accion=TipoAccionAuditoria.EDITAR,
        entidad_id=str(usuario.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=f"Editó el usuario {usuario.email}",
    )

    return _usuario_to_response(usuario)


# ---------------------------------------------------------------------------
# POST /{usuario_id}/habilitar-rehacer-biometria — override de un solo uso
# ---------------------------------------------------------------------------


@router.post(
    "/{usuario_id}/habilitar-rehacer-biometria",
    response_model=None,
    summary="Habilita al alumno a rehacer su referencia biométrica (una vez).",
)
async def habilitar_rehacer_biometria(
    usuario_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> dict:
    """Pone ``biometria_rehacer_habilitada = TRUE`` para el usuario.

    El alumno no puede rehacer su captura biométrica mientras siga vigente; con
    esto un admin le habilita UNA nueva captura. El flag se CONSUME (vuelve a
    FALSE) automáticamente cuando el alumno guarda la nueva referencia.
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
        usuario.biometria_rehacer_habilitada = True
        await session.commit()

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_EDICION,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        tipo_accion=TipoAccionAuditoria.EDITAR,
        entidad_id=str(usuario_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito="Habilitó al alumno a rehacer su referencia biométrica (una vez)",
    )

    return {"biometria_rehacer_habilitada": True}


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
        usuario_email = usuario.email

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_BAJA,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        # BAJA LÓGICA (soft-delete: setea eliminado_en, NO borra la fila) → es un
        # CAMBIO DE ESTADO, no una ELIMINACIÓN. "Eliminar" se reserva para el borrado
        # físico definitivo (que en usuarios no existe).
        tipo_accion=TipoAccionAuditoria.CAMBIO_ESTADO,
        entidad_id=str(usuario_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=f"El usuario {usuario_email} pasó de Activo a Inactivo (baja lógica)",
    )


# ---------------------------------------------------------------------------
# POST /{usuario_id}/reactivar — reactivar usuario dado de baja (admin_sistema)
# ---------------------------------------------------------------------------


@router.post("/{usuario_id}/reactivar", response_model=UsuarioDetalleResponse)
async def reactivar_usuario(
    usuario_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> UsuarioDetalleResponse:
    """Reactiva un usuario dado de baja (soft-delete revertido).

    - Setea ``eliminado_en = NULL``.
    - 404 si el usuario no existe (ni activo ni dado de baja).
    - 409 si el usuario ya está activo (``eliminado_en IS NULL``).
    - 409 si el admin intenta reactivarse a sí mismo.
    """
    # El admin no puede reactivarse a sí mismo.
    if str(usuario_id) == str(principal.subject):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No podés reactivarte a vos mismo.",
        )

    session_factory = _get_session_factory(request)

    async with session_factory() as session:
        result = await session.execute(
            select(UsuarioModel).where(UsuarioModel.id == usuario_id)
        )
        usuario = result.scalar_one_or_none()

        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado.",
            )

        if usuario.eliminado_en is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El usuario ya está activo.",
            )

        # Reactivar: limpiar eliminado_en via SQL directo (mismo patrón que DELETE).
        await session.execute(
            text("UPDATE usuario SET eliminado_en = NULL WHERE id = :id"),
            {"id": usuario_id},
        )
        await session.commit()
        await session.refresh(usuario)

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_REACTIVACION,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        # Reactivar (limpiar eliminado_en) también es un CAMBIO DE ESTADO — el reverso
        # de la baja lógica. No es una acción de una familia aparte.
        tipo_accion=TipoAccionAuditoria.CAMBIO_ESTADO,
        entidad_id=str(usuario_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=f"El usuario {usuario.email} pasó de Inactivo a Activo",
    )

    return UsuarioDetalleResponse(
        id=str(usuario.id),
        id_institucional=usuario.id_institucional,
        email=usuario.email,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        roles=usuario.roles,
        auth_provider=usuario.auth_provider,
        eliminado_en=None,  # acaba de reactivarse
    )


# ---------------------------------------------------------------------------
# Helpers privados para los endpoints de detalle (C-68)
# ---------------------------------------------------------------------------


async def _get_usuario_or_404(session: AsyncSession, usuario_id: str) -> UsuarioModel:
    """Devuelve el UsuarioModel por id (activo o dado de baja). 404 si no existe."""
    result = await session.execute(
        select(UsuarioModel).where(UsuarioModel.id == usuario_id)
    )
    usuario = result.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    return usuario


# ---------------------------------------------------------------------------
# GET /{usuario_id} — detalle del usuario (C-68, D1)
# ---------------------------------------------------------------------------


@router.get("/{usuario_id}", response_model=UsuarioDetalleResponse)
async def obtener_usuario(
    usuario_id: str,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> UsuarioDetalleResponse:
    """Detalle completo de un usuario (solo admin_sistema).

    Devuelve id, id_institucional, email, nombre, apellido, roles,
    auth_provider y eliminado_en (ISO 8601 o null).
    NUNCA incluye password_hash ni datos biometricos (gobernanza critica).
    404 si el usuario no existe.
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        usuario = await _get_usuario_or_404(session, usuario_id)

    return UsuarioDetalleResponse(
        id=str(usuario.id),
        id_institucional=usuario.id_institucional,
        email=usuario.email,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        roles=usuario.roles,
        auth_provider=usuario.auth_provider,
        eliminado_en=str(usuario.eliminado_en) if usuario.eliminado_en is not None else None,
        creado_en=str(usuario.creado_en) if getattr(usuario, "creado_en", None) is not None else None,
        ultimo_acceso_en=str(usuario.ultimo_acceso_en) if getattr(usuario, "ultimo_acceso_en", None) is not None else None,
    )


# ---------------------------------------------------------------------------
# GET /{usuario_id}/consent-profile — consentimiento vigente (C-68, D2)
# ---------------------------------------------------------------------------


@router.get("/{usuario_id}/consent-profile", response_model=ConsentProfileAdminResponse)
async def obtener_consent_profile(
    usuario_id: str,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ConsentProfileAdminResponse:
    """Estado vigente del consentimiento de perfil de un usuario (solo admin_sistema).

    - 404 si el usuario no existe.
    - 200 con todos los campos null si el usuario existe pero no tiene consentimiento
      registrado (no es un 404 — la ausencia de consentimiento es un estado valido).
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        # Verificar que el usuario existe (404 si no).
        await _get_usuario_or_404(session, usuario_id)

        # Buscar el consentimiento vigente del usuario.
        repo = ConsentimientoPerfilSqlRepository(session)
        vigente = await repo.vigente(usuario_id)

    if vigente is None:
        return ConsentProfileAdminResponse()

    return ConsentProfileAdminResponse(
        estado=vigente.estado,
        version_texto=vigente.version_texto,
        hash_texto=vigente.hash_texto,
        timestamp=str(vigente.timestamp),
    )


# ---------------------------------------------------------------------------
# GET /{usuario_id}/biometria/referencia/estado — estado biometrico (C-68, D3)
# ---------------------------------------------------------------------------


@router.get(
    "/{usuario_id}/biometria/referencia/estado",
    response_model=BiometriaReferenciaEstadoAdminResponse,
)
async def obtener_biometria_referencia_estado(
    usuario_id: str,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> BiometriaReferenciaEstadoAdminResponse:
    """Estado de la captura de referencia biometrica de un usuario (solo admin_sistema).

    GOBERNANZA CRITICA: NUNCA devuelve embedding_cifrado ni el vector. Solo metadatos.
    - tiene_referencia_vigente: si existe un embedding vigente.
    - algoritmo/fecha_expiracion/created_at: metadatos del embedding (NO el vector).
    - tiene_foto/foto_hash/foto_created_at: metadatos de la foto de referencia.

    404 si el usuario no existe.
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        # Verificar que el usuario existe (404 si no).
        await _get_usuario_or_404(session, usuario_id)

        # Embedding de referencia (solo metadatos, SIN embedding_cifrado).
        emb_repo = EmbeddingReferenciaRepository(session)
        emb = await emb_repo.obtener_vigente(usuario_id)

        # Foto de referencia — consulta por SQL crudo para no depender de
        # que el ORM model refleje exactamente el schema de la DB (que puede
        # variar entre slim y full). Solo leemos los metadatos necesarios.
        foto_result = await session.execute(
            text(
                "SELECT hash_sha256, created_at "
                "FROM foto_referencia "
                "WHERE usuario_id = :uid AND vigente = TRUE "
                "LIMIT 1"
            ),
            {"uid": usuario_id},
        )
        foto_row = foto_result.fetchone()

    tiene_referencia = emb is not None
    return BiometriaReferenciaEstadoAdminResponse(
        tiene_referencia_vigente=tiene_referencia,
        algoritmo=emb.algoritmo if emb is not None else None,
        fecha_expiracion=(
            str(emb.fecha_expiracion)
            if emb is not None and emb.fecha_expiracion is not None
            else None
        ),
        created_at=str(emb.created_at) if emb is not None else None,
        tiene_foto=foto_row is not None,
        foto_hash=foto_row[0] if foto_row is not None else None,
        foto_created_at=str(foto_row[1]) if foto_row is not None else None,
    )
