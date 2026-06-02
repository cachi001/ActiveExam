"""Servicio de ingestion de eventos de proctoring slim.

Orquesta:
  1. Verificar que la sesion existe (404 si no)
  2. Calcular sha256 del screenshot (integridad liviana, D9)
  3. Invocar la re-inferencia via ReinferenciaPort (NO importa mediapipe directamente)
  4. Persistir el evento con todos los campos

Depende del puerto ReinferenciaPort — el adapter concreto (MediaPipeReinferencia)
se inyecta desde main_slim.py via FastAPI Depends. Esto sigue DD-17 y mantiene
la capa de aplicacion desacoplada del motor de vision.

L2.5: el veredicto 'discrepancia' NO sanciona — solo enriquece la evidencia.
Ley 25.326: el screenshot se trata como dato sensible en todos los logs y comentarios.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.integridad import sha256_hex
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.proctoring import ProctoringRepository


async def ingestar_evento(
    db: AsyncSession,
    session_id: str,
    tipo: str,
    severidad: str,
    ts_cliente: datetime,
    reinferencia: ReinferenciaPort,
    payload: dict | None = None,
    screenshot_base64: str | None = None,
    face_count_cliente: int | None = None,
) -> ProctoringEventModel:
    """Ingesta un evento de deteccion con re-inferencia e integridad SHA-256.

    Args:
        db: Sesion async de SQLAlchemy.
        session_id: UUID de la sesion de proctoring.
        tipo: Tipo de evento (ej. 'FACE_ABSENT', 'MULTIPLE_FACES').
        severidad: 'bajo' | 'medio' | 'alto' | 'critico'.
        ts_cliente: Timestamp reportado por el cliente (no confiable).
        reinferencia: Adapter del puerto ReinferenciaPort (inyectado por FastAPI Depends).
        payload: Datos adicionales del evento (libre).
        screenshot_base64: Screenshot en base64 (dato sensible, Ley 25.326).
        face_count_cliente: Conteo de rostros reportado por el cliente.

    Returns:
        ProctoringEventModel persistido con veredicto y sha256.

    Raises:
        HTTPException 404: si la sesion no existe.
    """
    repo = ProctoringRepository(db)

    # 1. Verificar existencia de la sesion
    sesion = await db.get(ProctoringSessionModel, session_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail=f"Sesion {session_id!r} no encontrada")

    # 2. Integridad liviana (D9): SHA-256 del screenshot base64
    # PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)
    screenshot_sha256 = sha256_hex(screenshot_base64)

    # 3. Re-inferencia server-side (D8): NO importamos mediapipe aqui — usamos el puerto
    resultado = reinferencia.evaluar(screenshot_base64, face_count_cliente)

    # 4. Persistir evento con todos los campos
    return await repo.crear_evento(
        session_id=session_id,
        tipo=tipo,
        severidad=severidad,
        ts_cliente=ts_cliente,
        payload=payload,
        screenshot_b64=screenshot_base64,
        screenshot_sha256=screenshot_sha256,
        face_count_cliente=face_count_cliente,
        face_count_servidor=resultado.face_count_servidor,
        veredicto_reinferencia=resultado.veredicto,
    )
