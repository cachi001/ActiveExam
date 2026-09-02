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
from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: F401
from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.application.audit.acciones import AccionAuditoria, EntidadAuditoria, ModuloAuditoria, TipoAccionAuditoria
from app.domain.auth.roles import Rol
from app.infrastructure.auth.hashing import hashear_password_async
from app.infrastructure.persistence.models.comision_tutor import ComisionTutorModel
from app.infrastructure.persistence.models.exam_content import ComisionModel, MateriaModel
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
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

#: Largo mínimo de un username editado a mano. No es una regla de seguridad (la
#: contraseña es la que protege): es para que no quede una credencial de un
#: carácter, imposible de comunicar por teléfono sin equivocarse.
_USERNAME_MINIMO = 3

# Prefijo de username autogenerado por rol (alta manual por admin_sistema).
# Orden = prioridad para elegir el prefijo cuando el usuario tiene varios roles.
_PREFIJO_POR_ROL: list[tuple[str, str]] = [
    (Rol.ADMIN_SISTEMA.value, "ADMIN"),
    (Rol.COORDINADOR.value, "COORD"),
    (Rol.TUTOR.value, "TUT"),
    (Rol.ESTUDIANTE.value, "EST"),
]


def _generar_username(roles: list[str]) -> str:
    """Genera un username único cuando el caller de la API no envía uno.

    Formato: <PREFIJO_ROL>-<sufijo alfanumérico aleatorio>. El prefijo refleja el
    rol de mayor jerarquía del usuario; el sufijo evita colisiones sin depender
    de un contador secuencial (no hay lectura previa a la escritura, sin race).
    """
    prefijo = next((p for rol, p in _PREFIJO_POR_ROL if rol in roles), "USR")
    sufijo = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefijo}-{sufijo}"


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class CrearUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = None  # None → se genera automáticamente
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

    username: str | None = None
    email: str | None = None
    nombre: str | None = None
    apellido: str | None = None
    roles: list[str] | None = None

    @field_validator("username")
    @classmethod
    def username_usable(cls, v: str | None) -> str | None:
        """Un username es una credencial de ingreso: tiene que poder tipearse.

        Vacío o en blanco dejaría a la persona sin forma de entrar, y los espacios
        se pierden o se duplican al copiar y pegar.
        """
        if v is None:
            return v
        limpio = v.strip()
        if limpio != v or " " in v:
            raise ValueError("El username no puede tener espacios.")
        if len(limpio) < _USERNAME_MINIMO:
            raise ValueError(f"El username debe tener al menos {_USERNAME_MINIMO} caracteres.")
        return limpio

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


class InscripcionResumen(BaseModel):
    """Materia + comisión en la que está inscripto un usuario (rol estudiante)."""

    model_config = ConfigDict(extra="forbid")

    comision_id: str
    comision_codigo: str
    comision_nombre: str
    materia_id: str
    materia_codigo: str
    materia_nombre: str


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    auth_provider: str
    eliminado_en: str | None
    password_generada: str | None = None  # solo en POST cuando el admin no proveyó password
    creado_en: str | None = None
    ultimo_acceso_en: str | None = None
    inscripciones: list[InscripcionResumen] = []
    # Materia/comisión donde este usuario es el docente a cargo (rol tutor).
    comisiones_a_cargo: list[InscripcionResumen] = []


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
    username: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    auth_provider: str
    eliminado_en: str | None
    creado_en: str | None = None
    ultimo_acceso_en: str | None = None
    # Bloqueo por intentos fallidos de login (5 intentos -> 15 minutos). Se expone
    # porque NINGUNA pantalla lo mostraba: el admin se enteraba solo si la persona
    # avisaba, y el día del examen eso es alguien esperando quince minutos.
    # `bloqueado` es derivado (la fecha vieja queda en la fila aunque ya haya
    # vencido), asi que leer `bloqueado_hasta` crudo diria "bloqueado" de mas.
    bloqueado: bool = False
    bloqueado_hasta: str | None = None
    bloqueo_segundos_restantes: int | None = None
    # Se muestra aunque el bloqueo haya vencido: el contador NO se limpia solo, y
    # con 5 encima un unico error mas vuelve a bloquear otros 15 minutos.
    intentos_fallidos: int = 0
    # c-78: el userid del alumno en el campus, que Moodle manda en cada ingreso
    # por el link (claim `sub`). Se expone para poder VERIFICAR que llega bien:
    # es uno de los datos con los que se le devuelve la nota, y sin verlo no hay
    # forma de saber si esta cargado. None = la cuenta no entro por el campus
    # (alta manual) o es anterior a que se empezara a guardar.
    moodle_userid: str | None = None
    inscripciones: list[InscripcionResumen] = []
    # Materia/comisión donde este usuario es el docente a cargo (rol tutor).
    # Vacío para roles sin comisión asignada (estudiante usa `inscripciones`).
    comisiones_a_cargo: list[InscripcionResumen] = []


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


