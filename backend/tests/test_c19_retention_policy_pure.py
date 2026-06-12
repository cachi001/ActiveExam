"""Tests puros (sin stack) del modelo de politicas de retencion de c-19.

c-19 en rama slim (Postgres puro): la politica es un value object inmutable
con dos thresholds principales (sesiones y audit log). El archivado a Parquet
y la compresion TimescaleDB quedan diferidos a c-67 (sucesor planificado).

Estos tests describen el contrato del dominio sin acoplarse a la DB ni a
SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.domain.retention.policy import RetentionPolicy


def test_default_policy_session_180d_audit_5y() -> None:
    """La politica por defecto refleja la regla legal (Ley 25.326): 180 dias
    para sesiones de proctoring sin hold, 5 anios para audit log."""
    policy = RetentionPolicy.default()
    assert policy.session_max_age_days == 180
    assert policy.audit_log_retention_years == 5


def test_custom_policy_acepta_valores_validos() -> None:
    policy = RetentionPolicy(session_max_age_days=90, audit_log_retention_years=7)
    assert policy.session_max_age_days == 90
    assert policy.audit_log_retention_years == 7


def test_policy_es_inmutable() -> None:
    """La politica es un value object: no se puede mutar despues de creada
    (frozen=True). Cualquier intento de cambiarla debe fallar."""
    policy = RetentionPolicy.default()
    with pytest.raises(FrozenInstanceError):
        policy.session_max_age_days = 10  # type: ignore[misc]


def test_policy_rechaza_session_max_age_no_positivo() -> None:
    """No tiene sentido una politica de retencion con dias <= 0. El value
    object lo rechaza en construccion."""
    with pytest.raises(ValueError, match="session_max_age_days"):
        RetentionPolicy(session_max_age_days=0, audit_log_retention_years=5)
    with pytest.raises(ValueError, match="session_max_age_days"):
        RetentionPolicy(session_max_age_days=-1, audit_log_retention_years=5)


def test_policy_rechaza_audit_retention_no_positivo() -> None:
    with pytest.raises(ValueError, match="audit_log_retention_years"):
        RetentionPolicy(session_max_age_days=180, audit_log_retention_years=0)
