"""Purgado de CAPTURAS de proctoring vencidas (DPIA del proyecto).

``proctoring_event.screenshot_b64`` guarda la captura (una foto del rostro del
alumno tomada por la camara; la pantalla NO se captura) en base64 dentro de
Postgres. Un examen de 100 alumnos escribe ~360 MB y, sin esto, nunca se borraba
nada: guardar esas imagenes para siempre es un problema de cumplimiento, no solo
de disco.

DISEÑO (lo mas importante de este modulo): se borra la IMAGEN, NUNCA el
registro de que existio ni su huella. ``screenshot_sha256``, ``worm_object_key``,
``worm_uri`` y el resto del evento se CONSERVAN — la cadena de custodia
sobrevive: sigue constando QUE se capturo y con QUE hash, y si el deposito WORM
esta configurado la imagen sigue ahi. No se borra NI UNA FILA: es un UPDATE de
dos columnas, asi que ninguna FK ni referencia del sistema se ve afectada.

QUE SE SALVA DEL PLAZO: las sesiones ANULADAS y las que siguen EN COLA DE
REVISION conservan su imagen indefinidamente (ver
``_sesiones_con_evidencia_protegida``). Sin la foto, el verify-chain del informe
del alumno devuelve ``material_missing``: el hash sobrevive pero ya no hay nada
contra que compararlo. Perder eso justo en los casos con un veredicto en juego
vaciaria el expediente. El plazo aplica al resto, que es el grueso del peso.

RESTRICCION CRITICA: hoy en produccion (Render) el deposito WORM esta apagado
(``worm_storage=None``, ver ``event_service.py``), asi que Postgres es la UNICA
copia de la imagen: una vez purgada, NO se puede recuperar.

QUIEN LA DISPARA: desde el 28/8/2026 corre SOLA (``purga_programada.py``, tarea
de fondo colgada del arranque), porque el texto de consentimiento le declara al
alumno un plazo concreto y ese plazo tiene que cumplirse sin depender de que
alguien se acuerde. Sigue disponible el disparo manual por el endpoint admin
(``POST /api/v1/admin/retention/capturas``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.retention.policy import validar_retencion_capturas_dias
from app.domain.review.decision import DecisionSesion
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
    problema de cumplimiento que esta funcion existe para resolver. El prefijo se
    limpia tambien: sin binario no describe nada.

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

    vencidas = list(
        (
            await session.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.creada_en < corte
                )
            )
        )
        .scalars()
        .all()
    )
    protegidas = await _sesiones_con_evidencia_protegida(session, vencidas)
    purgables = [sid for sid in vencidas if sid not in protegidas]
    if not purgables:
        return 0

    resultado = await session.execute(
        update(ProctoringEventModel)
        .where(ProctoringEventModel.session_id.in_(purgables))
        .where(
            or_(
                ProctoringEventModel.screenshot_b64.is_not(None),
                ProctoringEventModel.screenshot_bin.is_not(None),
            )
        )
        .values(screenshot_b64=None, screenshot_bin=None, screenshot_prefijo=None)
    )
    return resultado.rowcount or 0


async def _sesiones_con_evidencia_protegida(
    session: AsyncSession, session_ids: list[str]
) -> set[str]:
    """Sesiones cuya captura NO se purga aunque haya vencido el plazo.

    Dos casos, decision del dueño (28/8/2026):

    - **Anulada** (``decision == 'anulado'``): la foto es en lo que se apoyo la
      anulacion. Sin ella el expediente del alumno queda con el verify-chain en
      ``material_missing`` — es decir, sin nada que peritar justo en el unico
      caso donde la evidencia importa de verdad.
    - **En cola de revision** (score >= umbral y sin decision todavia): el caso
      sigue abierto. Borrar la evidencia de algo no resuelto es cerrarlo por
      cansancio.

    El flag de riesgo se pide prestado a ``resultados_query`` (import diferido
    para no atar este modulo al de Moodle en tiempo de carga): duplicar acá la
    formula del score la dejaria desincronizada del umbral configurable y de los
    pesos vivos, que es exactamente el bug que ese modulo ya evita.
    """
    if not session_ids:
        return set()

    from app.application.moodle.resultados_query import _flaggeadas_por_sesion

    protegidas: set[str] = set(
        (
            await session.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.id.in_(session_ids),
                    ProctoringSessionModel.decision == DecisionSesion.ANULADO.value,
                )
            )
        )
        .scalars()
        .all()
    )

    sin_decision = (
        (
            await session.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.id.in_(session_ids),
                    or_(
                        ProctoringSessionModel.decision.is_(None),
                        ProctoringSessionModel.decision
                        == DecisionSesion.PENDIENTE.value,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    flaggeadas = await _flaggeadas_por_sesion(session, list(sin_decision))
    protegidas.update(sid for sid, en_riesgo in flaggeadas.items() if en_riesgo)
    return protegidas
