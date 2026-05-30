"""Casos de uso del consentimiento informado (aplicacion, C-08).

- ``record_consent`` (D1+D2): valida accion afirmativa server-side, sella el hash
  del texto exacto y persiste el acuse INMUTABLE (``Consentimiento`` de C-05).
- ``choose_alternative`` (D3): registra la eleccion de via alternativa en el audit
  log (append-only, inmutable) y escala a un proctor por la cola; NUNCA aborta.
- ``evaluate_gate`` (D4): consumible por C-09 — habilita biometria solo con acuse
  valido o via alternativa elegida.

Depende de PUERTOS (``ConsentRepository`` sin update/delete, ``AuditLogRepository``
append-only, ``MessageQueuePort``) — no de adaptadores (Hexagonal). La inmutabilidad
del acuse la garantiza el puerto (sin ``update``) + el trigger de la base (C-05).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.audit_chain import AuditEntry
from app.domain.consent_flow import rules
from app.domain.consent_flow.rules import ResolucionConsentimiento
from app.domain.consent_flow.text_catalog import VERSION_VIGENTE, ConsentText
from app.domain.entities.consent import Consentimiento
from app.domain.repositories.ports import AuditLogRepository, ConsentRepository
from app.infrastructure.messaging.port import MessageQueuePort

# Accion del audit log que marca la eleccion de la via alternativa (gate D4).
ACCION_VIA_ALTERNATIVA = "consent_alternative_chosen"
# Topic de la cola para escalar la verificacion alternativa a un proctor.
TOPIC_ESCALACION_PROCTOR = "consent.alternative.proctor"


@dataclass(frozen=True, slots=True)
class ConsentTextView:
    """Vista del texto vigente para la pantalla (cinco bloques + version)."""

    version: str
    bloques: dict[str, str]
    hash_texto: str


class ConsentService:
    """Flujo de consentimiento informado (base legal del tratamiento biometrico)."""

    def __init__(
        self,
        consents: ConsentRepository,
        audit_log: AuditLogRepository,
        queue: MessageQueuePort,
    ) -> None:
        self._consents = consents
        self._audit = audit_log
        self._queue = queue

    # --- Presentacion del texto (RN-CO-01) -----------------------------------

    def get_text_view(self, version: str | None = None) -> ConsentTextView:
        """Devuelve el texto vigente (o el de ``version``) para la pantalla."""
        texto: ConsentText = rules.resolver_texto(version)
        return ConsentTextView(
            version=texto.version, bloques=texto.bloques(), hash_texto=texto.hash_texto()
        )

    # --- Registro del acuse (D1 + D2) ----------------------------------------

    async def record_consent(
        self,
        *,
        user_id: str,
        exam_id: str,
        version_texto: str | None,
        affirmative_action: bool,
        timestamp: str,
    ) -> Consentimiento:
        """Registra el acuse INMUTABLE si hubo accion afirmativa (RN-CO-02).

        Levanta ``MissingAffirmativeActionError`` (-> 422) si falta la accion, o
        ``UnknownConsentVersionError`` (-> 422) si la version no existe. NO persiste
        nada ante un acuse invalido."""
        rules.validar_accion_afirmativa(affirmative_action)
        texto = rules.resolver_texto(version_texto)
        sello = rules.hash_acuse(
            user_id=user_id,
            exam_id=exam_id,
            texto=texto,
            timestamp=timestamp,
            affirmative_action=affirmative_action,
        )
        acuse = Consentimiento(
            user_id=user_id,
            exam_id=exam_id,
            version_texto=texto.version,
            timestamp=timestamp,
            hash=sello,
        )
        # ConsentRepository NO expone update/delete -> inmutabilidad (C-05, D5).
        return await self._consents.add(acuse)

    # --- Via alternativa sin biometria (D3) ----------------------------------

    async def choose_alternative(
        self,
        *,
        user_id: str,
        exam_id: str,
        timestamp: str,
        ip: str = "",
        user_agent: str = "",
    ) -> str:
        """Registra la eleccion de via alternativa y ESCALA a proctor (RN-CO-05).

        No aborta el examen (RN-GLB-02): deja traza inmutable en el audit log y
        encola la escalacion. Devuelve el id del mensaje de escalacion."""
        await self._audit.append(
            AuditEntry(
                actor=user_id,
                timestamp=timestamp,
                ip=ip,
                user_agent=user_agent,
                accion=ACCION_VIA_ALTERNATIVA,
                evidencia_id=None,
                proposito=f"via_alternativa:{exam_id}",
            )
        )
        return await self._queue.enqueue(
            TOPIC_ESCALACION_PROCTOR,
            {"user_id": user_id, "exam_id": exam_id, "timestamp": timestamp},
        )

    # --- Gate de consentimiento (D4) -----------------------------------------

    async def resolve(self, *, user_id: str, exam_id: str) -> ResolucionConsentimiento:
        """Determina como resolvio el estudiante (consentido / alternativa / no)."""
        for acuse in await self._consents.list():
            if acuse.user_id == user_id and acuse.exam_id == exam_id:
                return ResolucionConsentimiento.CONSENTIDO
        marcador = f"via_alternativa:{exam_id}"
        for entrada in await self._audit.list():
            if (
                entrada.actor == user_id
                and entrada.accion == ACCION_VIA_ALTERNATIVA
                and entrada.proposito == marcador
            ):
                return ResolucionConsentimiento.VIA_ALTERNATIVA
        return ResolucionConsentimiento.NO_RESUELTO

    async def evaluate_gate(self, *, user_id: str, exam_id: str) -> bool:
        """Gate D4 consumible por C-09: ``True`` si puede avanzar.

        Levanta ``ConsentNotResolvedError`` (-> 403) si no hay consentimiento ni
        via alternativa."""
        resolucion = await self.resolve(user_id=user_id, exam_id=exam_id)
        return rules.evaluar_gate(resolucion)

    async def biometria_habilitada(self, *, user_id: str, exam_id: str) -> bool:
        """``True`` solo si se consintio la biometria (la via alternativa no la exige)."""
        resolucion = await self.resolve(user_id=user_id, exam_id=exam_id)
        return rules.biometria_habilitada(resolucion)
