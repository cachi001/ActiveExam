"""Tests puros del servicio de decision del revisor (c-16, evolucionado
c-71 slice 2 D6/D7).

Verifica RN-RV-07 (inmutabilidad de la decision terminal de REVISION) y la
regla L2.5 (NUNCA sancion automatica — solo registro del juicio humano).

Modelo de dos fases (D6): la fase de revision emite `sin_hallazgos` |
`aprobado` | `caso_abierto`. `caso_abierto` es terminal de la revision (no
se puede volver a revisar) pero NO valida ni anula la nota todavia — eso lo
decide la fase de resolucion (`resolver_caso`, fuera de este servicio).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.review.decision import DecisionRevision, ReviewDecisionRecord


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
        decision: DecisionRevision,
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
                decision=DecisionRevision.PENDIENTE,
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


def test_decision_revision_tiene_4_estados_y_pendiente_no_es_terminal() -> None:
    from app.domain.review.decision import es_terminal

    assert DecisionRevision.PENDIENTE.value == "pendiente"
    assert DecisionRevision.SIN_HALLAZGOS.value == "sin_hallazgos"
    assert DecisionRevision.APROBADO.value == "aprobado"
    assert DecisionRevision.CASO_ABIERTO.value == "caso_abierto"
    assert not es_terminal(DecisionRevision.PENDIENTE)
    assert es_terminal(DecisionRevision.SIN_HALLAZGOS)
    assert es_terminal(DecisionRevision.APROBADO)
    assert es_terminal(DecisionRevision.CASO_ABIERTO)


def test_escalada_ya_no_existe_como_miembro_del_enum() -> None:
    """D6: `escalada` se dropea del modelo unificado (sin downstream)."""
    assert not hasattr(DecisionRevision, "ESCALADA")
    with pytest.raises(ValueError):
        DecisionRevision("escalada")


def test_mapeo_legado_descartada_derivada_escalada() -> None:
    """D6: valores viejos (c-16 slim) se traducen al modelo nuevo."""
    assert DecisionRevision.desde_valor_legado("pendiente") is DecisionRevision.PENDIENTE
    assert (
        DecisionRevision.desde_valor_legado("descartada")
        is DecisionRevision.SIN_HALLAZGOS
    )
    assert (
        DecisionRevision.desde_valor_legado("derivada") is DecisionRevision.CASO_ABIERTO
    )
    assert (
        DecisionRevision.desde_valor_legado("escalada") is DecisionRevision.CASO_ABIERTO
    )


def test_caso_abierto_no_valida_la_nota_sin_hallazgos_y_aprobado_si() -> None:
    from app.domain.review.decision import valida_la_nota

    assert valida_la_nota(DecisionRevision.SIN_HALLAZGOS) is True
    assert valida_la_nota(DecisionRevision.APROBADO) is True
    assert valida_la_nota(DecisionRevision.CASO_ABIERTO) is False


@pytest.mark.asyncio
async def test_decide_persiste_y_audita_la_primera_decision() -> None:
    service, repo, auditor = _make_service()
    result = await service.decide(
        "s1",
        decision=DecisionRevision.SIN_HALLAZGOS,
        actor="revisor-1",
        observaciones="sin evidencia relevante",
    )
    assert result.previous == DecisionRevision.PENDIENTE
    assert result.new == DecisionRevision.SIN_HALLAZGOS
    assert result.actor == "revisor-1"
    assert repo.persisted == [
        ("s1", "sin_hallazgos", "revisor-1", "sin evidencia relevante")
    ]
    assert auditor.calls == [
        (
            "s1",
            "revisor-1",
            "sin_hallazgos",
            "Revisó la sesión y registró su decisión",
        )
    ]


@pytest.mark.asyncio
async def test_decide_caso_abierto_persiste_como_derivacion_sin_validar_nota() -> None:
    service, repo, _ = _make_service()
    result = await service.decide(
        "s1",
        decision=DecisionRevision.CASO_ABIERTO,
        actor="revisor-2",
        observaciones="hay senales para resolver",
    )
    assert result.new == DecisionRevision.CASO_ABIERTO
    assert repo.persisted == [
        ("s1", "caso_abierto", "revisor-2", "hay senales para resolver")
    ]


@pytest.mark.asyncio
async def test_decide_rechaza_pendiente_porque_no_es_terminal() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no es terminal"):
        await service.decide(
            "s1",
            decision=DecisionRevision.PENDIENTE,
            actor="r",
            observaciones=None,
        )


@pytest.mark.asyncio
async def test_decide_sesion_inexistente_lanza_error() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no encontrada"):
        await service.decide(
            "no-existe",
            decision=DecisionRevision.SIN_HALLAZGOS,
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
                decision=DecisionRevision.CASO_ABIERTO,
                actor="revisor-original",
                decision_at="2026-06-10T10:00:00+00:00",
                observaciones=None,
            )
        }
    )
    with pytest.raises(DecisionAlreadyMadeError) as exc:
        await service.decide(
            "s2",
            decision=DecisionRevision.SIN_HALLAZGOS,
            actor="revisor-malicioso",
            observaciones="trato de cambiarla",
        )
    assert exc.value.current == DecisionRevision.CASO_ABIERTO
    # No se persistio
    assert ("s2", "sin_hallazgos", "revisor-malicioso", "trato de cambiarla") not in repo.persisted
    # Pero el intento quedo en el audit log con proposito de rechazo
    assert auditor.calls == [
        (
            "s2",
            "revisor-malicioso",
            "caso_abierto",  # decision actual, NO la intentada
            "Intentó cambiar una decisión ya registrada — RECHAZADO "
            "(las decisiones no se pueden modificar)",
        )
    ]
