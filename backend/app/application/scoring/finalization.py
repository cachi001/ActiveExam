"""Cierre de sesion + consolidacion asincrona del score final (C-13, Flujo 6, D5).

``SessionFinalizationService.finish`` (sincrono, lo invoca POST /sessions/{id}/finish):
marca la sesion FINALIZADA y ENCOLA la tarea de consolidacion en ``MessageQueuePort``
(no bloquea al estudiante, RN-SC-04). ``consolidar`` (la tarea asincrona del worker):
recomputa el SCORE FINAL desde los eventos persistidos (idempotente y recomputable),
libera la clave de sesion y decide el encolado por umbral (flaggeada/archivada).

El score PRIORIZA, NUNCA sanciona (L2.5, RN-SC-01): la unica salida es un estado de
sesion (flaggeada/archivada) + el score como prioridad ordinal; jamas un veredicto.
Depende SOLO de puertos (repos + cola). El umbral es configurable por examen (D6).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.repositories.ports import (
    EventRepository,
    ExamRepository,
    SessionRepository,
)
from app.domain.scoring.risk_score import (
    DecisionEncolado,
    EventoScore,
    PesosScore,
    decidir_encolado,
    score_correlacionado,
)
from app.infrastructure.messaging.port import MessageQueuePort

# Topic de la tarea asincrona de consolidacion del score al cierre.
TOPIC_CIERRE_SESION = "session.finalize"
# Umbral conservador por defecto si el examen no define el suyo (RN-SC-05, D6).
SCORE_THRESHOLD_DEFAULT = 5.0
# Clave de sesion liberada: cadena vacia -> la ingesta rechaza eventos firmados
# (SesionSinClaveError en application/events/ingestion.py).
CLAVE_LIBERADA = ""


@dataclass(frozen=True, slots=True)
class ResultadoCierre:
    """Resultado de la consolidacion al cierre (para metricas/telemetria)."""

    session_id: str
    score_final: float
    decision: DecisionEncolado
    clave_liberada: bool


class SessionFinalizationService:
    """Cierre de sesion (sincrono) + consolidacion del score (asincrono)."""

    def __init__(
        self,
        *,
        sesiones: SessionRepository,
        eventos: EventRepository,
        examenes: ExamRepository,
        cola: MessageQueuePort,
        pesos: PesosScore | None = None,
    ) -> None:
        self._sesiones = sesiones
        self._eventos = eventos
        self._examenes = examenes
        self._cola = cola
        self._pesos = pesos or PesosScore()

    async def finish(self, session_id: str) -> str:
        """Marca la sesion FINALIZADA y encola la consolidacion (no bloqueante, D5).

        Devuelve el id del mensaje encolado. El score final lo calcula la tarea
        asincrona; el estudiante no espera el calculo."""
        sesion = await self._get_sesion(session_id)
        if sesion.estado in (EstadoSesion.ACTIVA, EstadoSesion.INICIADA):
            sesion = sesion.transicionar(EstadoSesion.FINALIZADA)
            await self._sesiones.update(sesion)
        return await self._cola.enqueue(TOPIC_CIERRE_SESION, {"session_id": session_id})

    async def consolidar(self, session_id: str) -> ResultadoCierre:
        """Tarea asincrona: recomputa el score final (idempotente y recomputable
        desde la hypertable), libera la clave y decide el encolado por umbral.

        Idempotente: recomputa SIEMPRE desde los eventos persistidos (no acumula
        sobre un valor previo), de modo que reintentar produce el mismo resultado
        sin doble conteo (RN-SC-04)."""
        sesion = await self._get_sesion(session_id)
        eventos = await self._eventos.posteriores_a(
            session_id=session_id, last_event_id=None
        )
        score_final = score_correlacionado(
            [self._a_evento_score(e) for e in eventos], self._pesos
        )

        umbral = await self._umbral_de(sesion.exam_id)
        resultado = decidir_encolado(score_final, umbral=umbral)

        # Estado destino: flaggeada (a la cola C-16) o archivada (-> cerrada). NUNCA
        # una sancion (L2.5): solo un estado de prioridad/archivo.
        if resultado.decision is DecisionEncolado.FLAGGEADA:
            destino = EstadoSesion.FLAGGEADA
        else:
            destino = EstadoSesion.CERRADA  # archivada = ciclo cerrado sin cola

        # Libera la clave de sesion (ya no se firman mas eventos) y fija el score y
        # estado de forma idempotente (recomputado, no acumulado).
        sesion_final = self._sesion_consolidada(sesion, score_final, destino)
        await self._sesiones.update(sesion_final)

        if resultado.decision is DecisionEncolado.FLAGGEADA:
            # Encola la sesion priorizada para la cola de revision humana (C-16).
            await self._cola.enqueue(
                "review.queue",
                {"session_id": session_id, "score": score_final, "prioridad": score_final},
            )

        return ResultadoCierre(
            session_id=session_id,
            score_final=score_final,
            decision=resultado.decision,
            clave_liberada=True,
        )

    def _sesion_consolidada(
        self, sesion: Sesion, score_final: float, destino: EstadoSesion
    ) -> Sesion:
        """Devuelve la sesion con score, estado destino y clave liberada.

        Transiciona desde el estado actual respetando la maquina de estados (una
        sesion ya finalizada puede ir a flaggeada/cerrada). Idempotente: si ya esta
        en el destino, no re-transiciona."""
        con_estado = sesion
        if sesion.estado != destino:
            try:
                con_estado = sesion.transicionar(destino)
            except ValueError:
                # Ya consolidada en un estado terminal: no re-transiciona (idempotencia).
                con_estado = sesion
        return replace(con_estado, score=score_final, clave_sesion=CLAVE_LIBERADA)

    async def _umbral_de(self, exam_id: str) -> float:
        examen = await self._examenes.get(exam_id)
        if examen is None or examen.umbral_score is None:
            return SCORE_THRESHOLD_DEFAULT
        return float(examen.umbral_score)

    async def _get_sesion(self, session_id: str) -> Sesion:
        sesion = await self._sesiones.get(session_id)
        if sesion is None:
            raise ValueError(f"sesion inexistente: {session_id}")
        return sesion

    def _a_evento_score(self, ev) -> EventoScore:
        """Proyecta un Evento de dominio a la vista de score, derivando la
        persistencia de su payload (``sostenido_ms``/``frames_consecutivos`` de las
        reglas de C-11) cuando esta presente; default 1 (pico aislado)."""
        persistencia = 1
        payload = ev.payload or {}
        frames = payload.get("frames_consecutivos")
        if isinstance(frames, int) and frames > 0:
            persistencia = frames
        ts_ms = _ts_a_ms(ev.timestamp_backend)
        return EventoScore(
            tipo=ev.tipo, severidad=ev.severidad, ts_ms=ts_ms, persistencia=persistencia
        )


def _ts_a_ms(ts: str) -> int:
    """Convierte un timestamp ISO a ms epoch para la ventana de correlacion.

    Tolerante: si no parsea, devuelve 0 (la correlacion degrada a coincidencia en el
    mismo instante, conservador)."""
    from datetime import datetime

    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0
