"""Servicio de decision de sesion, UN SOLO PASO (colapsa c-16 + c-71 slice 2).

Regla dura RN-RV-07: la decision es INMUTABLE — una vez seteada (`aprobado` o
`anulado`), no se puede cambiar. Cualquier intento devuelve error con la
decision actual.

Barandas de la anulacion (D11, preservadas del modelo de dos fases aunque ya
no haya una fase de resolucion separada):
  (a) acto explicito del revisor, en el mismo `decide` (ya no hay una llamada
      aparte de "resolver": el owner del proyecto lo rechazo explicitamente);
  (b) motivo obligatorio no vacio + evidencia estructurada (lista de
      `event_id`) obligatoria cuando `decision == ANULADO`;
  (c) el efecto (nota anulada) se PROYECTA al alumno, filtrado a la evidencia
      elegida (`informe_service.build_informe_devolucion`);
  (d) reversibilidad por acto compensatorio append-only (`revertir_anulacion`,
      antes en `resolution_service.py`, fusionado aca).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.review.decision import (
    DecisionSesion,
    ReviewDecisionResult,
    es_terminal,
    valida_la_nota,
)
from app.domain.review.ports import ReviewAuditor, SessionReviewRepository


class DecisionAlreadyMadeError(Exception):
    """Se intento cambiar una decision ya tomada (RN-RV-07: inmutable)."""

    def __init__(self, session_id: str, current: DecisionSesion) -> None:
        super().__init__(
            f"Sesion {session_id!r} ya tiene decision {current.value!r}: "
            "es inmutable (RN-RV-07)."
        )
        self.session_id = session_id
        self.current = current


class MotivoRequeridoError(ValueError):
    """Motivo obligatorio no vacio cuando la decision es `anulado` (D11, baranda b)."""


class EvidenciaRequeridaError(ValueError):
    """`anulado` exige al menos un `event_id` de evidencia (D11, baranda b)."""


# Castellano llano: el registro de auditoria lo lee una persona (y eventualmente un
# organismo de control), no el equipo que escribio el endpoint.
_PURPOSE = "Revisó la sesión y registró su decisión"


@dataclass
class ReviewDecisionService:
    repo: SessionReviewRepository
    auditor: ReviewAuditor

    async def decide(
        self,
        session_id: str,
        *,
        decision: DecisionSesion,
        actor: str,
        motivo: str | None,
        evidencia_ids: list[str] | None = None,
    ) -> ReviewDecisionResult:
        """Persiste la decision si la sesion no tiene una terminal previa.

        `anulado` exige motivo no vacio y al menos un `event_id` de evidencia
        (D11, baranda b): sin esto no queda registrado NI por qué NI con qué
        se anuló una nota, y el dominio es CRÍTICO (RN-SC-01/DD-01).
        """
        if not es_terminal(decision):
            raise ValueError(
                f"Decision {decision.value!r} no es terminal. "
                "Solo aprobado/anulado son terminales."
            )

        evidencia = list(evidencia_ids or [])
        if decision is DecisionSesion.ANULADO:
            if motivo is None or not motivo.strip():
                raise MotivoRequeridoError(
                    "El motivo es obligatorio y no puede estar vacio para anular (D11, RN-RV-06)."
                )
            if not evidencia:
                raise EvidenciaRequeridaError(
                    "anulado exige al menos un event_id de evidencia (D11, baranda b)."
                )

        record = await self.repo.get_decision(session_id)
        if record is None:
            raise ValueError(f"Sesion {session_id!r} no encontrada")

        if es_terminal(record.decision):
            # Auditamos el intento aunque rechazado (RN-RV-07 trazabilidad)
            await self.auditor.log_decision(
                session_id,
                actor=actor,
                decision=record.decision.value,
                proposito=(
                    "Intentó cambiar una decisión ya registrada — RECHAZADO "
                    "(las decisiones no se pueden modificar)"
                ),
            )
            raise DecisionAlreadyMadeError(session_id, record.decision)

        decision_at = await self.repo.persist_decision(
            session_id,
            decision=decision,
            actor=actor,
            motivo=motivo.strip() if motivo else None,
            evidencia_ids=evidencia,
        )
        proposito = _PURPOSE
        if motivo and motivo.strip():
            proposito += f" | motivo: {motivo.strip()}"
        if evidencia:
            proposito += f" | evidencia: {', '.join(evidencia)}"
        await self.auditor.log_decision(
            session_id,
            actor=actor,
            decision=decision.value,
            proposito=proposito,
        )

        return ReviewDecisionResult(
            session_id=session_id,
            previous=record.decision,
            new=decision,
            actor=actor,
            decision_at=decision_at,
            nota_anulada=not valida_la_nota(decision),
        )

    async def revertir_anulacion(
        self, session_id: str, *, actor: str, motivo: str
    ) -> None:
        """Acto compensatorio APPEND-ONLY que restituye una nota anulada (D10b).

        NUNCA muta el acto de anulacion original ni la columna `decision`
        (eso rompe la cadena de custodia, RN-RV-06): registra una NUEVA entrada
        `nota_restituida` en el audit log. El estado efectivo de la nota se
        deriva del ultimo acto (``nota_esta_anulada``). Via del flujo de
        apelacion (c-18 hook).
        """
        if motivo is None or not motivo.strip():
            raise MotivoRequeridoError(
                "El motivo de la restitucion es obligatorio (RN-RV-06)."
            )
        record = await self.repo.get_decision(session_id)
        if record is None:
            raise ValueError(f"Sesion {session_id!r} no encontrada")
        if record.decision is not DecisionSesion.ANULADO:
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
