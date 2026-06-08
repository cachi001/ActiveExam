"""Router de enrollment biometrico (C-56 + C-61).

Endpoints del alumno autenticado:
- ``POST /enrollment/foto-perfil``: sube la foto de perfil al bucket no-WORM
  y persiste los metadatos en ``foto_referencia``.
- ``POST /enrollment/embedding-referencia``: recibe el embedding 128-d,
  lo cifra at-rest con Fernet, y lo persiste en ``embedding_referencia``.
- ``GET  /enrollment/foto-perfil``: devuelve la foto vigente del usuario
  autenticado como base64 en JSON (C-61, D7).
- ``GET  /enrollment/foto-perfil/{usuario_id}``: devuelve la foto de otro
  usuario (solo admin_sistema/proctor) (C-61, D7).

Autenticacion: Bearer JWT. HTTP 401 sin token. HTTP 403 con rol incorrecto.

La logica de negocio se delega a los application services
``GuardarFotoPerfilService`` y ``GuardarEmbeddingReferenciaService``.
El storage y el cifrado se inyectan desde el app state.

D3 del design: el backend acepta el embedding client-side (NO re-infiere en
enrollment). La re-inferencia aplica durante el examen (C-09 D2).

DATO SENSIBLE (Ley 25.326, C-61 D7): el binario de la foto NO se loguea.
El endpoint de foto ajena exige rol explicito (admin_sistema o proctor).
"""

from __future__ import annotations

