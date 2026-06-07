"""Application service: GuardarFotoPerfilSlimService (c-57, D6).

Servicio de aplicacion para persistir la foto de perfil del alumno en el
modulo slim (Railway / Postgres estandar, sin MinIO).

Diferencia con ``GuardarFotoPerfilService`` (full):
  - GuardarFotoPerfilService: recibe un ``ProfilePhotoStorageService`` (MinIO),
    sube al bucket y persiste la uri_storage + bucket en DB.
  - GuardarFotoPerfilSlimService: recibe solo la session, persiste el BYTEA
    directamente en DB via ``DbPhotoStorageService``.

DISENO (D6): se crea un servicio slim paralelo en lugar de contaminar el
servicio del full con logica del slim. El enrollment router detecta el tipo
de storage del app state y despacha al servicio correcto.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.storage.db_photo_storage import DbPhotoStorageService


class GuardarFotoPerfilSlimService:
    """Orquesta la persistencia de la foto de perfil del alumno en el slim.

    Persiste el BYTEA directamente en ``foto_referencia.foto_bytes`` via
    ``DbPhotoStorageService``. Sin MinIO, sin uri_storage.

    Args:
        session: sesion SQLAlchemy async (inyectada desde el endpoint).
    """

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session
        self._storage = DbPhotoStorageService()

    async def ejecutar(
        self,
        *,
        usuario_id: str,
        imagen_base64: str,
    ) -> str:
        """Persiste la foto de perfil y devuelve el foto_referencia_id.

        Args:
            usuario_id: UUID str del usuario autenticado (del token JWT).
            imagen_base64: dataURL base64 de la foto capturada en el cliente.

        Returns:
            ``foto_referencia_id`` (UUID str) del nuevo registro en DB.

        Raises:
            ValueError: si el base64 es invalido o la foto excede 500 KB.
        """
        return await self._storage.guardar(
            session=self._session,
            usuario_id=usuario_id,
            imagen_base64=imagen_base64,
        )
