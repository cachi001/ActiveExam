"""Tests del adaptador boto3 del puerto WORM (c-77) contra MinIO real.

Sin mocks de boto3/S3 (regla dura #4): habla con un MinIO real (Docker) via
``build_boto3_worm_storage``. Verifica no solo que el SDK se invoco con los
parametros correctos, sino que el Object Lock REAL impide sobreescribir/borrar
antes de ``retain_until`` (RN-CC-06, D4 — modo Compliance).

Requiere el servicio levantado: exporta RUN_STACK_TESTS=1 y un MinIO real en
MINIO_TEST_ENDPOINT (default localhost:9010, ver docker run en el change c-77).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.requires_stack

from app.infrastructure.storage.worm import build_boto3_worm_storage

_ENDPOINT = os.environ.get("MINIO_TEST_ENDPOINT", "localhost:9010")
_ACCESS_KEY = os.environ.get("MINIO_TEST_ACCESS_KEY", "minioadmin")
_SECRET_KEY = os.environ.get("MINIO_TEST_SECRET_KEY", "minioadmin123")
_BUCKET = "activeexam-evidencia-test"


def _ensure_bucket_con_object_lock(bucket: str) -> None:
    """Crea (si no existe) un bucket CON Object Lock habilitado desde el arranque.

    Object Lock solo se puede activar en la CREACION del bucket (S3/MinIO), nunca
    despues — por eso el fixture de test lo crea explicito, igual que hara el
    init del docker-compose (tarea 19).
    """
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=f"http://{_ENDPOINT}",
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
    )
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)


@pytest.fixture(scope="module", autouse=True)
def _bucket() -> None:
    _ensure_bucket_con_object_lock(_BUCKET)


def _storage():
    return build_boto3_worm_storage(
        endpoint=_ENDPOINT,
        access_key=_ACCESS_KEY,
        secret_key=_SECRET_KEY,
        bucket=_BUCKET,
        use_ssl=False,
    )


def _retain_until_iso(*, dias: int = 1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


class TestDepositoYRedescarga:
    """16.3 caso 1: sube un objeto, lo re-descarga, el hash coincide."""

    def test_deposit_y_fetch_coinciden_por_hash(self) -> None:
        storage = _storage()
        object_key = f"evidencia/{uuid.uuid4()}.bin"
        data = b"contenido de evidencia de prueba - caso 1"

        objeto = storage.deposit(
            object_key=object_key, data=data, retain_until=_retain_until_iso()
        )

        assert objeto.object_key == object_key
        assert objeto.mode == "COMPLIANCE"

        descargado = storage.fetch(object_key=object_key)
        assert hashlib.sha256(descargado).hexdigest() == hashlib.sha256(data).hexdigest()

    def test_deposit_y_fetch_con_otro_binario_distinto(self) -> None:
        """Triangulacion: distinto object_key/contenido/retain_until — no un fake-it."""
        storage = _storage()
        object_key = f"evidencia/{uuid.uuid4()}.bin"
        data = b"otro contenido completamente diferente, mas largo, caso 2 de prueba"

        storage.deposit(
            object_key=object_key, data=data, retain_until=_retain_until_iso(dias=5)
        )
        descargado = storage.fetch(object_key=object_key)

        assert descargado == data
        assert hashlib.sha256(descargado).hexdigest() == hashlib.sha256(data).hexdigest()


class TestObjectLockCompliance:
    """16.3: el Object Lock REAL impide sobreescribir/borrar antes de retain_until."""

    def test_no_se_puede_borrar_antes_de_retain_until(self) -> None:
        import boto3
        from botocore.exceptions import ClientError

        storage = _storage()
        object_key = f"evidencia/{uuid.uuid4()}.bin"
        storage.deposit(
            object_key=object_key,
            data=b"evidencia protegida",
            retain_until=_retain_until_iso(dias=1),
        )

        client = boto3.client(
            "s3",
            endpoint_url=f"http://{_ENDPOINT}",
            aws_access_key_id=_ACCESS_KEY,
            aws_secret_access_key=_SECRET_KEY,
        )
        # Un DELETE sin version_id en un bucket versionado (Object Lock exige
        # versionado) solo agrega un delete-marker: NO toca la version protegida.
        # La prueba real de Compliance es borrar la VERSION concreta que quedo
        # bloqueada -> MinIO debe rechazarlo con 403, no alcanza con inspeccionar
        # los argumentos que se le pasaron al SDK.
        version_id = client.list_object_versions(
            Bucket=_BUCKET, Prefix=object_key
        )["Versions"][0]["VersionId"]

        with pytest.raises(ClientError) as exc_info:
            client.delete_object(
                Bucket=_BUCKET,
                Key=object_key,
                VersionId=version_id,
                BypassGovernanceRetention=True,
            )
        assert exc_info.value.response["Error"]["Code"] in {
            "AccessDenied",
            "InvalidRequest",
            "ObjectLocked",
        }

        # Sigue estando intacto: la evidencia no se perdio.
        assert storage.fetch(object_key=object_key) == b"evidencia protegida"

    def test_no_se_puede_sobreescribir_con_retencion_mas_corta(self) -> None:
        """Triangulacion: intenta ACORTAR la retencion (otro vector de ataque)."""
        import boto3
        from botocore.exceptions import ClientError

        storage = _storage()
        object_key = f"evidencia/{uuid.uuid4()}.bin"
        storage.deposit(
            object_key=object_key,
            data=b"version original",
            retain_until=_retain_until_iso(dias=10),
        )

        client = boto3.client(
            "s3",
            endpoint_url=f"http://{_ENDPOINT}",
            aws_access_key_id=_ACCESS_KEY,
            aws_secret_access_key=_SECRET_KEY,
        )
        # Intenta ACORTAR la retencion (sigue en el futuro, pero antes que la
        # original de 10 dias) -> Compliance lo rechaza: nadie, ni el root, puede
        # reducir una retencion ya fijada (RN-CC-06).
        retencion_mas_corta = datetime.now(timezone.utc) + timedelta(days=2)
        with pytest.raises(ClientError) as exc_info:
            client.put_object_retention(
                Bucket=_BUCKET,
                Key=object_key,
                Retention={"Mode": "COMPLIANCE", "RetainUntilDate": retencion_mas_corta},
            )
        assert exc_info.value.response["Error"]["Code"] in {
            "AccessDenied",
            "InvalidRequest",
        }
