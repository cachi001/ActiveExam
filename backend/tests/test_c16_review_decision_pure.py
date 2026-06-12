"""Tests puros del servicio de decision del revisor (c-16 slim).

Verifica RN-RV-07 (inmutabilidad de la decision terminal) y la regla L2.5
(NUNCA sancion automatica — solo registro del juicio humano).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.review.decision import DecisionTerminal, ReviewDecisionRecord


@dataclass
class FakeRepo:
    records: dict[str, ReviewDecisionRecord] = field(default_factory=dict)
    persisted: list[tuple[str, str, str, str | None]] = field(default_factory=list)
    fake_at: str = "2026-06-11T12:00:00+00:00"

    async def get_decision(self, session_id: str):
        return self.records.get(session_id)

    async def persist_decision(
        self,
        session_id: str,
        *,
        decision: DecisionTerminal,
        actor: str,
        observaciones: str | None,
    ) -> str:
        self.persisted.append((session_id, decision.value, actor, observaciones))
        self.records[session_id] = ReviewDecisionRecord(
            session_id=session_id,
            decision=decision,
            actor=actor,
            decision_at=self.fake_at,
            observaciones=observaciones,
        )
        return self.fake_at


@dataclass
class FakeAuditor:
    calls: list[tuple[str, str, str, str]] = field(default_factory=list)

    async def log_decision(
        self, session_id: str, *, actor: str, decision: str, proposito: str
    ) -> None:
        self.calls.append((session_id, actor, decision, proposito))


def _make_service(records: dict | None = None):
    repo = FakeRepo(
        records={
            "s1": ReviewDecisionRecord(
                session_id="s1",
                decision=DecisionTerminal.PENDIENTE,
                actor=None,
                decision_at=None,
                observaciones=None,
            ),
            **(records or {}),
        }
    )
    auditor = FakeAuditor()
    return ReviewDecisionService(repo=repo, auditor=auditor), repo, auditor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_decision_terminal_enum_tiene_4_estados_y_pendiente_no_es_terminal() -> None:
    from app.domain.review.decision import es_terminal

    assert DecisionTerminal.PENDIENTE.value == "pendiente"
    assert DecisionTerminal.DESCARTADA.value == "descartada"
    assert DecisionTerminal.ESCALADA.value == "escalada"
    assert DecisionTerminal.DERIVADA.value == "derivada"
    assert not es_terminal(DecisionTerminal.PENDIENTE)
    assert es_terminal(DecisionTerminal.DESCARTADA)
    assert es_terminal(DecisionTerminal.ESCALADA)
    assert es_terminal(DecisionTerminal.DERIVADA)


@pytest.mark.asyncio
async def test_decide_persiste_y_audita_la_primera_decision() -> None:
    service, repo, auditor = _make_service()
    result = await service.decide(
        "s1",
        decision=DecisionTerminal.DESCARTADA,
        actor="revisor-1",
        observaciones="sin evidencia relevante",
    )
    assert result.previous == DecisionTerminal.PENDIENTE
    assert result.new == DecisionTerminal.DESCARTADA
    assert result.actor == "revisor-1"
    assert repo.persisted == [("s1", "descartada", "revisor-1", "sin evidencia relevante")]
    assert auditor.calls == [
        (
            "s1",
            "revisor-1",
            "descartada",
            "review.decide: registro inmutable de decision terminal (RN-RV-07, L2.5)",
        )
    ]


@pytest.mark.asyncio
async def test_decide_rechaza_pendiente_porque_no_es_terminal() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no es terminal"):
        await service.decide(
            "s1",
            decision=DecisionTerminal.PENDIENTE,
            actor="r",
            observaciones=None,
        )


@pytest.mark.asyncio
async def test_decide_sesion_inexistente_lanza_error() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no encontrada"):
        await service.decide(
            "no-existe",
            decision=DecisionTerminal.DESCARTADA,
            actor="r",
            observaciones=None,
        )


@pytest.mark.asyncio
async def test_decide_inmutable_lanza_error_y_audita_intento() -> None:
    """RN-RV-07: una vez decidida, NO se puede cambiar. El intento queda auditado."""
    service, repo, auditor = _make_service(
        records={
            "s2": ReviewDecisionRecord(
                session_id="s2",
                decision=DecisionTerminal.DERIVADA,
                actor="revisor-original",
                decision_at="2026-06-10T10:00:00+00:00",
                observaciones=None,
            )
        }
    )
    with pytest.raises(DecisionAlreadyMadeError) as exc:
        await service.decide(
            "s2",
            decision=DecisionTerminal.DESCARTADA,
            actor="revisor-malicioso",
            observaciones="trato de cambiarla",
        )
    assert exc.value.current == DecisionTerminal.DERIVADA
    # No se persistio
    assert ("s2", "descartada", "revisor-malicioso", "trato de cambiarla") not in repo.persisted
    # Pero el intento quedo en el audit log con propopsito de rechazo
    assert auditor.calls == [
        (
            "s2",
            "revisor-malicioso",
            "derivada",  # decision actual, NO la intentada
            "review.decide: intento de cambiar decision terminal — RECHAZADO",
        )
    ]
