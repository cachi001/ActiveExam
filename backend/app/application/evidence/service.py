"""Servicio de cadena de custodia — etapa 2 backend + worker etapas 3/4 (C-12 + C-24).

CAMBIO C-24 (DD-24-01, DD-24-03): el binario de evidencia pasa de CLIP de video
(5-10 s) a SCREENSHOT (frame unico PNG/JPEG). El contrato de la cadena de custodia
NO cambia (4 etapas acumulativas, RN-CC-02). Lo que cambia:
  - ``NotificacionEvidencia`` incluye los campos opcionales ``trigger`` y ``severidad``
    para clasificar el screenshot en la cola de revision.
  - La re-inferencia (etapa 4) es ESTATICA sobre el frame (DD-24-03): el worker
    llama a ``ServerInferencePort.inferir`` con los bytes de la imagen y el dominio
    compara los labels con los reportados por el cliente (senal forense de tampering).

ETAPA 2 (sincrona, ``EvidenceCustodyService.recibir_notificacion``):
1. Valida la **firma HMAC del cliente** sobre el hash del screenshot con la clave de
   sesion rotativa (zero trust, RN-GLB-01); firma invalida -> RECHAZO.
2. Re-descarga/recibe el binario y re-hashea (2.a verificacion); divergencia ->
   evento critico "evidencia corrupta o manipulada" (RN-CC-03), persistido y
   propagado al canal de C-10 (NUNCA descarte silencioso).
3. Persiste la ``Evidencia`` (hashes + firma cliente) SOLO si firma y hash validan.
4. Deposita el binario en el bucket **WORM (Object Lock Compliance)** con retain-until.
5. Escribe el **audit log** append-only (deposito).
6. Encola la tarea de firma+re-inferencia en ``MessageQueuePort`` (cola ganadora C-03).

WORKER (asincrono, ``EvidenceSigningWorker.procesar``): etapa 3 (3.a verificacion +
firma maestra asimetrica de Vault) y etapa 4 (re-inferencia ESTATICA firmada sobre
el frame). Divergencia -> mismo evento critico. El SLO E2->E4 < 30 s se instrumenta
en Prometheus. NUNCA sanciona (L2.5): persiste, audita, propaga senal.

Depende SOLO de puertos. NUNCA sanciona (L2.5): persiste, audita, propaga senal.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.audit_chain import AuditEntry
from app.domain.entities.evidence import Evidencia
from app.domain.evidence import custody_chain as cc
from app.domain.evidence.custody_chain import (
    ManipulacionDetectada,
    MasterSignerPort,
    ServerInferencePort,
)
from app.domain.repositories.ports import (
    AuditLogRepository,
    EvidenceRepository,
    SessionRepository,
)
from app.domain.biometrics import custody
from app.infrastructure.messaging.backplane import EventBackplane
from app.infrastructure.messaging.port import MessageQueuePort
from app.infrastructure.storage.worm import WormStoragePort

# Topic de la cola para la etapa asincrona de firma + re-inferencia (C-03 detras del puerto).
TOPIC_FIRMA_EVIDENCIA = "evidence.sign"


class FirmaClienteInvalidaError(ValueError):
    """La firma HMAC del cliente sobre el hash del clip no valida: rechazo."""


@dataclass(frozen=True, slots=True)
class NotificacionEvidencia:
    """Notificacion de evidencia del cliente (metadata + hash + firma, sin binario).

    CAMBIO C-24: se anaden ``trigger`` y ``severidad`` para clasificar el screenshot
    en la cola de revision. Ambos son opcionales para retrocompatibilidad con el
    contrato de C-12 (screenshots y clips conviven transitoriamente si es necesario).
    """

    session_id: str
    exam_id: str
    object_key: str
    hash_cliente: str
    firma_cliente: str
    # C-24: tipo de disparador ("event" | "heartbeat"); None si proviene de C-12 original.
    trigger: str | None = None
    # C-24: severidad del evento que origino el screenshot ("alta" | "critica"); None para heartbeat.
    severidad: str | None = None


class EvidenceCustodyService:
    """Etapa 2: verificacion sincrona + deposito WORM + audit + encolado."""

    def __init__(
        self,
        *,
        evidencias: EvidenceRepository,
        sesiones: SessionRepository,
        audit: AuditLogRepository,
        worm: WormStoragePort,
        cola: MessageQueuePort,
        backplane: EventBackplane,
    ) -> None:
        self._evidencias = evidencias
        self._sesiones = sesiones
        self._audit = audit
        self._worm = worm
        self._cola = cola
        self._backplane = backplane

    async def recibir_notificacion(
        self,
        notif: NotificacionEvidencia,
        *,
        clip_bytes: bytes,
        retain_until: str,
        actor: str = "backend",
        ip: str = "",
        user_agent: str = "",
    ) -> Evidencia:
        """Procesa la etapa 2. Levanta ``FirmaClienteInvalidaError`` (firma) o emite
        el evento critico de manipulacion (hash divergente) y re-lanza."""
        clave = await self._clave_de_sesion(notif.session_id)

        # 1) Verifica la firma HMAC del cliente sobre el hash del clip (zero trust).
        ok = custody.verificar_firma(
            clave_sesion=clave,
            mensaje=notif.hash_cliente.encode("utf-8"),
            firma=notif.firma_cliente,
        )
        if not ok:
            raise FirmaClienteInvalidaError("firma HMAC del cliente invalida: rechazo")

        # Construye la Evidencia con la etapa 1 del cliente.
        # C-24: trigger y severidad se persisten en meta para la comparacion forense
        # de la etapa 4 (tarea 3.3): si el cliente reporto labels, el worker los
        # compara con la re-inferencia server-side estatica (DD-24-03).
        uri = self._worm_uri(notif.object_key)
        meta: dict[str, object] = {
            "exam_id": notif.exam_id,
            "object_key": notif.object_key,
        }
        if notif.trigger is not None:
            meta["trigger"] = notif.trigger
        if notif.severidad is not None:
            meta["severidad"] = notif.severidad
        ev = Evidencia(
            session_id=notif.session_id,
            uri_bucket=uri,
            hash_cliente=notif.hash_cliente,
            firma_cliente=notif.firma_cliente,
            meta=meta,
        )

        # 2) Re-hash (2.a verificacion). Divergencia -> evento critico, no silencio.
        try:
            ev = cc.aplicar_etapa2(ev, clip_bytes=clip_bytes)
        except ManipulacionDetectada as manip:
            await self._emitir_manipulacion(notif, manip, actor=actor, ip=ip, ua=user_agent)
            raise

        # 3) Persiste la Evidencia (firma + hash validados).
        ev = await self._evidencias.add(ev)

        # 4) Deposita el binario en el bucket WORM (Object Lock Compliance).
        self._worm.deposit(
            object_key=notif.object_key, data=clip_bytes, retain_until=retain_until
        )

        # 5) Audit log del deposito (append-only, hash encadenado por el motor).
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",  # lo completa el motor (server_default now())
                ip=ip,
                user_agent=user_agent,
                accion="deposito_evidencia",
                evidencia_id=ev.id,
                proposito="custodia de evidencia (etapa 2)",
            )
        )

        # 6) Encola la tarea de firma+re-inferencia (cola ganadora de C-03).
        await self._cola.enqueue(
            TOPIC_FIRMA_EVIDENCIA,
            {
                "evidencia_id": ev.id,
                "object_key": notif.object_key,
                "exam_id": notif.exam_id,
                "session_id": notif.session_id,
            },
        )
        return ev

    async def _clave_de_sesion(self, session_id: str) -> str:
        sesion = await self._sesiones.get(session_id)
        if sesion is None:
            raise ValueError(f"sesion inexistente: {session_id}")
        if not sesion.clave_sesion:
            raise ValueError("la sesion no tiene clave emitida (C-09 no verifico)")
        return sesion.clave_sesion

    def _worm_uri(self, object_key: str) -> str:
        return f"worm://{object_key}"

    async def _emitir_manipulacion(
        self,
        notif: NotificacionEvidencia,
        manip: ManipulacionDetectada,
        *,
        actor: str,
        ip: str,
        ua: str,
    ) -> None:
        """Persiste traza forense + propaga el evento critico al canal (RN-CC-03).

        NUNCA sanciona (L2.5): emite la senal critica que el panel/score ponderan."""
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",
                ip=ip,
                user_agent=ua,
                accion="manipulacion_detectada",
                evidencia_id=None,
                proposito=f"hash divergente en etapa '{manip.etapa}' (RN-CC-03)",
            )
        )
        canal = self._backplane.canal_de(exam_id=notif.exam_id)
        await self._backplane.publish(
            canal=canal,
            evento={
                "tipo": cc.TIPO_EVIDENCIA_MANIPULADA,
                "severidad": cc.SEVERIDAD_CRITICA,
                "session_id": notif.session_id,
                "exam_id": notif.exam_id,
                "etapa": manip.etapa,
                "payload": {"object_key": notif.object_key},
            },
        )


class EvidenceSigningWorker:
    """Worker asincrono: etapa 3 (firma maestra) + etapa 4 (re-inferencia firmada).

    CAMBIO C-24 (DD-24-03): la re-inferencia (etapa 4) es ahora ESTATICA sobre el
    frame (imagen PNG/JPEG). El worker re-descarga el screenshot del WORM, re-verifica
    el hash (3.a, etapa 3), firma con la clave maestra asimetrica (Vault), y luego
    ejecuta deteccion de rostros/objetos sobre la imagen (etapa 4, via
    ``ServerInferencePort.inferir``). El resultado se compara con los labels reportados
    por el cliente; una discrepancia es senal forense firmada (tarea 3.3).

    Tradeoff L2.5 aceptado (design.md c-24): sin contexto temporal, no hay re-
    verificacion de liveness; suficiente y proporcional para revision humana.

    Consume de la cola ganadora de C-03 (via ``MessageQueuePort``) detras del puerto;
    re-descarga el artefacto del WORM, re-verifica el hash (3.a), firma con la clave
    maestra asimetrica (Vault) y firma el output de la re-inferencia server-side.

    NUNCA sanciona automaticamente (L2.5): la discrepancia es senal, no veredicto."""

    def __init__(
        self,
        *,
        evidencias: EvidenceRepository,
        audit: AuditLogRepository,
        worm: WormStoragePort,
        signer: MasterSignerPort,
        inferencia: ServerInferencePort,
        backplane: EventBackplane,
    ) -> None:
        self._evidencias = evidencias
        self._audit = audit
        self._worm = worm
        self._signer = signer
        self._inferencia = inferencia
        self._backplane = backplane

    async def procesar(self, mensaje: dict[str, object]) -> Evidencia:
        """Procesa una tarea de firma. Levanta ``ManipulacionDetectada`` (re-emitida)
        si el clip re-descargado no coincide con ``hash_backend`` (RN-CC-03)."""
        evidencia_id = str(mensaje["evidencia_id"])
        object_key = str(mensaje["object_key"])
        ev = await self._evidencias.get(evidencia_id)
        if ev is None:
            raise ValueError(f"evidencia inexistente: {evidencia_id}")

        clip_bytes = self._worm.fetch(object_key=object_key)

        # Etapa 3: 3.a verificacion de hash + firma maestra asimetrica (Vault).
        try:
            ev = cc.aplicar_firma_maestra(ev, clip_bytes=clip_bytes, signer=self._signer)
        except ManipulacionDetectada as manip:
            await self._emitir_manipulacion_worker(ev, manip)
            raise

        # Etapa 4: re-inferencia server-side + firma del output.
        ev = cc.aplicar_reinferencia(
            ev, clip_bytes=clip_bytes, inferencia=self._inferencia, signer=self._signer
        )

        ev = await self._evidencias.update(ev)
        await self._audit.append(
            AuditEntry(
                actor="worker",
                timestamp="",
                ip="",
                user_agent="",
                accion="firma_maestra_y_reinferencia",
                evidencia_id=ev.id,
                proposito="firma maestra + re-inferencia (etapas 3/4)",
            )
        )
        return ev

    async def _emitir_manipulacion_worker(
        self, ev: Evidencia, manip: ManipulacionDetectada
    ) -> None:
        exam_id = ev.meta.get("exam_id", "")
        await self._audit.append(
            AuditEntry(
                actor="worker",
                timestamp="",
                ip="",
                user_agent="",
                accion="manipulacion_detectada",
                evidencia_id=ev.id,
                proposito=f"hash divergente en etapa '{manip.etapa}' (RN-CC-03)",
            )
        )
        canal = self._backplane.canal_de(exam_id=exam_id)
        await self._backplane.publish(
            canal=canal,
            evento={
                "tipo": cc.TIPO_EVIDENCIA_MANIPULADA,
                "severidad": cc.SEVERIDAD_CRITICA,
                "session_id": ev.session_id,
                "exam_id": exam_id,
                "etapa": manip.etapa,
                "payload": {"evidencia_id": ev.id},
            },
        )
