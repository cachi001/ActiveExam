"""Application service: GuardarFotoPerfilService (C-56, task 5.1).

Orquesta:
1. Decodificar el dataURL base64 a bytes.
2. Calcular el hash SHA-256 y subir la foto al bucket no-WORM.
3. Marcar las fotos anteriores del usuario como no vigentes.
4. Crear el nuevo registro en foto_referencia.

Devuelve el ``foto_referencia_id`` (UUID opaco) para que el cliente lo
persista en el store (no el binario de la foto).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.repositories.biometric_reference import (
    FotoReferenciaRepository,
)
from app.infrastructure.storage.profile_photo import (
    ProfilePhotoStorageService,
    decodificar_imagen_base64,
)


class GuardarFotoPerfilService:
    """Orquesta la persistencia de la foto de perfil del alumno.

    Args:
        session: sesion SQLAlchemy async (inyectada desde el endpoint).
        storage: servicio de subida al bucket de perfiles.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        storage: ProfilePhotoStorageService,
    ) -> None:
        self._session = session
        self._storage = storage
        self._repo = FotoReferenciaRepository(session)

    async def ejecutar(
        self,
        *,
        usuario_id: str,
        imagen_base64: str,
    ) -> str:
        """Persiste la foto de perfil y devuelve el foto_referencia_id.

        Args:
            usuario_id: UUID del usuario autenticado (del token JWT).
            imagen_base64: dataURL base64 de la foto capturada en el cliente.

        Returns:
            ``foto_referencia_id`` (UUID str) del nuevo registro en DB.

        Raises:
            ValueError: si el formato de la imagen no es base64 valido.
        """
        # 1. Decodificar el dataURL base64 a bytes.
        imagen_bytes = decodificar_imagen_base64(imagen_base64)

        # 2. Subir al bucket y calcular hash SHA-256.
        foto_subida = self._storage.subir_foto_perfil(
            usuario_id=usuario_id,
            imagen_bytes=imagen_bytes,
        )

        # 3. Marcar las fotos anteriores como no vigentes (invariante: solo una vigente).
        await self._repo.marcar_anteriores_no_vigentes(usuario_id)

        # 4. Crear el nuevo registro vigente.
        foto = await self._repo.crear(
            usuario_id=usuario_id,
            uri_storage=foto_subida.uri_storage,
            hash_sha256=foto_subida.hash_sha256,
            bucket=foto_subida.bucket,
        )

        return foto.id
