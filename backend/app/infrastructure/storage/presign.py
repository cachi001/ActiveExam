"""Puerto + adaptador de URL firmada (presign) para storage MinIO/S3 (C-07 D2).

La foto institucional de referencia sube DIRECTO al storage por URL firmada, sin
transitar el backend (RN-CC-04, RN-GLB-01: el cliente es sensor no confiable; el
backend registra metadata y valida hash, no recibe el binario). Este modulo expone
un puerto ``PresignService`` y un adaptador minimo.

El adaptador concreto contra el SDK de MinIO/S3 (boto3/minio) se cablea en
produccion; aqui se define el contrato y una implementacion determinista que
construye la URL/campos del POST firmado a partir de la config de storage de C-04.
La firma criptografica real (SigV4) la hace el SDK en produccion; el contrato
(devolver una URL firmada con expiracion + el key del objeto) es lo que C-07 fija
y los tests ejercen sin red.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# Expiracion de la URL de descarga de clip de evidencia: 15 min (RN-CC-05, C-12).
DOWNLOAD_EXPIRES_SECONDS = 900


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """Resultado de un presign: a donde subir y con que key (sin binario)."""

    url: str
    object_key: str
    expires_in: int
    method: str = "PUT"


@dataclass(frozen=True, slots=True)
class PresignedDownload:
    """Resultado de un presign de descarga (GET firmado con expiracion)."""

    url: str
    object_key: str
    expires_in: int
    method: str = "GET"


class PresignService(ABC):
    """Puerto de generacion de URLs firmadas de subida/descarga."""

    @abstractmethod
    def presign_upload(
        self, *, object_key: str, expires_in: int = 900
    ) -> PresignedUpload:
        """Genera una URL firmada para subir el objeto ``object_key`` al bucket."""

    @abstractmethod
    def presign_download(
        self, *, object_key: str, expires_in: int = DOWNLOAD_EXPIRES_SECONDS
    ) -> PresignedDownload:
        """Genera una URL firmada de GET para descargar el clip (expira 15 min)."""


class StoragePresignService(PresignService):
    """Adaptador de presign sobre el endpoint/bucket de storage (config C-04).

    Construye el contrato del presign; en produccion la firma SigV4 la agrega el
    SDK. La URL apunta al endpoint configurado y al bucket de evidencia/referencia.
    """

    def __init__(self, *, endpoint: str, bucket: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._bucket = bucket

    def presign_upload(
        self, *, object_key: str, expires_in: int = 900
    ) -> PresignedUpload:
        # En produccion: signer.generate_presigned_url(...). Aqui se devuelve la
        # URL canonica del objeto + expiracion; el query de firma lo agrega el SDK.
        url = f"{self._endpoint}/{self._bucket}/{object_key}?X-Amz-Expires={expires_in}"
        return PresignedUpload(url=url, object_key=object_key, expires_in=expires_in)

    def presign_download(
        self, *, object_key: str, expires_in: int = DOWNLOAD_EXPIRES_SECONDS
    ) -> PresignedDownload:
        # URL firmada de GET con expiracion (15 min para clips, RN-CC-05). El query
        # SigV4 (X-Amz-Signature) lo agrega el SDK en produccion; aqui se fija el
        # contrato: la URL caduca a los ``expires_in`` segundos.
        url = (
            f"{self._endpoint}/{self._bucket}/{object_key}"
            f"?X-Amz-Expires={expires_in}&response-content-disposition=attachment"
        )
        return PresignedDownload(url=url, object_key=object_key, expires_in=expires_in)
