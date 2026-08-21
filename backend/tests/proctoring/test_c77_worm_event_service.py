"""Tests de integracion del deposito WORM adicional en ingestar_evento (c-77, 18.5).

Llama a ``event_service.ingestar_evento`` DIRECTO (sin pasar por el router HTTP
ni por ``MediaPipeReinferencia``) con un stub PURO de ``ReinferenciaPort`` — asi
evitamos instanciar el motor MediaPipe real en este test file. Sigue siendo un
test de integracion real: Postgres real (``activeexam_engine``/``db_session`` de
``tests/proctoring/conftest.py``, sin mocks de DB) + MinIO real en Docker cuando
corresponde (regla dura #4).

Casos:
  1. worm_storage=None -> comportamiento IDENTICO al actual (screenshot solo en
     Postgres, columnas worm_* NULL). Es la RED DE SEGURIDAD de este change.
  2. worm_storage configurado (MinIO real) -> el evento se persiste en DB igual
     que siempre Y ADEMAS aparece en el bucket con Object Lock; columnas worm_*
     pobladas.
  3. worm_storage cuyo `deposit` siempre falla (simula MinIO caido/inalcanzable)
     -> NO tumba la ingesta: el evento se persiste igual en Postgres, worm_*
     quedan NULL.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
from app.application.proctoring.reinferencia import ResultadoReinferencia
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.storage.worm import build_boto3_worm_storage

pytestmark = pytest.mark.asyncio

# Sesiones creadas por _crear_sesion() no tienen alumno_idnumber/email (legacy,
# sin identidad) -> principal_es_dueno_de_sesion siempre las deja pasar (H1). Un
# principal cualquiera alcanza para estos tests de WORM, que no ejercitan el
# guard de pertenencia (eso lo cubre test_h1_idor_pertenencia_sesion.py).
_PRINCIPAL_TEST = AuthenticatedPrincipal(username="estudiante1", email="estudiante1@activeexam.local")

_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_MINIO_ENDPOINT = os.environ.get("MINIO_TEST_ENDPOINT", "localhost:9010")
_MINIO_ACCESS_KEY = os.environ.get("MINIO_TEST_ACCESS_KEY", "minioadmin")
_MINIO_SECRET_KEY = os.environ.get("MINIO_TEST_SECRET_KEY", "minioadmin123")
_MINIO_BUCKET = "activeexam-evidencia-test"


@dataclass
class _ReinferenciaStub:
    """Stub PURO del puerto — NO instancia MediaPipe."""

    def evaluar(
        self, screenshot_b64: str | None, face_count_cliente: int | None
    ) -> ResultadoReinferencia:
        if screenshot_b64 is None:
            return ResultadoReinferencia(face_count_servidor=None, veredicto="no_evaluado")
        return ResultadoReinferencia(face_count_servidor=1, veredicto="coincide")


class _WormStorageSiempreFalla:
    """Simula MinIO inalcanzable: cualquier deposit() levanta excepcion de red."""

    def deposit(self, *, object_key: str, data: bytes, retain_until: str):
        raise ConnectionError("MinIO endpoint inalcanzable (simulado)")

    def fetch(self, *, object_key: str) -> bytes:
        raise ConnectionError("MinIO endpoint inalcanzable (simulado)")


async def _crear_sesion(db_session: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="test")
    db_session.add(sesion)
    await db_session.commit()
    await db_session.refresh(sesion)
    return sesion.id


def _worm_storage_real():
    return build_boto3_worm_storage(
        endpoint=_MINIO_ENDPOINT,
        access_key=_MINIO_ACCESS_KEY,
        secret_key=_MINIO_SECRET_KEY,
        bucket=_MINIO_BUCKET,
        use_ssl=False,
    )


def _asegurar_bucket_con_object_lock() -> None:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=f"http://{_MINIO_ENDPOINT}",
        aws_access_key_id=_MINIO_ACCESS_KEY,
        aws_secret_access_key=_MINIO_SECRET_KEY,
    )
    try:
        client.head_bucket(Bucket=_MINIO_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=_MINIO_BUCKET, ObjectLockEnabledForBucket=True)


# ---------------------------------------------------------------------------
# Caso 1: worm_storage=None -> comportamiento IDENTICO al actual.
# ---------------------------------------------------------------------------


async def test_sin_worm_storage_persiste_solo_en_postgres(db_session: AsyncSession) -> None:
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="FACE_ABSENT",
        severidad="alto",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_PNG_1X1_B64,
        face_count_cliente=1,
        worm_storage=None,
    )

    assert evento.screenshot_b64 == _PNG_1X1_B64
    assert evento.worm_object_key is None
    assert evento.worm_uri is None
    assert evento.worm_retain_until is None


async def test_sin_worm_storage_y_sin_screenshot_tambien_identico(
    db_session: AsyncSession,
) -> None:
    """Triangulacion: sin screenshot tampoco pasa nada raro."""
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="GAZE_DEVIATION",
        severidad="bajo",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        worm_storage=None,
    )

    assert evento.screenshot_b64 is None
    assert evento.worm_object_key is None


# ---------------------------------------------------------------------------
# Caso 3: MinIO inalcanzable durante el deposito -> la ingesta NO se cae.
# ---------------------------------------------------------------------------


async def test_fallo_de_deposit_no_tumba_la_ingesta(db_session: AsyncSession) -> None:
    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="MULTIPLE_FACES",
        severidad="critico",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_PNG_1X1_B64,
        face_count_cliente=2,
        worm_storage=_WormStorageSiempreFalla(),
    )

    # El evento SE PERSISTIO igual — la evidencia en DB es la red de seguridad.
    assert evento.screenshot_b64 == _PNG_1X1_B64
    assert evento.worm_object_key is None
    assert evento.worm_uri is None
    assert evento.worm_retain_until is None


# ---------------------------------------------------------------------------
# Caso 2: worm_storage configurado contra MinIO real (Docker).
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
async def test_con_minio_configurado_persiste_en_db_y_en_el_bucket(
    db_session: AsyncSession,
) -> None:
    import boto3

    _asegurar_bucket_con_object_lock()
    client = boto3.client(
        "s3",
        endpoint_url=f"http://{_MINIO_ENDPOINT}",
        aws_access_key_id=_MINIO_ACCESS_KEY,
        aws_secret_access_key=_MINIO_SECRET_KEY,
    )

    session_id = await _crear_sesion(db_session)

    evento = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="FACE_ABSENT",
        severidad="alto",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_PNG_1X1_B64,
        face_count_cliente=1,
        worm_storage=_worm_storage_real(),
    )

    # DB: sigue igual que siempre (fuente de verdad).
    assert evento.screenshot_b64 == _PNG_1X1_B64
    # ADEMAS: referencia WORM poblada.
    assert evento.worm_object_key == f"{session_id}/{evento.id}.bin"
    assert evento.worm_uri is not None
    assert evento.worm_retain_until is not None

    # Y el binario esta REALMENTE en el bucket (no solo la referencia en DB).
    objeto_s3 = client.get_object(Bucket=_MINIO_BUCKET, Key=evento.worm_object_key)
    assert objeto_s3["Body"].read() == base64.b64decode(_PNG_1X1_B64)
    # Object Lock realmente aplicado (no solo el llamado al SDK).
    retencion = client.get_object_retention(Bucket=_MINIO_BUCKET, Key=evento.worm_object_key)
    assert retencion["Retention"]["Mode"] == "COMPLIANCE"


@pytest.mark.requires_stack
async def test_dos_eventos_de_la_misma_sesion_usan_object_keys_distintos(
    db_session: AsyncSession,
) -> None:
    """Triangulacion: dos screenshots distintos de la MISMA sesion no se pisan."""
    _asegurar_bucket_con_object_lock()
    session_id = await _crear_sesion(db_session)
    storage = _worm_storage_real()

    evento_1 = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="GAZE_DEVIATION",
        severidad="medio",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_PNG_1X1_B64,
        worm_storage=storage,
    )
    evento_2 = await event_service.ingestar_evento(
        db=db_session,
        session_id=session_id,
        tipo="GAZE_DEVIATION",
        severidad="medio",
        ts_cliente=datetime.now(timezone.utc),
        reinferencia=_ReinferenciaStub(),
        principal=_PRINCIPAL_TEST,
        screenshot_base64=_PNG_1X1_B64,
        worm_storage=storage,
    )

    assert evento_1.worm_object_key != evento_2.worm_object_key
    assert evento_1.id != evento_2.id
