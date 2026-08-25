"""Servicio de ingestion de eventos de proctoring activeexam.

Orquesta:
  1. Verificar que la sesion existe (404 si no)
  2. Calcular sha256 del screenshot (integridad liviana, D9)
  3. Invocar la re-inferencia via ReinferenciaPort (NO importa mediapipe directamente)
  4. Persistir el evento con todos los campos

Depende del puerto ReinferenciaPort — el adapter concreto (MediaPipeReinferencia)
se inyecta desde main_activeexam.py via FastAPI Depends. Esto sigue DD-17 y mantiene
la capa de aplicacion desacoplada del motor de vision.

L2.5: el veredicto 'discrepancia' NO sanciona — solo enriquece la evidencia.
Ley 25.326: el screenshot se trata como dato sensible en todos los logs y comentarios.
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.infrastructure.crypto.evidence_encryption import EvidenceCipher
    from app.infrastructure.storage.worm import WormStoragePort
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.captura_almacenada import separar_data_url
from app.application.proctoring.integridad import (
    CUSTODIA_DISCREPANCIA,
    sha256_hex,
    verificar_custodia_cliente,
)
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.domain.auth.authorization import principal_es_dueno_de_sesion
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.retention.policy import RetentionPolicy
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.proctoring import ProctoringRepository

logger = logging.getLogger(__name__)


async def ingestar_evento(
    db: AsyncSession,
    session_id: str,
    tipo: str,
    severidad: str,
    ts_cliente: datetime,
    reinferencia: ReinferenciaPort,
    principal: AuthenticatedPrincipal,
    payload: dict | None = None,
    screenshot_base64: str | None = None,
    face_count_cliente: int | None = None,
    cipher: "EvidenceCipher | None" = None,
    worm_storage: "WormStoragePort | None" = None,
    screenshot_sha256_cliente: str | None = None,
) -> ProctoringEventModel:
    """Ingesta un evento de deteccion con re-inferencia e integridad SHA-256.

    Args:
        db: Sesion async de SQLAlchemy.
        session_id: UUID de la sesion de proctoring.
        tipo: Tipo de evento (ej. 'FACE_ABSENT', 'MULTIPLE_FACES').
        severidad: 'bajo' | 'medio' | 'alto' | 'critico'.
        ts_cliente: Timestamp reportado por el cliente (no confiable).
        reinferencia: Adapter del puerto ReinferenciaPort (inyectado por FastAPI Depends).
        payload: Datos adicionales del evento (libre). C-76 (15.3): `copiar_pegar`
            puede traer `payload['clipboard_sha256']` — el hash SHA-256 del
            contenido pegado, calculado en el cliente (Web Crypto). Como `payload`
            es JSONB libre (sin schema por tipo de evento), no requiere cambios
            aca ni migracion: se persiste tal cual llega. El backend NUNCA recibe
            ni persiste el contenido en claro (Ley 25.326) — solo el hash.
        screenshot_base64: Screenshot en base64 (dato sensible, Ley 25.326).
        face_count_cliente: Conteo de rostros reportado por el cliente.
        worm_storage: Puerto WORM (c-77), inyectado desde main_activeexam.py SOLO
            si MinIO esta configurado (minio_configurado(settings) True). Si es
            None (Render hoy, sin VPS) el comportamiento es IDENTICO al actual:
            el screenshot se persiste UNICAMENTE en Postgres, como siempre.
        principal: titular autenticado del request (H1, IDOR). Solo el dueño de
            la sesion puede ingestar eventos en ella. Antes cualquier alumno
            autenticado podia postear eventos (falsos) en la sesion de OTRO
            alumno con solo conocer su ``session_id``.

    Returns:
        ProctoringEventModel persistido con veredicto y sha256.

    Raises:
        HTTPException 404: si la sesion no existe.
        HTTPException 403: si la sesion no pertenece al principal.
    """
    repo = ProctoringRepository(db)

    # 1. Verificar existencia de la sesion
    sesion = await db.get(ProctoringSessionModel, session_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail=f"Sesion {session_id!r} no encontrada")

    if not principal_es_dueno_de_sesion(
        principal, sesion.alumno_idnumber, sesion.alumno_email
    ):
        raise HTTPException(status_code=403, detail="La sesion pertenece a otro alumno.")

    # 2. Integridad liviana (D9): SHA-256 del screenshot base64 EN CLARO (el hash
    # identifica el contenido original; se calcula antes de cifrar).
    screenshot_sha256 = sha256_hex(screenshot_base64)

    # 2b. Primera capa de la cadena de custodia (regla dura #6): re-hashear lo que
    # mandó el cliente y contrastarlo con lo que el cliente AFIRMA. Hasta c-78 el
    # campo se aceptaba en el schema y se descartaba, así que esta comparación no
    # existía. L2.5: una discrepancia NO rechaza el evento — se asienta como señal
    # para el revisor humano (regla dura #5).
    custodia_cliente = verificar_custodia_cliente(
        screenshot_base64, screenshot_sha256_cliente
    )
    if custodia_cliente == CUSTODIA_DISCREPANCIA:
        # Dato sensible (Ley 25.326): se loguean los HASHES, nunca la imagen.
        logger.warning(
            "custodia: el hash del cliente no corresponde a la imagen recibida "
            "(session_id=%s, tipo=%s, cliente=%s). El evento se persiste igual; "
            "queda como señal para el revisor humano.",
            session_id,
            tipo,
            screenshot_sha256_cliente,
        )

    # 3. Re-inferencia server-side (D8): NO importamos mediapipe aqui — usamos el puerto.
    # Corre sobre el plaintext en memoria (nunca se persiste en claro si hay cipher).
    resultado = reinferencia.evaluar(screenshot_base64, face_count_cliente)

    # 4. Cifrado at-rest de la evidencia sensible (Ley 25.326, regla #7).
    #
    # c-78 (16.4): se guarda en BINARIO, no como base64. Medido con pg_column_size,
    # la misma captura pasa de 151.224 a 85.065 bytes (44% menos) — era doble
    # expansion base64 (el data URL, y encima el token Fernet que tambien es base64).
    # `screenshot_b64` queda SOLO para leer el historico; las filas nuevas no la usan.
    #
    # Ningun hash cambia: el prefijo se guarda tal cual, asi que el string se
    # reconstruye byte a byte y `screenshot_sha256` sigue verificando.
    screenshot_prefijo, screenshot_binario = separar_data_url(screenshot_base64)
    if cipher is not None and screenshot_binario is not None:
        screenshot_binario = cipher.encrypt_bytes(screenshot_binario)

    # 5. Deposito WORM ADICIONAL (c-77): NUNCA reemplaza Postgres, que sigue siendo
    # la fuente de verdad/red de seguridad. Con worm_storage=None (Render hoy, sin
    # VPS) NO se genera id explicito: el id lo sigue asignando el server_default
    # (gen_random_uuid()), exactamente como antes de este change — cero cambio de
    # comportamiento. Solo cuando hay worm_storage se genera el id ANTES del
    # insert, porque el object_key lo necesita derivado del id del evento.
    evento_id: str | None = None
    worm_object_key: str | None = None
    worm_uri: str | None = None
    worm_retain_until: datetime | None = None
    if worm_storage is not None and screenshot_base64 is not None:
        evento_id = str(uuid.uuid4())
        try:
            # Misma politica de retencion que ya existe en el repo para evidencia
            # (app.domain.retention.policy.RetentionPolicy.default(), 180 dias).
            retain_until_dt = datetime.now(timezone.utc) + timedelta(
                days=RetentionPolicy.default().session_max_age_days
            )
            objeto = worm_storage.deposit(
                object_key=f"{session_id}/{evento_id}.bin",
                data=base64.b64decode(screenshot_base64),
                retain_until=retain_until_dt.isoformat(),
            )
            worm_object_key = objeto.object_key
            worm_uri = objeto.uri
            worm_retain_until = retain_until_dt
        except Exception:  # noqa: BLE001 - MinIO no confiable aun: nunca tumba la ingesta
            logger.exception(
                "worm_storage: fallo el deposito de evidencia (session_id=%s, "
                "evento_id=%s); evidencia queda solo en Postgres",
                session_id,
                evento_id,
            )

    # 6. Persistir evento con todos los campos
    return await repo.crear_evento(
        id=evento_id,
        session_id=session_id,
        tipo=tipo,
        severidad=severidad,
        ts_cliente=ts_cliente,
        payload=payload,
        screenshot_bin=screenshot_binario,
        screenshot_prefijo=screenshot_prefijo,
        screenshot_sha256=screenshot_sha256,
        screenshot_sha256_cliente=screenshot_sha256_cliente,
        custodia_cliente=custodia_cliente,
        face_count_cliente=face_count_cliente,
        face_count_servidor=resultado.face_count_servidor,
        veredicto_reinferencia=resultado.veredicto,
        worm_object_key=worm_object_key,
        worm_uri=worm_uri,
        worm_retain_until=worm_retain_until,
    )