def _usuario_to_response(
    u: UsuarioModel,
    inscripciones: list[InscripcionResumen] | None = None,
    comisiones_a_cargo: list[InscripcionResumen] | None = None,
) -> UsuarioResponse:
    return UsuarioResponse(
        id=str(u.id),
        username=u.username,
        email=u.email,
        nombre=u.nombre,
        apellido=u.apellido,
        roles=u.roles,
        auth_provider=u.auth_provider,
        eliminado_en=str(u.eliminado_en) if u.eliminado_en is not None else None,
        creado_en=u.creado_en.isoformat() if getattr(u, "creado_en", None) is not None else None,
        ultimo_acceso_en=u.ultimo_acceso_en.isoformat() if getattr(u, "ultimo_acceso_en", None) is not None else None,
        inscripciones=inscripciones or [],
        comisiones_a_cargo=comisiones_a_cargo or [],
    )


async def _inscripciones_por_usuario(
    session: AsyncSession, usuario_ids: list[str]
) -> dict[str, list[InscripcionResumen]]:
    """Batch: trae materia+comisión para varios usuarios de una sola query (evita N+1)."""
    if not usuario_ids:
        return {}
    result = await session.execute(
        select(InscripcionModel.usuario_id, ComisionModel, MateriaModel)
        .join(ComisionModel, InscripcionModel.comision_id == ComisionModel.id)
        .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
        .where(InscripcionModel.usuario_id.in_(usuario_ids))
        .order_by(MateriaModel.nombre, ComisionModel.codigo)
    )
    por_usuario: dict[str, list[InscripcionResumen]] = {}
    for usuario_id, comision, materia in result.all():
        por_usuario.setdefault(str(usuario_id), []).append(
            InscripcionResumen(
                comision_id=str(comision.id),
                comision_codigo=comision.codigo,
                comision_nombre=comision.nombre,
                materia_id=str(materia.id),
                materia_codigo=materia.codigo,
                materia_nombre=materia.nombre,
            )
        )
    return por_usuario


