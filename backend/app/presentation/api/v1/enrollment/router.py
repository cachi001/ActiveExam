"""Router de enrollment biometrico (C-56).

Endpoints del alumno autenticado:
- ``POST /enrollment/foto-perfil``: sube la foto de perfil al bucket no-WORM
  y persiste los metadatos en ``foto_referencia``.
- ``POST /enrollment/embedding-referencia``: recibe el embedding 128-d,
  lo cifra at-rest con Fernet, y lo persiste en ``embedding_referencia``.

Autenticacion: Bearer JWT (rol ``estudiante``). HTTP 401 sin token. HTTP 403
con token de rol incorrecto.

La logica de negocio se delega a los application services
``GuardarFotoPerfilService`` y ``GuardarEmbeddingReferenciaService``.
El storage y el cifrado se inyectan desde el app state.

D3 del design: el backend acepta el embedding client-side (NO re-infiere en
enrollment). La re-inferencia aplica durante el examen (C-09 D2).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.enrollment.guardar_embedding_referencia import (
    DimensionError,
    GuardarEmbeddingReferenciaService,
)
from app.application.enrollment.guardar_foto_perfil import GuardarFotoPerfilService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.crypto.embedding_encryption import (
    ConfigurationError,
    EmbeddingEncryptionService,
)
from app.infrastructure.persistence.session import get_session
from app.infrastructure.storage.profile_photo import ProfilePhotoStorageService
from app.presentation.api.v1.auth.dependencies import require_roles
from app.presentation.api.v1.enrollment.schemas import (
    EmbeddingReferenciaRequest,
    EmbeddingReferenciaResponse,
    FotoPerfilRequest,
    FotoPerfilResponse,
)

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


def _get_profile_storage(request: Request) -> ProfilePhotoStorageService:
    """Toma el servicio de storage de perfiles del app state o 500."""
    storage = getattr(request.app.state, "profile_photo_storage", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Servicio de storage de perfiles no inicializado.",
        )
    return storage


def _get_embedding_encryption() -> EmbeddingEncryptionService:
    """Instancia el servicio de cifrado de embeddings desde la config."""
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
    encryption = _get_embedding_encryption()

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
