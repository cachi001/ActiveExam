"""Purgado de CAPTURAS de proctoring vencidas (Ley 25.326 + DPIA del proyecto).

``proctoring_event.screenshot_b64`` guarda la captura (rostro + pantalla del
alumno) en base64 dentro de Postgres. Un examen de 100 alumnos escribe ~360 MB
y, sin esto, nunca se borraba nada: guardar esas imagenes para siempre es un
problema de cumplimiento, no solo de disco.

DISEÑO (lo mas importante de este modulo): se borra la IMAGEN, NUNCA el
registro de que existio ni su huella. ``screenshot_sha256``, ``worm_object_key``,
``worm_uri`` y el resto del evento se CONSERVAN — la cadena de custodia
sobrevive: sigue constando QUE se capturo y con QUE hash, y si el deposito WORM
esta configurado la imagen sigue ahi.

RESTRICCION CRITICA: hoy en produccion (Render) el deposito WORM esta apagado
(``worm_storage=None``, ver ``event_service.py``), asi que Postgres es la UNICA
copia de la imagen. Por eso esta funcion NUNCA se llama sola: no hay cron ni
scheduler colgado de esto — la dispara explicitamente el endpoint admin
(``POST /api/v1/admin/retention/capturas``). Una vez purgada, la imagen NO se
puede recuperar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.retention.policy import validar_retencion_capturas_dias
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)


async def purgar_capturas_vencidas(session: AsyncSession, dias: int) -> int:
    """Pone en NULL la captura de los eventos cuya SESION es mas vieja que
    ``dias``. Devuelve cuantas capturas purgo.

    Purga las DOS columnas (c-78): ``screenshot_bin`` (binaria, las filas nuevas)
    y ``screenshot_b64`` (base64 legacy, el historico). Borrar solo una habria
    dejado de purgar de verdad justo cuando la captura pesa mas — que es el
    problema de cumplimiento que esta funcion existe para resolver (Ley 25.326).
    El prefijo se limpia tambien: sin binario no describe nada.

    Idempotente: solo toca eventos que todavia tienen captura, asi que correrla
    dos veces seguidas la segunda vez purga 0 (no rompe ni cuenta de mas). No hace
    commit — el caller controla la transaccion (mismo patron que el resto de los
    repos/servicios del proyecto).
    """
    # Defensivo: aunque la config ya valida el piso al editarse, una fila
    # pre-existente (anterior a la migracion) o escrita por fuera del endpoint
    # no deberia poder disparar un purgado por debajo del minimo legal.
    validar_retencion_capturas_dias(dias)

    corte = datetime.now(timezone.utc) - timedelta(days=dias)

    sesiones_vencidas = select(ProctoringSessionModel.id).where(
        ProctoringSessionModel.creada_en < corte
    )
    resultado = await session.execute(
        update(ProctoringEventModel)
        .where(ProctoringEventModel.session_id.in_(sesiones_vencidas))
        .where(
            or_(
                ProctoringEventModel.screenshot_b64.is_not(None),
                ProctoringEventModel.screenshot_bin.is_not(None),
            )
        )
        .values(screenshot_b64=None, screenshot_bin=None, screenshot_prefijo=None)
    )
    return resultado.rowcount or 0
