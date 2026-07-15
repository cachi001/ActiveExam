"""Tests puros del servicio de RESOLUCION (fase 2), c-71 slice 2 D9/D11/D13.

Verifica las barandas: acto separado con precondicion `caso_abierto` (409 si
no), motivo obligatorio no vacio en toda resolucion, evidencia obligatoria en
`anulado_por_fraude` (400 si falta), inmutabilidad de la resolucion, y que la
anulacion es siempre un acto humano explicito (NUNCA automatica, regla #5).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.application.review.resolution_service import (
    CasoNoAbiertoError,
    EvidenciaRequeridaError,
    MotivoRequeridoError,
    ResolucionAlreadyMadeError,
    ReviewResolutionService,
)
from app.domain.review.decision import (
    DecisionResolucion,
    DecisionRevision,
    ResolutionRecord,
)


@dataclass
class FakeResolutionRepo:
    records: dict[str, ResolutionRecord] = field(default_factory=dict)
    persisted: list[tuple[str, str, str, str]] = field(default_factory=list)
    fake_at: str = "2026-07-13T12:00:00+00:00"

    async def get_resolution(self, session_id: str):
        return self.records.get(session_id)

    async def persist_resolution(
        self,
        session_id: str,
        *,
        resolucion: DecisionResolucion,
        actor: str,
        motivo: str,
    ) -> str:
        self.persisted.append((session_id, resolucion.value, actor, motivo))
        prev = self.records[session_id]
        self.records[session_id] = ResolutionRecord(
            session_id=session_id,
            decision=prev.decision,
            resolucion=resolucion,
            actor=actor,
            resolucion_at=self.fake_at,
            motivo=motivo,
        )
        return self.fake_at


@dataclass
class FakeAuditor:
    calls: list[tuple[str, str, str, str]] = field(default_factory=list)

    async def log_decision(
        self, session_id: str, *, actor: str, decision: str, proposito: str
    ) -> None:
        self.calls.append((session_id, actor, decision, proposito))


def _make(
    decision: DecisionRevision = DecisionRevision.CASO_ABIERTO,
    resolucion: DecisionResolucion | None = None,
):
    repo = FakeResolutionRepo(
        records={
            "s1": ResolutionRecord(
                session_id="s1",
                decision=decision,
                resolucion=resolucion,
                actor=None,
                resolucion_at=None,
                motivo=None,
            )
        }
    )
    auditor = FakeAuditor()
    return ReviewResolutionService(repo=repo, auditor=auditor), repo, auditor


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anular_caso_abierto_persiste_audita_y_anula_la_nota() -> None:
    svc, repo, auditor = _make()
    result = await svc.resolve(
        "s1",
        resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
        actor="revisor-1",
        motivo="copia detectada en 3 clips",
        evidencia_ref="clip-42",
    )
    assert result.resolucion == DecisionResolucion.ANULADO_POR_FRAUDE
    assert result.nota_anulada is True
    assert repo.persisted == [
        ("s1", "anulado_por_fraude", "revisor-1", "copia detectada en 3 clips")
    ]
    # El acto queda auditado con un proposito DISTINTO del de revisar (RN-RV-06)
    assert len(auditor.calls) == 1
    accion, proposito = auditor.calls[0][2], auditor.calls[0][3]
    assert accion == "anulado_por_fraude"
    assert "resolve" in proposito
    # Baranda (b): motivo + referencia a la evidencia quedan en el audit log
    assert "copia detectada en 3 clips" in proposito
    assert "clip-42" in proposito


@pytest.mark.asyncio
async def test_descartar_caso_abierto_valida_la_nota() -> None:
    svc, _, _ = _make()
    result = await svc.resolve(
        "s1",
        resolucion=DecisionResolucion.CASO_DESCARTADO,
        actor="revisor-1",
        motivo="revisado, no hubo fraude",
        evidencia_ref=None,
    )
    assert result.resolucion == DecisionResolucion.CASO_DESCARTADO
    assert result.nota_anulada is False


# ---------------------------------------------------------------------------
# Barandas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_caso_no_abierto_lanza_conflicto() -> None:
    """Precondicion: solo `caso_abierto` es resoluble (409)."""
    svc, repo, _ = _make(decision=DecisionRevision.SIN_HALLAZGOS)
    with pytest.raises(CasoNoAbiertoError):
        await svc.resolve(
            "s1",
            resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
            actor="r",
            motivo="x",
            evidencia_ref="clip",
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_resolver_dos_veces_es_inmutable() -> None:
    svc, repo, _ = _make(resolucion=DecisionResolucion.CASO_DESCARTADO)
    with pytest.raises(ResolucionAlreadyMadeError):
        await svc.resolve(
            "s1",
            resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
            actor="r",
            motivo="x",
            evidencia_ref="clip",
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_motivo_vacio_es_rechazado() -> None:
    svc, repo, _ = _make()
    with pytest.raises(MotivoRequeridoError):
        await svc.resolve(
            "s1",
            resolucion=DecisionResolucion.CASO_DESCARTADO,
            actor="r",
            motivo="   ",
            evidencia_ref=None,
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_anular_sin_evidencia_es_rechazado() -> None:
    svc, repo, _ = _make()
    with pytest.raises(EvidenciaRequeridaError):
        await svc.resolve(
            "s1",
            resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
            actor="r",
            motivo="fraude claro",
            evidencia_ref=None,
        )
    assert repo.persisted == []


@pytest.mark.asyncio
async def test_descartar_no_exige_evidencia() -> None:
    svc, _, _ = _make()
    result = await svc.resolve(
        "s1",
        resolucion=DecisionResolucion.CASO_DESCARTADO,
        actor="r",
        motivo="ok",
        evidencia_ref=None,
    )
    assert result.nota_anulada is False


@pytest.mark.asyncio
async def test_sesion_inexistente_lanza_error() -> None:
    svc, _, _ = _make()
    with pytest.raises(ValueError, match="no encontrada"):
        await svc.resolve(
            "no-existe",
            resolucion=DecisionResolucion.CASO_DESCARTADO,
            actor="r",
            motivo="ok",
            evidencia_ref=None,
        )


# ---------------------------------------------------------------------------
# Reversibilidad por acto compensatorio append-only (D10b, section 11)
# ---------------------------------------------------------------------------


def test_nota_esta_anulada_deriva_del_ultimo_acto() -> None:
    from app.domain.review.decision import nota_esta_anulada

    # Anulada y sin restitucion posterior -> anulada.
    assert nota_esta_anulada(DecisionResolucion.ANULADO_POR_FRAUDE, False) is True
    # Anulada PERO con acto compensatorio posterior -> restituida (no anulada).
    assert nota_esta_anulada(DecisionResolucion.ANULADO_POR_FRAUDE, True) is False
    # Descartada / sin resolucion -> nunca anulada.
    assert nota_esta_anulada(DecisionResolucion.CASO_DESCARTADO, False) is False
    assert nota_esta_anulada(None, False) is False


@pytest.mark.asyncio
async def test_revertir_es_append_only_no_muta_el_acto_de_anulacion() -> None:
    svc, repo, auditor = _make()
    await svc.resolve(
        "s1",
        resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
        actor="autoridad-1",
        motivo="fraude",
        evidencia_ref="clip-1",
    )
    persisted_tras_anular = list(repo.persisted)

    await svc.revertir_anulacion("s1", actor="c18-apelacion", motivo="apelacion exitosa")

    # La columna de resolucion NO se muta al revertir (append-only): persisted igual.
    assert repo.persisted == persisted_tras_anular
    # El acto de anulacion original sigue en el audit + hay un acto de restitucion.
    acciones = [c[2] for c in auditor.calls]
    assert "anulado_por_fraude" in acciones
    assert "nota_restituida" in acciones
    # El acto de restitucion lleva su propio proposito y actor.
    restitucion = next(c for c in auditor.calls if c[2] == "nota_restituida")
    assert restitucion[1] == "c18-apelacion"
    assert "restitu" in restitucion[3].lower()


@pytest.mark.asyncio
async def test_revertir_una_nota_no_anulada_es_rechazado() -> None:
    svc, _, _ = _make(resolucion=DecisionResolucion.CASO_DESCARTADO)
    with pytest.raises(ValueError, match="no.*anulad"):
        await svc.revertir_anulacion("s1", actor="x", motivo="y")