import base64
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.enrollment.guardar_embedding_referencia import (
    DimensionError,
    GuardarEmbeddingReferenciaService,
)
from app.application.enrollment.guardar_foto_perfil import GuardarFotoPerfilService
from app.application.enrollment.guardar_foto_perfil_slim import GuardarFotoPerfilSlimService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.crypto.embedding_encryption import (
    ConfigurationError,
    EmbeddingEncryptionService,
)
from app.infrastructure.storage.db_photo_storage import DbPhotoStorageService
from app.infrastructure.storage.profile_photo import ProfilePhotoStorageService
from app.presentation.api.v1.auth.dependencies import require_roles
from app.presentation.api.v1.enrollment.schemas import (
    EmbeddingReferenciaRequest,
    EmbeddingReferenciaResponse,
    FotoPerfilRequest,
    FotoPerfilResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_require_estudiante = require_roles(Rol.ESTUDIANTE)


def _get_session_factory(request: Request):
    """Toma el session_factory del app state o 500 si no esta inicializado."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subsistema de persistencia no inicializado.",
        )
    return factory


def _get_profile_storage(request: Request) -> ProfilePhotoStorageService | DbPhotoStorageService:
    """Toma el servicio de storage de perfiles del app state o 500.

    Devuelve ``ProfilePhotoStorageService`` (full/MinIO) o ``DbPhotoStorageService``
    (slim/BYTEA). El endpoint ``guardar_foto_perfil`` detecta el tipo y despacha
    al servicio correcto.
    """
    storage = getattr(request.app.state, "profile_photo_storage", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Servicio de storage de perfiles no inicializado.",
        )
    return storage


def _get_embedding_encryption(request: Request) -> EmbeddingEncryptionService:
    """Toma el servicio de cifrado de embeddings del app state (slim) o lo instancia (full).

    En el slim (main_slim.py), el servicio se cablea en ``app.state.embedding_encryption``
    con la clave de ``SlimSettings.embedding_encryption_key`` (sin cargar Settings del full).
    En el full (main.py), se instancia desde la config completa.
    """
    service = getattr(request.app.state, "embedding_encryption", None)
    if service is not None:
        return service
    # Modo full: instanciar desde la config completa (Settings).
    try:
        return EmbeddingEncryptionService()
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Servicio de cifrado no disponible: {exc}",
        ) from exc


@router.post(
    "/foto-perfil",
    response_model=FotoPerfilResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sube la foto de perfil del alumno al storage y persiste la referencia.",
)
async def guardar_foto_perfil(
    body: FotoPerfilRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_estudiante),
) -> FotoPerfilResponse:
    """Persiste la foto de perfil del alumno autenticado.

    - Sube la foto al bucket de perfiles (no-WORM, SSE-S3).
    - Calcula el hash SHA-256 del contenido.
    - Persiste los metadatos en ``foto_referencia`` (DB).
    - Marca fotos anteriores del usuario como no vigentes.
    - Devuelve el ``foto_referencia_id`` (UUID opaco).

    HTTP 401 si no hay token. HTTP 403 si el rol no es ``estudiante``.
    """
    factory = _get_session_factory(request)
    storage = _get_profile_storage(request)

    # El UUID del usuario viene del claim ``sub`` del token (emitido por
    # own_issuer como str(usuario.id)). Si el subject falta (token malformado
    # que paso la validacion), se rechaza con 401.
    if not principal.subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no porta un subject (sub) valido.",
        )

    try:
        async with factory() as session:
            # Slim (Railway): storage es DbPhotoStorageService -> BYTEA en DB.
            # Full (produccion): storage es ProfilePhotoStorageService -> MinIO.
            if isinstance(storage, DbPhotoStorageService):
                service_slim = GuardarFotoPerfilSlimService(session=session)
                foto_id = await service_slim.ejecutar(
                    usuario_id=principal.subject,
                    imagen_base64=body.imagen_base64,
                )
            else:
                service = GuardarFotoPerfilService(session=session, storage=storage)
                foto_id = await service.ejecutar(
                    usuario_id=principal.subject,
                    imagen_base64=body.imagen_base64,
                )
            await session.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return FotoPerfilResponse(foto_referencia_id=UUID(foto_id))


@router.post(
    "/embedding-referencia",
    response_model=EmbeddingReferenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persiste el embedding biometrico de referencia cifrado at-rest.",
)
async def guardar_embedding_referencia(
    body: EmbeddingReferenciaRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_estudiante),
) -> EmbeddingReferenciaResponse:
    """Persiste el embedding 128-d cifrado at-rest.

    - Valida la dimension del embedding (debe ser exactamente 128).
    - Cifra el vector con Fernet (EMBEDDING_ENCRYPTION_KEY).
    - Persiste el ciphertext en ``embedding_referencia`` (DB).
    - Marca embeddings anteriores del usuario como no vigentes.
    - Devuelve el ``referencia_id`` (UUID opaco) al cliente.

    El embedding crudo NUNCA se loguea ni se persiste en claro.
    HTTP 401 sin token. HTTP 403 con rol incorrecto.
    HTTP 422 si el embedding no tiene 128 dimensiones.
    """
    # Idem foto-perfil: usar el UUID del sub, no el id_institucional.
    if not principal.subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no porta un subject (sub) valido.",
        )

    factory = _get_session_factory(request)
    encryption = _get_embedding_encryption(request)

    try:
        async with factory() as session:
            service = GuardarEmbeddingReferenciaService(
                session=session,
                encryption=encryption,
            )
            referencia_id = await service.ejecutar(
                usuario_id=principal.subject,
                embedding=body.embedding,
            )
            await session.commit()
    except DimensionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return EmbeddingReferenciaResponse(referencia_id=UUID(referencia_id))


# ---------------------------------------------------------------------------
# Helpers de lectura de foto (C-61, D7)
# ---------------------------------------------------------------------------


class FotoPerfilReadResponse(BaseModel):
    """Response de lectura de foto de perfil como base64 dataURL."""

    model_config = ConfigDict(extra="forbid")

    imagen_base64: str


async def _leer_foto_slim(
    session_factory: async_sessionmaker[AsyncSession],
    usuario_id: str,
) -> str | None:
    """Lee la foto vigente de un usuario desde la DB slim (BYTEA).

    Retorna el dataURL base64 o None si no existe foto vigente.
    El binario NO se loguea (Ley 25.326 — dato sensible).
    """
    async with session_factory() as session:
        result = await session.execute(
            text(
                "SELECT foto_bytes FROM foto_referencia "
                "WHERE usuario_id = :usuario_id AND vigente = true "
                "LIMIT 1"
            ),
            {"usuario_id": usuario_id},
        )
        row = result.fetchone()
        if row is None:
            return None
        foto_bytes: bytes = row[0]
    # Convertir a base64 dataURL (JPEG por convencion; el cliente acepta ambos).
    b64 = base64.b64encode(foto_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


# ---------------------------------------------------------------------------
# GET /enrollment/foto-perfil — foto propia del usuario autenticado (C-61, D7)
# ---------------------------------------------------------------------------


@router.get(
    "/foto-perfil",
    response_model=FotoPerfilReadResponse,
    summary="Devuelve la foto de perfil vigente del usuario autenticado (base64).",
)
async def obtener_foto_perfil_propia(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_roles(Rol.ESTUDIANTE, Rol.PROCTOR, Rol.ADMIN_SISTEMA)),
) -> FotoPerfilReadResponse:
    """Devuelve la foto vigente del usuario autenticado como base64 dataURL.

    - 200: foto en base64.
    - 401: sin token.
    - 404: sin foto vigente.

    DATO SENSIBLE (Ley 25.326): el binario no se loguea.
    """
    if not principal.subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no porta un subject (sub) valido.",
        )

    factory = _get_session_factory(request)
    imagen_base64 = await _leer_foto_slim(factory, principal.subject)

    if imagen_base64 is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay foto de perfil vigente para este usuario.",
        )

    return FotoPerfilReadResponse(imagen_base64=imagen_base64)


# ---------------------------------------------------------------------------
# GET /enrollment/foto-perfil/{usuario_id} — foto ajena (admin/proctor)
# ---------------------------------------------------------------------------

_require_staff = require_roles(Rol.ADMIN_SISTEMA, Rol.PROCTOR)


@router.get(
    "/foto-perfil/{usuario_id}",
    response_model=FotoPerfilReadResponse,
    summary="Devuelve la foto de perfil de otro usuario (solo admin/proctor).",
)
async def obtener_foto_perfil_ajena(
    usuario_id: str,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_staff),
) -> FotoPerfilReadResponse:
    """Devuelve la foto vigente de otro usuario (solo admin_sistema/proctor).

    - 200: foto en base64.
    - 401: sin token.
    - 403: rol insuficiente (un estudiante no puede ver la foto de otro).
    - 404: el usuario objetivo no tiene foto vigente.

    DATO SENSIBLE (Ley 25.326): el binario no se loguea. Finalidad acotada
    a supervision/gestion. El guard de rol es defensa en profundidad.
    """
    factory = _get_session_factory(request)
    imagen_base64 = await _leer_foto_slim(factory, usuario_id)

    if imagen_base64 is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay foto de perfil vigente para ese usuario.",
        )

    return FotoPerfilReadResponse(imagen_base64=imagen_base64)
