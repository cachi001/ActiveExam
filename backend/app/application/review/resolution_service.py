"""Servicio de RESOLUCION (fase 2) de la cola de revision — c-71 slice 2.

Acto separado del `decide` de revision (D9, baranda a). Aplica las cuatro
barandas de la anulacion (D11):

- (a) acto explicito y distinto del flaggeo/revision (este servicio + su
  endpoint `POST .../resolve`, gateado por `resolver_caso`),
- (b) motivo obligatorio no vacio + evidencia adjunta en `anulado_por_fraude`,
  registrados en el audit log inmutable existente,
- (c) el efecto (nota anulada) se PROYECTA al alumno (D11b, fuera de aqui),
- (d) reversibilidad por acto compensatorio append-only (resolution_reversal).

Precondicion: la revision (fase 1) debe estar en `caso_abierto` (409 si no).
La resolucion es INMUTABLE una vez seteada (RN-RV-07): un segundo intento
falla. El sistema NUNCA anula automaticamente (regla dura #5): la unica via es
esta llamada, disparada por un acto humano con la capacidad `resolver_caso`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.review.decision import (
    DecisionResolucion,
    ResolutionResult,
    es_caso_abierto,
    resolucion_valida_la_nota,
)
from app.domain.review.ports import ReviewAuditor, SessionReviewRepository


class CasoNoAbiertoError(Exception):
    """Se intento resolver una sesion cuya revision no quedo en `caso_abierto`."""

    def __init__(self, session_id: str, decision: str) -> None:
        super().__init__(
            f"Sesion {session_id!r} no esta en caso_abierto (fase 1 = {decision!r}): "
            "solo un caso abierto es resoluble (D9)."
        )
        self.session_id = session_id
        self.decision = decision


class ResolucionAlreadyMadeError(Exception):
    """La resolucion ya fue emitida — es inmutable (RN-RV-07)."""

    def __init__(self, session_id: str, current: DecisionResolucion) -> None:
        super().__init__(
            f"Sesion {session_id!r} ya tiene resolucion {current.value!r}: "
            "es inmutable (RN-RV-07). Revertir es un acto compensatorio aparte."
        )
        self.session_id = session_id
        self.current = current


class MotivoRequeridoError(ValueError):
    """Motivo obligatorio no vacio en TODA resolucion (D11, baranda b)."""


class EvidenciaRequeridaError(ValueError):
    """`anulado_por_fraude` exige evidencia adjunta (D11, baranda b)."""


# Castellano llano: el registro de auditoria lo lee una persona (y eventualmente un
# organismo de control), no el equipo que escribio el endpoint. Antes era
# "review.resolve: veredicto humano de resolucion (RN-RV-06/07, L2.5) — acto
# distinto del de revisar".
_PURPOSE = "Resolvió el caso y emitió el veredicto sobre el examen"


@dataclass
class ReviewResolutionService:
    repo: SessionReviewRepository
    auditor: ReviewAuditor

    async def resolve(
        self,
        session_id: str,
        *,
        resolucion: DecisionResolucion,
        actor: str,
        motivo: str,
        evidencia_ref: str | None,
    ) -> ResolutionResult:
        """Emite el veredicto sobre un caso abierto. Ver barandas en el modulo."""
        if motivo is None or not motivo.strip():
            raise MotivoRequeridoError(
                "El motivo es obligatorio y no puede estar vacio (D11, RN-RV-06)."
            )
        if resolucion is DecisionResolucion.ANULADO_POR_FRAUDE and not (
            evidencia_ref and evidencia_ref.strip()
        ):
            raise EvidenciaRequeridaError(
                "anulado_por_fraude exige evidencia adjunta (D11, baranda b)."
            )

        record = await self.repo.get_resolution(session_id)
        if record is None:
            raise ValueError(f"Sesion {session_id!r} no encontrada")

        if record.resolucion is not None:
            # Auditamos el intento aunque rechazado (RN-RV-07 trazabilidad)
            await self.auditor.log_decision(
                session_id,
                actor=actor,
                decision=record.resolucion.value,
                proposito=(
                    "Intentó cambiar un veredicto ya emitido — RECHAZADO (los veredictos no se pueden modificar)"
                ),
            )
            raise ResolucionAlreadyMadeError(session_id, record.resolucion)

        if not es_caso_abierto(record.decision):
            raise CasoNoAbiertoError(session_id, record.decision.value)

        resolucion_at = await self.repo.persist_resolution(
            session_id,
            resolucion=resolucion,
            actor=actor,
            motivo=motivo.strip(),
        )
        # Baranda (b): el acto queda en el audit log inmutable con motivo y
        # referencia a la evidencia, distinguible del acto de revisar (RN-RV-06).
        proposito = f"{_PURPOSE} | motivo: {motivo.strip()}"
        if evidencia_ref and evidencia_ref.strip():
            proposito += f" | evidencia: {evidencia_ref.strip()}"
        await self.auditor.log_decision(
            session_id,
            actor=actor,
            decision=resolucion.value,
            proposito=proposito,
        )

        return ResolutionResult(
            session_id=session_id,
            resolucion=resolucion,
            actor=actor,
            resolucion_at=resolucion_at,
            nota_anulada=not resolucion_valida_la_nota(resolucion),
        )

    async def revertir_anulacion(
        self, session_id: str, *, actor: str, motivo: str
    ) -> None:
        """Acto compensatorio APPEND-ONLY que restituye una nota anulada (D10b).

        NUNCA muta el acto de anulacion original ni la columna `resolucion`
        (eso rompe la cadena de custodia, RN-RV-06): registra una NUEVA entrada
        `nota_restituida` en el audit log. El estado efectivo de la nota se
        deriva del ultimo acto (``nota_esta_anulada``). Esta es la pieza que el
        flujo de apelacion de c-18 dispara; slice 2 solo deja el hook.
        """
        if motivo is None or not motivo.strip():
            raise MotivoRequeridoError(
                "El motivo de la restitucion es obligatorio (RN-RV-06)."
            )
        record = await self.repo.get_resolution(session_id)
        if record is None:
            raise ValueError(f"Sesion {session_id!r} no encontrada")
        if record.resolucion is not DecisionResolucion.ANULADO_POR_FRAUDE:
            raise ValueError(
                f"Sesion {session_id!r}: la nota no esta anulada; nada que restituir."
            )
        await self.auditor.log_decision(
            session_id,
            actor=actor,
            decision="nota_restituida",
            proposito=(
                "Restituyó la nota de un examen que había sido anulado"
                f" | motivo: {motivo.strip()}"
            ),
        )
