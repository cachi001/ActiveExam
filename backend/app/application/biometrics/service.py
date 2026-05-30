"""Caso de uso VerifyIdentity (aplicacion, C-09).

Orquesta el pipeline de verificacion biometrica re-inferido SERVER-SIDE (el
cliente es sensor no confiable, RN-GLB-01):

1. Gate de consentimiento (C-08) + referencia presente (C-07) como PRECONDICIONES.
2. Re-inferencia server-side del clip (motor de vision abstraido, DD-17): produce
   el embedding y la evidencia de liveness desde el CLIP EXACTO.
3. Liveness hibrido como prerrequisito obligatorio (RN-BIO-05): sin liveness, no
   hay comparacion 1:1.
4. Comparacion 1:1 por distancia coseno contra la referencia cifrada (D5).
5. Si match -> emite la clave de sesion rotativa (HMAC, D6/RN-BIO-02), habilita el
   examen, persiste el embedding capturado CIFRADO at-rest (D5) y deja la custodia
   inicial del clip (RN-BIO-07).
6. Si no-match -> maquina de reintentos (max 2); al 3.º fallo emite EVENTO CRITICO
   y ESCALA a proctor por la cola, SIN abortar ni sancionar (RN-BIO-04, L2.5).

Depende de PUERTOS (Hexagonal): vision engine, lectura de referencia cifrada,
secreto maestro, gate de consentimiento, gate de referencia, repo de Embedding,
repo de Evento (append-only), repo de Sesion y la cola. NUNCA de adaptadores.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.consent.service import ConsentService
from app.application.exam_config.service import ExamConfigService
from app.domain.biometrics import custody
from app.domain.biometrics.liveness import liveness_exitoso
from app.domain.biometrics.matching import UMBRAL_COSENO_DEFECTO, comparar_identidad
from app.domain.biometrics.ports import (
    ReferenceEmbeddingPort,
    SecretProviderPort,
    VisionEnginePort,
)
from app.domain.biometrics.retries import EstadoVerificacion, VeredictoIntento
from app.domain.consent_flow.errors import ConsentNotResolvedError
from app.domain.entities.embedding import Embedding
from app.domain.entities.event import Evento
from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.repositories.ports import (
    EmbeddingRepository,
    EventRepository,
    SessionRepository,
)
from app.infrastructure.messaging.port import MessageQueuePort

# Tipo de evento critico de fallo de verificacion (consumido por el panel C-15).
TIPO_EVENTO_FALLO_BIO = "posible_cambio_identidad"
SEVERIDAD_CRITICA = "critica"
# Topic de la cola para escalar la verificacion fallida a un proctor humano.
TOPIC_ESCALACION_PROCTOR_BIO = "biometria.verificacion.proctor"
# Version del esquema del embedding cifrado persistido.
VERSION_EMBEDDING = "v1"


class ReferenciaFaltanteError(RuntimeError):
    """No hay referencia biometrica del estudiante: la 1:1 no puede operar (C-07)."""


class LivenessFallidoError(RuntimeError):
    """El liveness hibrido no fue exitoso: la comparacion 1:1 NO se ejecuta."""


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    """Resultado de un intento de verificacion (para la presentacion)."""

    veredicto: VeredictoIntento
    distancia: float | None
    reintentos_restantes: int
    clave_sesion_emitida: bool
    escalado_a_proctor: bool
    intentos_fallidos: int


class VerifyIdentityService:
    """Pipeline de verificacion biometrica re-inferido server-side (C-09)."""

    def __init__(
        self,
        *,
        vision: VisionEnginePort,
        referencias: ReferenceEmbeddingPort,
        secretos: SecretProviderPort,
        embeddings: EmbeddingRepository,
        eventos: EventRepository,
        sesiones: SessionRepository,
        consent: ConsentService,
        exam_config: ExamConfigService,
        queue: MessageQueuePort,
        umbral: float = UMBRAL_COSENO_DEFECTO,
    ) -> None:
        self._vision = vision
        self._referencias = referencias
        self._secretos = secretos
        self._embeddings = embeddings
        self._eventos = eventos
        self._sesiones = sesiones
        self._consent = consent
        self._exam_config = exam_config
        self._queue = queue
        self._umbral = umbral

    async def verify(
        self,
        *,
        sesion: Sesion,
        estado: EstadoVerificacion,
        clip_uri: str,
        clip_hash: str,
        timestamp: str,
    ) -> tuple[EstadoVerificacion, VerificationOutcome]:
        """Procesa UN intento de verificacion. Devuelve (nuevo_estado, outcome).

        Precondiciones (levantan error si no se cumplen):
        - gate de consentimiento (C-08) resuelto (consentido) -> si no, 403.
        - referencia presente (C-07) -> si no, ``ReferenciaFaltanteError``.

        El veredicto sale de la maquina de reintentos sobre el resultado RE-INFERIDO
        server-side; el veredicto del cliente nunca decide (RN-GLB-01)."""
        user_id, exam_id = sesion.user_id, sesion.exam_id

        # --- Precondiciones (gates de C-08 y C-07) ---------------------------
        if not await self._consent.biometria_habilitada(user_id=user_id, exam_id=exam_id):
            raise ConsentNotResolvedError(
                "biometria no habilitada: falta consentimiento valido (C-08)"
            )
        if await self._exam_config.reference_missing(exam_id, user_id):
            raise ReferenciaFaltanteError(
                "sin referencia biometrica: derivar a via alternativa (C-07/C-08)"
            )

        # --- Re-inferencia SERVER-SIDE del clip (RN-GLB-01, D2) --------------
        reinferencia = await self._vision.reinferir(clip_uri=clip_uri, clip_hash=clip_hash)

        # --- Liveness obligatorio (RN-BIO-05): sin liveness, no hay 1:1 ------
        if not liveness_exitoso(reinferencia.liveness):
            return await self._registrar_fallo(
                sesion=sesion,
                estado=estado,
                distancia=None,
                timestamp=timestamp,
                motivo="liveness_fallido",
            )

        # --- Comparacion 1:1 contra la referencia cifrada (D5) --------------
        referencia = await self._referencias.leer_referencia(
            user_id=user_id, exam_id=exam_id
        )
        if referencia is None:
            raise ReferenciaFaltanteError("referencia ilegible o ausente")
        comparacion = comparar_identidad(
            reinferencia.embedding, referencia, umbral=self._umbral
        )

        if comparacion.es_match:
            return await self._registrar_exito(
                sesion=sesion,
                estado=estado,
                embedding=reinferencia.embedding,
                distancia=comparacion.distancia,
            )
        return await self._registrar_fallo(
            sesion=sesion,
            estado=estado,
            distancia=comparacion.distancia,
            timestamp=timestamp,
            motivo="no_match",
        )

    # --- Exito: emite clave de sesion rotativa + persiste embedding cifrado --

    async def _registrar_exito(
        self,
        *,
        sesion: Sesion,
        estado: EstadoVerificacion,
        embedding: tuple[float, ...],
        distancia: float,
    ) -> tuple[EstadoVerificacion, VerificationOutcome]:
        nuevo_estado, veredicto = estado.registrar_intento(exito=True)

        # Deriva y emite la clave de sesion rotativa (HMAC) SOLO al verificar (D6).
        secreto = await self._secretos.secreto_maestro()
        session_id = sesion.id or f"{sesion.user_id}:{sesion.exam_id}"
        clave_rotativa = custody.derivar_clave_sesion(
            secreto_maestro=secreto, session_id=session_id, epoca=0
        )
        # Habilita el examen: fija la clave rotativa y transiciona la sesion a
        # ACTIVA (si arranco INICIADA). La maquina de estados del dominio valida la
        # transicion (``Sesion.transicionar``); si ya estaba ACTIVA, se conserva.
        con_clave = Sesion(
            id=sesion.id,
            user_id=sesion.user_id,
            exam_id=sesion.exam_id,
            clave_sesion=clave_rotativa,
            estado=sesion.estado,
            score=sesion.score,
            metadata={**sesion.metadata, "biometria": "verificada"},
        )
        habilitada = (
            con_clave.transicionar(EstadoSesion.ACTIVA)
            if sesion.estado == EstadoSesion.INICIADA
            else con_clave
        )
        await self._sesiones.update(habilitada)

        # Persiste el embedding capturado CIFRADO at-rest (D5). El cifrado real lo
        # hace el adaptador (KMS) en ``add``; el dominio entrega los bytes opacos.
        await self._embeddings.add(
            Embedding(
                user_id=sesion.user_id,
                vector_cifrado=_serializar_para_cifrado(embedding),
                version=VERSION_EMBEDDING,
                fecha="",
            )
        )
        return nuevo_estado, VerificationOutcome(
            veredicto=veredicto,
            distancia=distancia,
            reintentos_restantes=nuevo_estado.reintentos_restantes,
            clave_sesion_emitida=True,
            escalado_a_proctor=False,
            intentos_fallidos=nuevo_estado.intentos_fallidos,
        )

    # --- Fallo: reintento o escalacion al 3.º (evento critico + cola) -------

    async def _registrar_fallo(
        self,
        *,
        sesion: Sesion,
        estado: EstadoVerificacion,
        distancia: float | None,
        timestamp: str,
        motivo: str,
    ) -> tuple[EstadoVerificacion, VerificationOutcome]:
        nuevo_estado, veredicto = estado.registrar_intento(exito=False)
        escalado = veredicto == VeredictoIntento.ESCALAR_A_PROCTOR

        if escalado:
            # 3.º fallo: EVENTO CRITICO + ESCALACION a proctor. NUNCA abort/sancion.
            session_id = sesion.id or f"{sesion.user_id}:{sesion.exam_id}"
            await self._eventos.append(
                Evento(
                    session_id=session_id,
                    exam_id=sesion.exam_id,
                    tipo=TIPO_EVENTO_FALLO_BIO,
                    severidad=SEVERIDAD_CRITICA,
                    timestamp_cliente=timestamp,
                    timestamp_backend=timestamp,
                    payload={"motivo": motivo, "intentos_fallidos": nuevo_estado.intentos_fallidos},
                )
            )
            await self._queue.enqueue(
                TOPIC_ESCALACION_PROCTOR_BIO,
                {
                    "session_id": session_id,
                    "user_id": sesion.user_id,
                    "exam_id": sesion.exam_id,
                    "motivo": motivo,
                    "timestamp": timestamp,
                },
            )

        # Persiste el contador de reintentos en la metadata de la sesion para que
        # el siguiente request reconstruya el estado (sin transicionar la sesion:
        # sigue INICIADA hasta una verificacion exitosa; NUNCA se cierra/sanciona).
        await self._sesiones.update(
            Sesion(
                id=sesion.id,
                user_id=sesion.user_id,
                exam_id=sesion.exam_id,
                clave_sesion=sesion.clave_sesion,
                estado=sesion.estado,
                score=sesion.score,
                metadata={
                    **sesion.metadata,
                    "intentos_fallidos": str(nuevo_estado.intentos_fallidos),
                    "verificacion_cerrada": "true" if nuevo_estado.cerrado else "false",
                },
            )
        )

        return nuevo_estado, VerificationOutcome(
            veredicto=veredicto,
            distancia=distancia,
            reintentos_restantes=nuevo_estado.reintentos_restantes,
            clave_sesion_emitida=False,
            escalado_a_proctor=escalado,
            intentos_fallidos=nuevo_estado.intentos_fallidos,
        )


def _serializar_para_cifrado(embedding: tuple[float, ...]) -> bytes:
    """Serializa el embedding a bytes para que el adaptador KMS lo CIFRE en ``add``.

    El dominio NO cifra (no conoce claves): produce la representacion canonica que
    el adaptador de persistencia cifra at-rest. Formato: floats separados por '|'."""
    return "|".join(repr(x) for x in embedding).encode("utf-8")
