"""Tests puros del RetentionRunReport y RetentionDeletion.

El reporte de una corrida de retencion es un value object inmutable que
describe que se borro y que se difirio por hold. Es la "salida observable"
del motor — se serializa al response HTTP y al audit log.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.domain.retention.policy import RetentionPolicy
from app.domain.retention.report import RetentionDeletion, RetentionRunReport


def _ts() -> datetime:
    return datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


def test_deletion_es_inmutable() -> None:
    d = RetentionDeletion(
        target_id="s-1", target_kind="session", reason="age_exceeded", at=_ts()
    )
    with pytest.raises(FrozenInstanceError):
        d.target_id = "otro"  # type: ignore[misc]


def test_report_total_deletions_cuenta_lista() -> None:
    policy = RetentionPolicy.default()
    report = RetentionRunReport(
        policy_applied=policy,
        deletions=[
            RetentionDeletion("s-1", "session", "age_exceeded", _ts()),
            RetentionDeletion("s-2", "session", "age_exceeded", _ts()),
            RetentionDeletion("u-3", "embedding_referencia", "user_egress", _ts()),
        ],
        holds_deferred=[],
        run_at=_ts(),
    )
    assert report.total_deletions == 3
    assert report.total_holds_deferred == 0


def test_report_holds_deferred_cuenta_lista() -> None:
    report = RetentionRunReport(
        policy_applied=RetentionPolicy.default(),
        deletions=[],
        holds_deferred=["s-x", "s-y"],
        run_at=_ts(),
    )
    assert report.total_deletions == 0
    assert report.total_holds_deferred == 2


def test_report_es_inmutable() -> None:
    report = RetentionRunReport(
        policy_applied=RetentionPolicy.default(),
        deletions=[],
        holds_deferred=[],
        run_at=_ts(),
    )
    with pytest.raises(FrozenInstanceError):
        report.deletions = []  # type: ignore[misc]


def test_report_filtra_deletions_por_kind() -> None:
    """El reporte expone helpers para inspeccionar borrados por tipo."""
    report = RetentionRunReport(
        policy_applied=RetentionPolicy.default(),
        deletions=[
            RetentionDeletion("s-1", "session", "age_exceeded", _ts()),
            RetentionDeletion("u-1", "embedding_referencia", "user_egress", _ts()),
            RetentionDeletion("u-1", "foto_referencia", "user_egress", _ts()),
            RetentionDeletion("s-2", "session", "age_exceeded", _ts()),
        ],
        holds_deferred=[],
        run_at=_ts(),
    )
    assert report.count_by_kind("session") == 2
    assert report.count_by_kind("embedding_referencia") == 1
    assert report.count_by_kind("foto_referencia") == 1
    assert report.count_by_kind("desconocido") == 0