async def _comisiones_a_cargo_por_usuario(
    session: AsyncSession, usuario_ids: list[str]
) -> dict[str, list[InscripcionResumen]]:
    """Batch: comisión(es) donde cada usuario es tutor a cargo (c-79, N:M)."""
    if not usuario_ids:
        return {}
    result = await session.execute(
        select(ComisionTutorModel.tutor_id, ComisionModel, MateriaModel)
        .join(ComisionModel, ComisionModel.id == ComisionTutorModel.comision_id)
        .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
        .where(ComisionTutorModel.tutor_id.in_(usuario_ids))
        .order_by(MateriaModel.nombre, ComisionModel.codigo)
    )
    por_usuario: dict[str, list[InscripcionResumen]] = {}
    for docente_id, comision, materia in result.all():
        por_usuario.setdefault(str(docente_id), []).append(
            InscripcionResumen(
                comision_id=str(comision.id),
                comision_codigo=comision.codigo,
                comision_nombre=comision.nombre,
                materia_id=str(materia.id),
                materia_codigo=materia.codigo,
                materia_nombre=materia.nombre,
            )
        )
    return por_usuario


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
    El panel de administración siempre envía `username` (campo requerido en el
    formulario de alta). Si algún otro caller de la API lo omite, se genera uno.
    409 si email o username ya existen.
    """
    session_factory = _get_session_factory(request)

    # Si el admin no proveyó contraseña, generamos una segura aleatoria.
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password_plain = body.password or "".join(secrets.choice(alphabet) for _ in range(16))
    # En thread aparte (ver hashear_password_async): bcrypt bloqueaba el bucle.
    password_hash = await hashear_password_async(password_plain)
    password_devolver = None if body.password else password_plain

    username = body.username or _generar_username(body.roles)

    usuario = UsuarioModel(
        username=username,
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
        # Validación CRUZADA (c-76-4): username/email son UNIQUE cada uno por
        # separado, pero eso no impide que el username nuevo coincida con el
        # EMAIL de otra cuenta (o viceversa) — el login matchea por
        # "email OR username", así que esa colisión cruzada rompería el login
        # de la otra cuenta. Se rechaza acá, antes del INSERT.
        cruce = await session.execute(
            select(UsuarioModel.id).where(
                or_(
                    UsuarioModel.email == username,
                    UsuarioModel.username == body.email,
                )
            )
        )
        if cruce.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El username o el email coinciden con la identidad de otro usuario.",
            )

        session.add(usuario)
        try:
            await session.commit()
            await session.refresh(usuario)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email o username.",
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
    materia_id: str | None = None,
    comision_id: str | None = None,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ListarUsuariosResponse:
    """Lista usuarios paginados con filtros opcionales.

    Filtros:
    - ``rol``: filtra por rol exacto (JSONB contains).
    - ``estado``: ``"activo"`` (default) = solo activos; ``"inactivo"`` = solo dados de baja;
      ``"todos"`` = ambos.
    - ``q``: búsqueda ILIKE en nombre, apellido, email e username.
    - ``comision_id`` / ``materia_id``: solo usuarios inscriptos en esa comisión (o en
      cualquier comisión de esa materia si se pasa ``materia_id`` sin ``comision_id``).
      Pensado para usarse junto a ``rol=estudiante`` (los demás roles nunca tienen inscripción).

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
                    UsuarioModel.username.ilike(pattern),
                )
            )

        # Filtro por comisión/materia (via EXISTS — no multiplica filas del usuario).
        if comision_id is not None or materia_id is not None:
            inscripcion_where = [InscripcionModel.usuario_id == UsuarioModel.id]
            if comision_id is not None:
                inscripcion_where.append(InscripcionModel.comision_id == comision_id)
            if materia_id is not None:
                inscripcion_where.append(ComisionModel.materia_id == materia_id)
            exists_stmt = (
                select(InscripcionModel.id)
                .join(ComisionModel, InscripcionModel.comision_id == ComisionModel.id)
                .where(*inscripcion_where)
            )
            base_where.append(exists_stmt.exists())

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

        usuario_ids = [str(u.id) for u in usuarios]
        inscripciones_por_usuario = await _inscripciones_por_usuario(session, usuario_ids)
        comisiones_a_cargo_por_usuario = await _comisiones_a_cargo_por_usuario(session, usuario_ids)

    return ListarUsuariosResponse(
        items=[
            _usuario_to_response(
                u,
                inscripciones_por_usuario.get(str(u.id)),
                comisiones_a_cargo_por_usuario.get(str(u.id)),
            )
            for u in usuarios
        ],
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
    """Edita username, email, nombre, apellido y/o roles de un usuario.

    Regla anti-lockout (D2): el admin no puede quitarse su propio rol admin_sistema.
    No permite editar password_hash ni auth_provider (extra='forbid').
    404 si el usuario no existe.

    Cambiar el username CIERRA las sesiones abiertas de esa cuenta: el token porta
    el username viejo y quedaría presentando una identidad que ya no existe. 409 si
    el username nuevo ya lo usa otra persona, sea como username o como email (el
    login matchea por los dos).
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

        # Renombre. Va ANTES del email para que, si vienen los dos, un username
        # inválido no deje el email ya pisado.
        renombrado = body.username is not None and body.username != usuario.username
        if renombrado:
            # Simétrico a la validación cruzada del email: el login matchea por
            # "email OR username", así que el username nuevo tampoco puede ser el
            # email de otra persona — se disputarían la credencial de ingreso.
            cruce = await session.execute(
                select(UsuarioModel.id).where(
                    or_(
                        UsuarioModel.username == body.username,
                        UsuarioModel.email == body.username,
                    ),
                    UsuarioModel.id != usuario.id,
                )
            )
            if cruce.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Ese username ya lo usa otra persona, como username o "
                        "como email."
                    ),
                )
            usuario.username = body.username

        if body.email is not None:
            # Validación CRUZADA (c-76-4): el nuevo email no puede coincidir
            # con el username de OTRO usuario (mismo riesgo que en el alta:
            # el login matchea por "email OR username").
            cruce = await session.execute(
                select(UsuarioModel.id).where(
                    UsuarioModel.username == body.email,
                    UsuarioModel.id != usuario.id,
                )
            )
            if cruce.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ese email coincide con el username de otro usuario.",
                )
            usuario.email = body.email
        if body.nombre is not None:
            usuario.nombre = body.nombre
        if body.apellido is not None:
            usuario.apellido = body.apellido

        if renombrado:
            # El access token porta el username viejo (`preferred_username`), así
            # que una sesión abierta seguiría presentando una identidad que ya no
            # existe. Se cortan las sesiones: la persona vuelve a entrar con el
            # nombre nuevo. Solo al renombrar — corregir un apellido no puede
            # echar a nadie de un examen en curso.
            await session.execute(
                delete(RefreshTokenModel).where(
                    RefreshTokenModel.usuario_id == str(usuario.id)
                )
            )

        try:
            await session.commit()
            await session.refresh(usuario)
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email o username.",
            ) from exc

    from app.application.audit.service import registrar_seguro

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
        proposito=(
            f"Editó el usuario {usuario.email}"
            + (
                f" (renombró el usuario a {usuario.username}, sesiones cerradas)"
                if renombrado
                else ""
            )
        ),
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
        username=usuario.username,
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


def _estado_de_bloqueo(usuario: UsuarioModel) -> tuple[bool, str | None, int | None]:
    """Traduce ``bloqueado_hasta`` a (bloqueado, hasta_iso, segundos_restantes).

    La fila conserva la fecha del último bloqueo aunque ya haya vencido, así que
    el estado hay que derivarlo comparando contra el reloj. Un bloqueo vencido
    devuelve todo en falso/None: mostrar una fecha pasada haría que el admin
    desbloquee a alguien que ya podía entrar.

    Se devuelven también los segundos que faltan para que la pantalla pueda
    contar hacia atrás sin depender de que su reloj coincida con el del servidor
    (mismo criterio que el cartel del login).
    """
    hasta = getattr(usuario, "bloqueado_hasta", None)
    if hasta is None:
        return False, None, None
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=UTC)
    restantes = int((hasta - datetime.now(UTC)).total_seconds())
    if restantes <= 0:
        return False, None, None
    return True, hasta.isoformat(), restantes


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

    Devuelve id, username, email, nombre, apellido, roles,
    auth_provider y eliminado_en (ISO 8601 o null).
    NUNCA incluye password_hash ni datos biometricos (gobernanza critica).
    404 si el usuario no existe.
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        usuario = await _get_usuario_or_404(session, usuario_id)

        inscripciones: list[InscripcionResumen] = []
        if Rol.ESTUDIANTE.value in usuario.roles:
            result = await session.execute(
                select(ComisionModel, MateriaModel)
                .join(InscripcionModel, InscripcionModel.comision_id == ComisionModel.id)
                .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
                .where(InscripcionModel.usuario_id == usuario_id)
                .order_by(MateriaModel.nombre, ComisionModel.codigo)
            )
            inscripciones = [
                InscripcionResumen(
                    comision_id=str(comision.id),
                    comision_codigo=comision.codigo,
                    comision_nombre=comision.nombre,
                    materia_id=str(materia.id),
                    materia_codigo=materia.codigo,
                    materia_nombre=materia.nombre,
                )
                for comision, materia in result.all()
            ]

        comisiones_a_cargo: list[InscripcionResumen] = []
        if Rol.TUTOR.value in usuario.roles:
            result = await session.execute(
                select(ComisionModel, MateriaModel)
                .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
                .join(ComisionTutorModel, ComisionTutorModel.comision_id == ComisionModel.id)
                .where(ComisionTutorModel.tutor_id == usuario_id)
                .order_by(MateriaModel.nombre, ComisionModel.codigo)
            )
            comisiones_a_cargo = [
                InscripcionResumen(
                    comision_id=str(comision.id),
                    comision_codigo=comision.codigo,
                    comision_nombre=comision.nombre,
                    materia_id=str(materia.id),
                    materia_codigo=materia.codigo,
                    materia_nombre=materia.nombre,
                )
                for comision, materia in result.all()
            ]

    bloqueado, bloqueado_hasta, segundos_restantes = _estado_de_bloqueo(usuario)

    return UsuarioDetalleResponse(
        id=str(usuario.id),
        username=usuario.username,
        email=usuario.email,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        roles=usuario.roles,
        auth_provider=usuario.auth_provider,
        eliminado_en=str(usuario.eliminado_en) if usuario.eliminado_en is not None else None,
        creado_en=str(usuario.creado_en) if getattr(usuario, "creado_en", None) is not None else None,
        ultimo_acceso_en=str(usuario.ultimo_acceso_en) if getattr(usuario, "ultimo_acceso_en", None) is not None else None,
        bloqueado=bloqueado,
        bloqueado_hasta=bloqueado_hasta,
        bloqueo_segundos_restantes=segundos_restantes,
        intentos_fallidos=getattr(usuario, "intentos_fallidos", 0) or 0,
        moodle_userid=(
            str((usuario.attrs_federados or {}).get("moodle_userid"))
            if (usuario.attrs_federados or {}).get("moodle_userid") is not None
            else None
        ),
        inscripciones=inscripciones,
        comisiones_a_cargo=comisiones_a_cargo,
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


def _vencimiento_de_referencia(fecha_captura) -> str | None:
    """Cuando vence una referencia biometrica capturada en ``fecha_captura``.

    Se calcula con la MISMA cuenta que decide si hay que rehacer la captura
    (`_sumar_meses` + `BIOMETRIC_VALIDITY_MONTHS`), para que la fecha que ve el
    admin sea exactamente la que aplica el sistema y no dos numeros que pueden
    separarse.
    """
    if fecha_captura is None:
        return None
    from app.application.enrollment.guardar_embedding_referencia import (
        BIOMETRIC_VALIDITY_MONTHS,
        _sumar_meses,
    )

    return str(_sumar_meses(fecha_captura, BIOMETRIC_VALIDITY_MONTHS))


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
        # variar entre activeexam y full). Solo leemos los metadatos necesarios.
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
        # La columna `fecha_expiracion` no la escribe nadie: queda NULL siempre, y
        # leerla de ahi dejaba "Fecha de vencimiento" VACIO en pantalla, mientras
        # el consentimiento que el alumno acepta promete una vigencia de 24 meses.
        # La vigencia real se DERIVA de la fecha de captura (misma cuenta que usa
        # `_referencia_sigue_vigente` para decidir si hay que rehacerla), asi que se
        # calcula igual acá. Persistirla seria peor: cambiar la vigencia dejaria las
        # filas viejas con una fecha que ya no es la que aplica la logica.
        fecha_expiracion=(
            _vencimiento_de_referencia(emb.fecha_captura) if emb is not None else None
        ),
        created_at=str(emb.created_at) if emb is not None else None,
        tiene_foto=foto_row is not None,
        foto_hash=foto_row[0] if foto_row is not None else None,
        foto_created_at=str(foto_row[1]) if foto_row is not None else None,
    )


class ResetearPasswordResponse(BaseModel):
    """Respuesta de POST /users/{id}/resetear-password (c-78)."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: str
    username: str
    password_temporal: str = Field(
        ...,
        description=(
            "Se muestra UNA sola vez: no se guarda en claro en ningún lado. El "
            "usuario está obligado a cambiarla al entrar."
        ),
    )
    debe_cambiar_password: bool = True


@router.post(
    "/{usuario_id}/resetear-password",
    response_model=ResetearPasswordResponse,
    summary="Generar una contraseña temporal para un usuario (solo admin_sistema)",
)
async def resetear_password(
    usuario_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ResetearPasswordResponse:
    """Le genera al usuario una contraseña temporal y la devuelve UNA vez.

    Existe porque no había forma de resetear la contraseña de nadie (c-78): el
    alta genera una temporal, ``change-password`` exige la actual, el seed no
    pisa las existentes y no hay "olvidé mi contraseña". Si un docente la olvida
    el día del examen, sin esto nadie puede ayudarlo salvo entrando a la base.

    DOMINIO CRÍTICO (auth). Las guardas, todas necesarias:

    - **solo ``admin_sistema``** (``_require_admin``): resetear contraseñas es,
      literalmente, poder tomar la cuenta de cualquiera.
    - queda ``debe_cambiar_password=True``, igual que el alta: el admin destraba
      el acceso pero no se queda sabiendo la clave de nadie.
    - **409 en cuentas LTI**: esas no entran con contraseña (nacen con el
      centinela y su dueño fija la suya desde el dashboard). Darle una temporal
      le abriría un camino de entrada que hoy no tiene.
    - **404 en cuentas dadas de baja**: no se le destraba el acceso a alguien que
      fue dado de baja.

    Queda registrado en auditoría quién reseteó a quién. La contraseña NUNCA se
    escribe en el log ni en el propósito de la auditoría.
    """
    session_factory = _get_session_factory(request)

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password_plain = "".join(secrets.choice(alphabet) for _ in range(16))
    # En thread aparte (ver hashear_password_async): bcrypt bloquea el bucle.
    password_hash = await hashear_password_async(password_plain)

    async with session_factory() as session:
        usuario = (
            await session.execute(
                select(UsuarioModel).where(UsuarioModel.id == usuario_id)
            )
        ).scalar_one_or_none()

        if usuario is None or usuario.eliminado_en is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado.",
            )
        if usuario.auth_provider == "lti":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Esa cuenta entra desde el campus, no con contraseña. Si "
                    "quiere entrar directo, tiene que fijar la suya desde su perfil."
                ),
            )

        usuario.password_hash = password_hash
        usuario.debe_cambiar_password = True
        # Destraba tambien el lockout por intentos fallidos. El login corta por
        # `bloqueado_hasta` ANTES de verificar la contraseña, asi que sin esto el
        # admin daba una clave nueva y la persona seguia sin poder entrar: no habia
        # ninguna otra forma de desbloquear salvo entrar por SQL a la base. El dia
        # del examen eso deja a alguien afuera 15 minutos sin salida.
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        username = usuario.username
        await session.commit()

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_EDICION,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        entidad_id=str(usuario_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        # La contraseña NO se registra: el propósito dice qué pasó, no el secreto.
        proposito=(
            f"Resete\u00f3 la contrase\u00f1a de {username}. Queda obligado a "
            "cambiarla al entrar."
        ),
    )

    return ResetearPasswordResponse(
        usuario_id=str(usuario_id),
        username=username,
        password_temporal=password_plain,
    )


