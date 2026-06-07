"""Servicio de storage para la foto de perfil del alumno (C-56, D1, D7).

La foto de perfil es MUTABLE y RENOVABLE: se almacena en el bucket NO-WORM
``activeexam-perfil`` (SSE-S3, sin Object Lock), separado del bucket de
evidencia WORM (Compliance mode). Mezclarlos violaría el derecho de supresion
de la Ley 25.326 (la foto de perfil se elimina al egreso; la evidencia de examen
no puede borrarse durante la retencion).

El binario NO transita el backend como archivo: el alumno captura el dataURL
en el cliente, el backend recibe la imagen en base64, la decodifica, calcula el
hash SHA-256, y la sube directamente al bucket via SDK (o via HTTP PUT firmado).

El hash SHA-256 se persiste en la DB para verificar integridad sin requerir
Object Lock (la integridad del binario se valida comparando hash_sha256 de la
foto descargada contra el hash almacenado en foto_referencia.hash_sha256).

PRODUCCION: reemplazar el ``_PutFn`` callable con el SDK boto3/minio real,
inyectado desde la capa de composicion (create_app / wiring). El contrato del
puerto no cambia.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from dataclasses import dataclass


# Tipo del callable que sube el binario al bucket. En produccion: boto3 put_object.
# En tests: un callable en memoria que almacena los bytes sin red.
_PutFn = Callable[[str, str, bytes], None]  # (bucket, key, data) -> None


@dataclass(frozen=True, slots=True)
class FotoSubida:
    """Resultado de subir la foto al bucket."""

    uri_storage: str  # key del objeto en el bucket (ruta relativa)
    hash_sha256: str  # hash SHA-256 del contenido (integridad)
    bucket: str       # nombre del bucket donde se almaceno


class ProfilePhotoStorageService:
    """Servicio de subida de la foto de perfil al bucket no-WORM (C-56, D1).

    Encapsula:
    - La decodificacion del dataURL base64 del cliente.
    - El calculo del hash SHA-256 del contenido.
    - La subida del binario al bucket via el callable inyectado.

    La clave del objeto en el bucket sigue el patron:
        perfil/{usuario_id}/{hash_sha256[:8]}.jpg

    Esto garantiza unicidad por contenido y usuario sin depender de UUIDs
    adicionales, y facilita la verificacion de integridad por key.

    Args:
        bucket: nombre del bucket de perfiles (sin Object Lock).
        put_fn: callable (bucket, key, data) -> None que sube el binario.
            En produccion: adaptador del SDK boto3/minio.
    """

    def __init__(self, *, bucket: str, put_fn: _PutFn) -> None:
        self._bucket = bucket
        self._put = put_fn

    def subir_foto_perfil(self, *, usuario_id: str, imagen_bytes: bytes) -> FotoSubida:
        """Calcula el hash SHA-256 y sube la foto al bucket.

        Args:
            usuario_id: UUID del usuario (para el prefijo de la key).
            imagen_bytes: bytes del binario de la foto (JPEG/PNG/WebP).

        Returns:
            ``FotoSubida`` con la uri_storage, hash_sha256 y bucket.
        """
        hash_sha256 = hashlib.sha256(imagen_bytes).hexdigest()
        key = f"perfil/{usuario_id}/{hash_sha256[:8]}.jpg"
        self._put(self._bucket, key, imagen_bytes)
        return FotoSubida(uri_storage=key, hash_sha256=hash_sha256, bucket=self._bucket)


def decodificar_imagen_base64(data_url: str) -> bytes:
    """Decodifica un dataURL base64 (data:image/...;base64,...) a bytes.

    Acepta tanto el formato completo (con el prefijo data:...) como el base64
    puro (sin prefijo). Si el formato es invalido, lanza ValueError.

    Args:
        data_url: string base64 con o sin prefijo 'data:image/...;base64,'.

    Returns:
        bytes del contenido de la imagen.

    Raises:
        ValueError: si el string no es base64 valido.
    """
    if "," in data_url:
        # Formato: 'data:image/jpeg;base64,<base64data>'
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url

    try:
        return base64.b64decode(b64.strip())
    except Exception as exc:
        raise ValueError(f"Formato de imagen invalido (no es base64): {exc}") from exc
