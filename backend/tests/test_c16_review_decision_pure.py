"""Tests puros del servicio de decision del revisor — UN SOLO PASO (colapsa
c-16 + c-71 slice 2, decision explicita del owner del proyecto).

Verifica RN-RV-07 (inmutabilidad de la decision terminal), la regla L2.5
(NUNCA sancion automatica — solo registro del juicio humano) y las barandas
de la anulacion (D11): motivo obligatorio no vacio + evidencia ESTRUCTURADA
obligatoria (lista de `event_id`) cuando `decision=ANULADO`. NO existe una
segunda fase de "resolucion" ni el estado `caso_abierto`: el owner del
proyecto lo rechazo explicitamente ("no existe el caso abierto, nunca dije
que era un estado y no lo va a ser"; confirmado "si, un solo paso: quien
revisa decide", sin segunda instancia).

Tambien cubre `revertir_anulacion` (acto compensatorio append-only, D10b),
fusionado a este servicio desde el extinto `resolution_service.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.application.review.service import (
    DecisionAlreadyMadeError,
    EvidenciaRequeridaError,
    MotivoRequeridoError,
    ReviewDecisionService,
)
from app.domain.review.decision import DecisionSesion, ReviewDecisionRecord


@dataclass
class FakeRepo:
    records: dict[str, ReviewDecisionRecord] = field(default_factory=dict)
    persisted: list[tuple[str, str, str, str | None, tuple[str, ...]]] = field(
        default_factory=list
    )
    fake_at: str = "2026-08-03T12:00:00+00:00"

    async def get_decision(self, session_id: str):
        return self.records.get(session_id)

    async def persist_decision(
        self,
        session_id: str,
        *,
        decision: DecisionSesion,
        actor: str,
        motivo: str | None,
        evidencia_ids: list[str],
    ) -> str:
        self.persisted.append(
            (session_id, decision.value, actor, motivo, tuple(evidencia_ids))
        )
        self.records[session_id] = ReviewDecisionRecord(
            session_id=session_id,
            decision=decision,
            actor=actor,
            decision_at=self.fake_at,
            motivo=motivo,
            evidencia_ids=tuple(evidencia_ids),
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
                decision=DecisionSesion.PENDIENTE,
                actor=None,
                decision_at=None,
                motivo=None,
                evidencia_ids=(),
            ),
            **(records or {}),
        }
    )
    auditor = FakeAuditor()
    return ReviewDecisionService(repo=repo, auditor=auditor), repo, auditor


# ---------------------------------------------------------------------------
# El enum tiene 3 estados, sin caso_abierto
# ---------------------------------------------------------------------------


def test_decision_sesion_tiene_3_estados_y_pendiente_no_es_terminal() -> None:
    from app.domain.review.decision import es_terminal

    assert DecisionSesion.PENDIENTE.value == "pendiente"
    assert DecisionSesion.APROBADO.value == "aprobado"
    assert DecisionSesion.ANULADO.value == "anulado"
    assert not es_terminal(DecisionSesion.PENDIENTE)
    assert es_terminal(DecisionSesion.APROBADO)
    assert es_terminal(DecisionSesion.ANULADO)


def test_caso_abierto_ya_no_existe_como_miembro_del_enum() -> None:
    assert not hasattr(DecisionSesion, "CASO_ABIERTO")
    assert not hasattr(DecisionSesion, "SIN_HALLAZGOS")
    with pytest.raises(ValueError):
        DecisionSesion("caso_abierto")
    with pytest.raises(ValueError):
        DecisionSesion("sin_hallazgos")


def test_aprobado_valida_la_nota_anulado_no() -> None:
    from app.domain.review.decision import valida_la_nota

    assert valida_la_nota(DecisionSesion.APROBADO) is True
    assert valida_la_nota(DecisionSesion.ANULADO) is False


# ---------------------------------------------------------------------------
# decide(): happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_aprobado_persiste_y_audita_sin_exigir_evidencia() -> None:
    service, repo, auditor = _make_service()
    result = await service.decide(
        "s1",
        decision=DecisionSesion.APROBADO,
        actor="revisor-1",
        motivo="sin evidencia relevante",
    )
    assert result.previous == DecisionSesion.PENDIENTE
    assert result.new == DecisionSesion.APROBADO
    assert result.actor == "revisor-1"
    assert result.nota_anulada is False
    assert repo.persisted == [
        ("s1", "aprobado", "revisor-1", "sin evidencia relevante", ())
    ]
    assert len(auditor.calls) == 1
    assert auditor.calls[0][2] == "aprobado"


@pytest.mark.asyncio
async def test_decide_anulado_persiste_evidencia_estructurada_y_anula_la_nota() -> None:
    service, repo, auditor = _make_service()
    result = await service.decide(
        "s1",
        decision=DecisionSesion.ANULADO,
        actor="revisor-2",
        motivo="copia detectada en 3 clips",
        evidencia_ids=["evt-1", "evt-2"],
    )
    assert result.new == DecisionSesion.ANULADO
    assert result.nota_anulada is True
    assert repo.persisted == [
        (
            "s1",
            "anulado",
            "revisor-2",
            "copia detectada en 3 clips",
            ("evt-1", "evt-2"),
        )
    ]
    # El acto queda auditado con motivo Y evidencia (D11 baranda b).
    proposito = auditor.calls[0][3]
    assert "copia detectada en 3 clips" in proposito
    assert "evt-1" in proposito and "evt-2" in proposito


# ---------------------------------------------------------------------------
# Barandas de la anulacion (D11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anular_sin_motivo_es_rechazado() -> None:
    service, repo, _ = _make_service()
    with pytest.raises(MotivoRequeridoError):
        await service.decide(
            "s1",
            decision=DecisionSesion.ANULADO,
            actor="r",
            motivo="   ",
            evidencia_ids=["evt-1"],
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_anular_sin_evidencia_es_rechazado() -> None:
    service, repo, _ = _make_service()
    with pytest.raises(EvidenciaRequeridaError):
        await service.decide(
            "s1",
            decision=DecisionSesion.ANULADO,
            actor="r",
            motivo="fraude claro",
            evidencia_ids=[],
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_aprobar_no_exige_motivo_ni_evidencia() -> None:
    service, repo, _ = _make_service()
    result = await service.decide(
        "s1", decision=DecisionSesion.APROBADO, actor="r", motivo=None
    )
    assert result.nota_anulada is False
    assert repo.persisted == [("s1", "aprobado", "r", None, ())]


# ---------------------------------------------------------------------------
# Validaciones generales
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rechaza_pendiente_porque_no_es_terminal() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no es terminal"):
        await service.decide(
            "s1", decision=DecisionSesion.PENDIENTE, actor="r", motivo=None
        )


@pytest.mark.asyncio
async def test_decide_sesion_inexistente_lanza_error() -> None:
    service, _, _ = _make_service()
    with pytest.raises(ValueError, match="no encontrada"):
        await service.decide(
            "no-existe", decision=DecisionSesion.APROBADO, actor="r", motivo=None
        )


@pytest.mark.asyncio
async def test_decide_inmutable_lanza_error_y_audita_intento() -> None:
    """RN-RV-07: una vez decidida, NO se puede cambiar. El intento queda auditado."""
    service, repo, auditor = _make_service(
        records={
            "s2": ReviewDecisionRecord(
                session_id="s2",
                decision=DecisionSesion.ANULADO,
                actor="revisor-original",
                decision_at="2026-08-01T10:00:00+00:00",
                motivo="fraude",
                evidencia_ids=("evt-9",),
            )
        }
    )
    with pytest.raises(DecisionAlreadyMadeError) as exc:
        await service.decide(
            "s2",
            decision=DecisionSesion.APROBADO,
            actor="revisor-malicioso",
            motivo="trato de cambiarla",
        )
    assert exc.value.current == DecisionSesion.ANULADO
    # No se persistio
    assert not any(p[0] == "s2" and p[1] == "aprobado" for p in repo.persisted)
    # Pero el intento quedo en el audit log con proposito de rechazo
    assert auditor.calls == [
        (
            "s2",
            "revisor-malicioso",
            "anulado",  # decision actual, NO la intentada
            "Intentó cambiar una decisión ya registrada — RECHAZADO "
            "(las decisiones no se pueden modificar)",
        )
    ]


# ---------------------------------------------------------------------------
# Reversibilidad por acto compensatorio append-only (D10b)
# ---------------------------------------------------------------------------


def test_nota_esta_anulada_deriva_del_ultimo_acto() -> None:
    from app.domain.review.decision import nota_esta_anulada

    # Anulada y sin restitucion posterior -> anulada.
    assert nota_esta_anulada(DecisionSesion.ANULADO, False) is True
    # Anulada PERO con acto compensatorio posterior -> restituida (no anulada).
    assert nota_esta_anulada(DecisionSesion.ANULADO, True) is False
    # Aprobada / pendiente -> nunca anulada.
    assert nota_esta_anulada(DecisionSesion.APROBADO, False) is False
    assert nota_esta_anulada(DecisionSesion.PENDIENTE, False) is False


@pytest.mark.asyncio
async def test_revertir_es_append_only_no_muta_el_acto_de_anulacion_original() -> None:
    service, repo, auditor = _make_service()
    await service.decide(
        "s1",
        decision=DecisionSesion.ANULADO,
        actor="autoridad-1",
        motivo="fraude",
        evidencia_ids=["evt-1"],
    )
    persisted_tras_anular = list(repo.persisted)

    await service.revertir_anulacion(
        "s1", actor="c18-apelacion", motivo="apelacion exitosa"
    )

    # La decision NO se muta al revertir (append-only): persisted igual.
    assert repo.persisted == persisted_tras_anular
    # El acto de anulacion original sigue en el audit + hay un acto de restitucion.
    acciones = [c[2] for c in auditor.calls]
    assert "anulado" in acciones
    assert "nota_restituida" in acciones
    restitucion = next(c for c in auditor.calls if c[2] == "nota_restituida")
    assert restitucion[1] == "c18-apelacion"
    assert "restitu" in restitucion[3].lower()


@pytest.mark.asyncio
async def test_revertir_una_nota_no_anulada_es_rechazado() -> None:
    service, repo, _ = _make_service(
        records={
            "s3": ReviewDecisionRecord(
                session_id="s3",
                decision=DecisionSesion.APROBADO,
                actor="r",
                decision_at="2026-08-01T10:00:00+00:00",
                motivo="ok",
                evidencia_ids=(),
            )
        }
    )
    with pytest.raises(ValueError, match="no.*anulad"):
        await service.revertir_anulacion("s3", actor="x", motivo="y")


@pytest.mark.asyncio
async def test_revertir_sin_motivo_es_rechazado() -> None:
    service, _, _ = _make_service()
    await service.decide(
        "s1",
        decision=DecisionSesion.ANULADO,
        actor="a",
        motivo="fraude",
        evidencia_ids=["evt-1"],
    )
    with pytest.raises(MotivoRequeridoError):
        await service.revertir_anulacion("s1", actor="x", motivo="  ")