class DesbloquearCuentaResponse(BaseModel):
    """Respuesta de POST /users/{id}/desbloquear."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: str
    username: str
    bloqueado: bool = False
    #: True si la cuenta estaba realmente trabada al momento de la llamada. Sirve
    #: para que la pantalla distinga "la destrabé" de "no hacía falta".
    estaba_bloqueada: bool


@router.post(
    "/{usuario_id}/desbloquear",
    response_model=DesbloquearCuentaResponse,
    summary="Destrabar una cuenta bloqueada por intentos fallidos (solo admin_sistema)",
)
async def desbloquear_cuenta(
    usuario_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> DesbloquearCuentaResponse:
    """Limpia el bloqueo por intentos fallidos y NADA más.

    El login corta por ``bloqueado_hasta`` antes de verificar la contraseña, así
    que hasta ahora la única forma de destrabar a alguien era resetearle la
    contraseña. Eso funciona, pero arrastra dos efectos que en pleno examen
    estorban: la clave que la persona sabe deja de servir, y encima queda
    obligada a elegir una nueva antes de poder rendir.

    Este endpoint hace solo lo necesario: pone ``intentos_fallidos`` en cero y
    ``bloqueado_hasta`` en NULL. **No toca ``password_hash`` ni
    ``debe_cambiar_password``**: la persona vuelve a entrar con la suya.

    DOMINIO CRÍTICO (auth). Las guardas:

    - **solo ``admin_sistema``** (``_require_admin``): desbloquear es levantar la
      defensa contra fuerza bruta de una cuenta ajena.
    - **404 en cuentas dadas de baja**: a quien fue dado de baja no se le
      devuelve el acceso por esta puerta (para eso está reactivar).
    - **idempotente**: destrabar una cuenta que no estaba trabada no es un error.
      El admin no siempre sabe si lo está, y hacerlo fallar solo lo confundiría.

    Queda registrado en auditoría quién destrabó a quién.
    """
    session_factory = _get_session_factory(request)

    async with session_factory() as session:
        usuario = (
            await session.execute(
                select(UsuarioModel).where(UsuarioModel.id == usuario_id)
            )
        ).scalar_one_or_none()

        if usuario is None or usuario.eliminado_en is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado.",
            )

        estaba_bloqueada, _, _ = _estado_de_bloqueo(usuario)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        username = usuario.username
        await session.commit()

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        session_factory,
        actor=principal.email,
        accion=AccionAuditoria.USUARIO_EDICION,
        modulo=ModuloAuditoria.USUARIOS,
        entidad=EntidadAuditoria.USUARIO,
        entidad_id=str(usuario_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=(
            f"Destrabó la cuenta de {username}, bloqueada por intentos "
            "fallidos. La contraseña no se tocó."
            if estaba_bloqueada
            else (
                f"Pidió destrabar la cuenta de {username}, que no estaba "
                "bloqueada. Se limpió el contador de intentos fallidos."
            )
        ),
    )

    return DesbloquearCuentaResponse(
        usuario_id=str(usuario_id),
        username=username,
        estaba_bloqueada=estaba_bloqueada,
    )
