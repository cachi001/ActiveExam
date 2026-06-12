"""Tests puros del motor de retencion (c-19).

Sin DB: uso fakes en memoria para cada puerto. El test verifica la
orquestacion del motor — que respete los holds, que llame a los deleters
correctos, que escriba al auditor con el actor y la razon correctos.

Sigo la regla dura del proyecto (RN-DSR-02 + L2.5):
- Sesiones con hold NO se borran.
- Cada accion queda registrada en el auditor.
- El reporte refleja exactamente que se hizo y que se difirio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from app.application.retention.engine import RetentionEngine
from app.domain.retention.hold import HoldDecision, HoldVerifier
from app.domain.retention.policy import RetentionPolicy
from app.domain.retention.report import RetentionRunReport


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAgingRepo:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.last_cutoff: datetime | None = None

    async def find_older_than(self, cutoff: datetime) -> list[str]:
        self.last_cutoff = cutoff
        return list(self._ids)


class FakeEgressRepo:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    async def find_egressed_with_biometry(self) -> list[str]:
        return list(self._ids)


@dataclass
class FakeHoldVerifier:
    """Verifier que responde HOLD para ids especificados; NO_HOLD para el resto."""

    holds: set[str] = field(default_factory=set)

    async def verify(self, session_id: str) -> HoldDecision:
        return HoldDecision.HOLD if session_id in self.holds else HoldDecision.NO_HOLD


@dataclass
class FakeSessionDeleter:
    deleted: list[str] = field(default_factory=list)

    async def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)


@dataclass
class FakeEmbeddingDeleter:
    deletions: dict[str, int] = field(default_factory=dict)  # usuario_id -> filas
    next_count: int = 1

    async def delete_for_user(self, usuario_id: str) -> int:
        self.deletions[usuario_id] = self.next_count
        return self.next_count


@dataclass
class FakeFotoDeleter:
    deletions: dict[str, int] = field(default_factory=dict)
    next_count: int = 1

    async def delete_for_user(self, usuario_id: str) -> int:
        self.deletions[usuario_id] = self.next_count
        return self.next_count


@dataclass
class FakeAuditor:
    session_deleted: list[tuple[str, str, str]] = field(default_factory=list)
    hold_deferred: list[tuple[str, str]] = field(default_factory=list)
    biometric_egress: list[tuple[str, str, int, int]] = field(default_factory=list)

    async def log_session_deleted(
        self, session_id: str, *, actor: str, reason: str
    ) -> None:
        self.session_deleted.append((session_id, actor, reason))

    async def log_hold_deferred(self, session_id: str, *, actor: str) -> None:
        self.hold_deferred.append((session_id, actor))

    async def log_biometric_egress(
        self,
        usuario_id: str,
        *,
        actor: str,
        embeddings_deleted: int,
        fotos_deleted: int,
    ) -> None:
        self.biometric_egress.append(
            (usuario_id, actor, embeddings_deleted, fotos_deleted)
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


def _make_engine(
    *,
    aged: list[str] | None = None,
    egressed: list[str] | None = None,
    holds: set[str] | None = None,
) -> tuple[
    RetentionEngine,
    FakeSessionDeleter,
    FakeEmbeddingDeleter,
    FakeFotoDeleter,
    FakeAuditor,
    FakeHoldVerifier,
]:
    session_deleter = FakeSessionDeleter()
    embedding_deleter = FakeEmbeddingDeleter()
    foto_deleter = FakeFotoDeleter()
    auditor = FakeAuditor()
    verifier = FakeHoldVerifier(holds=set(holds or []))

    engine = RetentionEngine(
        aging_repo=FakeAgingRepo(aged or []),
        egress_repo=FakeEgressRepo(egressed or []),
        hold_verifier=verifier,
        session_deleter=session_deleter,
        embedding_deleter=embedding_deleter,
        foto_deleter=foto_deleter,
        auditor=auditor,
        now=_now,
    )
    return engine, session_deleter, embedding_deleter, foto_deleter, auditor, verifier


# ---------------------------------------------------------------------------
# apply_session_retention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_retention_sin_sesiones_no_borra() -> None:
    engine, deleter, _, _, auditor, _ = _make_engine(aged=[])
    report = await engine.apply_session_retention(
        RetentionPolicy.default(), actor="retention-job"
    )
    assert isinstance(report, RetentionRunReport)
    assert report.total_deletions == 0
    assert report.total_holds_deferred == 0
    assert deleter.deleted == []
    assert auditor.session_deleted == []
    assert auditor.hold_deferred == []


@pytest.mark.asyncio
async def test_session_retention_aplica_cutoff_correcto() -> None:
    """El motor pide al aging_repo sesiones anteriores a now - session_max_age_days."""
    aging = FakeAgingRepo([])
    engine = RetentionEngine(
        aging_repo=aging,
        egress_repo=FakeEgressRepo([]),
        hold_verifier=FakeHoldVerifier(),
        session_deleter=FakeSessionDeleter(),
        embedding_deleter=FakeEmbeddingDeleter(),
        foto_deleter=FakeFotoDeleter(),
        auditor=FakeAuditor(),
        now=_now,
    )
    await engine.apply_session_retention(
        RetentionPolicy(session_max_age_days=180, audit_log_retention_years=5),
        actor="job",
    )
    assert aging.last_cutoff == _now() - timedelta(days=180)


@pytest.mark.asyncio
async def test_session_retention_sesion_aged_sin_hold_se_borra() -> None:
    engine, deleter, _, _, auditor, _ = _make_engine(aged=["s-1"])
    report = await engine.apply_session_retention(
        RetentionPolicy.default(), actor="retention-job"
    )
    assert report.total_deletions == 1
    assert report.deletions[0].target_id == "s-1"
    assert report.deletions[0].target_kind == "session"
    assert report.deletions[0].reason == "age_exceeded"
    assert deleter.deleted == ["s-1"]
    assert auditor.session_deleted == [("s-1", "retention-job", "age_exceeded")]


@pytest.mark.asyncio
async def test_session_retention_sesion_aged_con_hold_se_difiere() -> None:
    engine, deleter, _, _, auditor, _ = _make_engine(
        aged=["s-1"], holds={"s-1"}
    )
    report = await engine.apply_session_retention(
        RetentionPolicy.default(), actor="retention-job"
    )
    assert report.total_deletions == 0
    assert report.total_holds_deferred == 1
    assert report.holds_deferred == ["s-1"]
    assert deleter.deleted == []
    assert auditor.session_deleted == []
    assert auditor.hold_deferred == [("s-1", "retention-job")]


@pytest.mark.asyncio
async def test_session_retention_mix_borra_solo_las_sin_hold() -> None:
    engine, deleter, _, _, auditor, _ = _make_engine(
        aged=["s-1", "s-2", "s-3"], holds={"s-2"}
    )
    report = await engine.apply_session_retention(
        RetentionPolicy.default(), actor="job"
    )
    assert report.total_deletions == 2
    assert sorted(d.target_id for d in report.deletions) == ["s-1", "s-3"]
    assert report.holds_deferred == ["s-2"]
    assert sorted(deleter.deleted) == ["s-1", "s-3"]
    assert {e[0] for e in auditor.session_deleted} == {"s-1", "s-3"}
    assert auditor.hold_deferred == [("s-2", "job")]


# ---------------------------------------------------------------------------
# apply_embedding_egress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_egress_sin_usuarios_no_borra_nada() -> None:
    engine, _, emb, foto, auditor, _ = _make_engine(egressed=[])
    report = await engine.apply_embedding_egress(actor="retention-job")
    assert report.total_deletions == 0
    assert emb.deletions == {}
    assert foto.deletions == {}
    assert auditor.biometric_egress == []


@pytest.mark.asyncio
async def test_embedding_egress_borra_embedding_y_foto_de_usuario_egresado() -> None:
    engine, _, emb, foto, auditor, _ = _make_engine(egressed=["u-1"])
    report = await engine.apply_embedding_egress(actor="retention-job")
    # 1 embedding + 1 foto borradas
    assert report.total_deletions == 2
    kinds = sorted(d.target_kind for d in report.deletions)
    assert kinds == ["embedding_referencia", "foto_referencia"]
    assert all(d.reason == "user_egress" for d in report.deletions)
    assert emb.deletions == {"u-1": 1}
    assert foto.deletions == {"u-1": 1}
    assert auditor.biometric_egress == [("u-1", "retention-job", 1, 1)]


@pytest.mark.asyncio
async def test_embedding_egress_holds_no_aplican_al_egreso() -> None:
    """Importante: el hold por caso disciplinario solo difiere la eliminacion
    de SESIONES. El egreso del usuario es un evento legal independiente que
    elimina embeddings/fotos sin importar holds (Ley 25.326: principio de
    minimizacion). En slim no hay holds de todas formas (NullHoldVerifier)."""
    engine, _, emb, _, _, _ = _make_engine(egressed=["u-1"], holds={"u-1"})
    report = await engine.apply_embedding_egress(actor="job")
    # u-1 tiene hold por sesion pero igual se le borra el embedding al egreso
    assert emb.deletions == {"u-1": 1}
    assert report.total_deletions == 2
