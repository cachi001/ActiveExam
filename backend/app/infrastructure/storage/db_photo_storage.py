"""Adaptador de storage de foto de perfil en DB BYTEA (slim, c-57, D1).

En el modulo slim (Railway / Postgres estandar), la foto de perfil se persiste
directamente como BYTEA en la columna ``foto_referencia.foto_bytes``, sin MinIO.

IMPLEMENTACION: usa SQLAlchemy Core (INSERT/UPDATE via text()) en lugar de ORM
para evitar el conflicto de MetaData entre ``FotoReferenciaModel`` (full, con
uri_storage/bucket) y la variante slim (con foto_bytes). El Core permite trabajar
directamente con la tabla sin declarar un modelo ORM nuevo.

LIMITE DE TAMANO: <= 500 KB (decodificado). Fotos mas grandes se rechazan con
``ValueError`` (el router las convierte en HTTP 422).

INVARIANTE: solo un registro ``vigente = True`` por usuario. Al guardar una foto
nueva, las anteriores del mismo usuario se marcan ``vigente = False``.
"""

from __future__ import annotations

import base64
import hashlib
import uuid as _uuid_module

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Limite de tamano de la foto decodificada (bytes).
_MAX_FOTO_BYTES = 500 * 1024  # 500 KB


class DbPhotoStorageService:
    """Servicio de storage de foto de perfil en DB BYTEA (slim).

    A diferencia de ``ProfilePhotoStorageService`` (MinIO), esta implementacion
    persiste el binario directamente en Postgres. Compatible con Railway
    (Postgres estandar, sin S3).

    Usa SQLAlchemy Core (sin ORM) para evitar conflictos de MetaData con
    ``FotoReferenciaModel`` del full (que tiene columnas uri_storage/bucket).

    Uso:
        service = DbPhotoStorageService()
        foto_id = await service.guardar(session, usuario_id, imagen_base64)
    """

    async def guardar(
        self,
        session: AsyncSession,
        usuario_id: str,
        imagen_base64: str,
    ) -> str:
        """Persiste la foto de perfil en DB (BYTEA) y retorna el UUID creado.

        Flujo:
          1. Decodifica el dataURL base64 a bytes.
          2. Valida que el tamano sea <= 500 KB.
          3. Calcula el hash SHA-256 del contenido.
          4. Marca las fotos anteriores del usuario como vigente=False.
          5. Inserta la nueva fila con foto_bytes, hash_sha256 y vigente=True.
          6. Flush para que la DB asigne el UUID; retorna el UUID.

        Args:
            session: sesion SQLAlchemy async activa (el caller hace commit).
            usuario_id: UUID str del usuario (FK a usuario.id).
            imagen_base64: string base64 con o sin prefijo 'data:image/...;base64,'.

        Returns:
            UUID str del nuevo registro en foto_referencia.

        Raises:
            ValueError: si el base64 es invalido o la foto excede 500 KB.
        """
        imagen_bytes = _decodificar_base64(imagen_base64)

        if len(imagen_bytes) > _MAX_FOTO_BYTES:
            raise ValueError(
                f"La foto excede el limite de {_MAX_FOTO_BYTES // 1024} KB "
                f"({len(imagen_bytes) // 1024} KB decodificado). "
                "Comprimila antes de subirla."
            )

        hash_sha256 = hashlib.sha256(imagen_bytes).hexdigest()
        nuevo_id = str(_uuid_module.uuid4())

        # Marcar fotos anteriores como no vigentes (invariante: solo 1 vigente).
        await session.execute(
            text(
                "UPDATE foto_referencia "
                "SET vigente = false "
                "WHERE usuario_id = :usuario_id AND vigente = true"
            ),
            {"usuario_id": usuario_id},
        )

        # Insertar la nueva foto vigente usando Core SQL.
        # gen_random_uuid() o UUID generado en Python — usamos Python para consistencia.
        await session.execute(
            text(
                "INSERT INTO foto_referencia "
                "(id, usuario_id, foto_bytes, hash_sha256, vigente) "
                "VALUES (:id, :usuario_id, :foto_bytes, :hash_sha256, true)"
            ),
            {
                "id": nuevo_id,
                "usuario_id": usuario_id,
                "foto_bytes": imagen_bytes,
                "hash_sha256": hash_sha256,
            },
        )

        return nuevo_id


def _decodificar_base64(data_url: str) -> bytes:
    """Decodifica un dataURL base64 (con o sin prefijo) a bytes.

    Acepta:
      - Formato completo: 'data:image/jpeg;base64,<base64data>'
      - Base64 puro: '<base64data>'

    Raises:
        ValueError: si el string no es base64 valido.
    """
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url

    try:
        return base64.b64decode(b64.strip())
    except Exception as exc:
        raise ValueError(f"Formato de imagen invalido (no es base64): {exc}") from exc
