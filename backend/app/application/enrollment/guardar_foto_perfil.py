"""Application service: GuardarFotoPerfilService (C-56, task 5.1) — EN PAUSA.

Guardaba la foto de perfil en el bucket MinIO (no-WORM) y dejaba en
``foto_referencia`` solo los punteros al objeto (``uri_storage``, ``bucket``).

POR QUE ESTA COMENTADO
----------------------
Esas dos columnas las crea la migración 0007, de la rama "full", que **no está
aplicada en ninguna base viva**: la cadena que corre en producción y en dev es la
de activeexam (0005 -> 0008 -> ...), donde la foto va como BYTEA en
``foto_bytes``. Con la tabla real, este servicio subía la foto al bucket y recién
después reventaba al guardar la fila: objeto huérfano en MinIO y alumno sin foto.

El código queda acá tal cual porque MinIO es a donde se vuelve. Para reactivarlo:

  1. migrar ``foto_referencia`` para que tenga ``uri_storage`` y ``bucket``
  2. descomentar esas columnas en ``FotoReferenciaModel``
  3. descomentar ``FotoReferenciaRepository.crear_en_bucket``
  4. descomentar la clase de abajo, su import y la rama ``else`` de
     ``presentation/api/v1/enrollment/router.py::guardar_foto_perfil``

Mientras tanto, el camino vivo es ``GuardarFotoPerfilActiveExamService``
(``guardar_foto_perfil_activeexam.py``), que persiste el binario en Postgres.
"""

from __future__ import annotations

# from sqlalchemy.ext.asyncio import AsyncSession
#
# from app.infrastructure.persistence.repositories.biometric_reference import (
#     FotoReferenciaRepository,
# )
# from app.infrastructure.storage.profile_photo import (
#     ProfilePhotoStorageService,
#     decodificar_imagen_base64,
# )
#
#
# class GuardarFotoPerfilService:
#     """Orquesta la persistencia de la foto de perfil del alumno.
#
#     Args:
#         session: sesion SQLAlchemy async (inyectada desde el endpoint).
#         storage: servicio de subida al bucket de perfiles.
#     """
#
#     def __init__(
#         self,
#         *,
#         session: AsyncSession,
#         storage: ProfilePhotoStorageService,
#     ) -> None:
#         self._session = session
#         self._storage = storage
#         self._repo = FotoReferenciaRepository(session)
#
#     async def ejecutar(
#         self,
#         *,
#         usuario_id: str,
#         imagen_base64: str,
#     ) -> str:
#         """Persiste la foto de perfil y devuelve el foto_referencia_id.
#
#         Args:
#             usuario_id: UUID del usuario autenticado (del token JWT).
#             imagen_base64: dataURL base64 de la foto capturada en el cliente.
#
#         Returns:
#             ``foto_referencia_id`` (UUID str) del nuevo registro en DB.
#
#         Raises:
#             ValueError: si el formato de la imagen no es base64 valido.
#         """
#         # 1. Decodificar el dataURL base64 a bytes.
#         imagen_bytes = decodificar_imagen_base64(imagen_base64)
#
#         # 2. Subir al bucket y calcular hash SHA-256.
#         foto_subida = self._storage.subir_foto_perfil(
#             usuario_id=usuario_id,
#             imagen_bytes=imagen_bytes,
#         )
#
#         # 3. Marcar las fotos anteriores como no vigentes (invariante: solo una vigente).
#         await self._repo.marcar_anteriores_no_vigentes(usuario_id)
#
#         # 4. Crear el nuevo registro vigente.
#         foto = await self._repo.crear_en_bucket(
#             usuario_id=usuario_id,
#             uri_storage=foto_subida.uri_storage,
#             hash_sha256=foto_subida.hash_sha256,
#             bucket=foto_subida.bucket,
#         )
#
#         return foto.id
