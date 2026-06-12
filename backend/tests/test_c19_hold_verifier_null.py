"""Tests puros del HoldDecision y del NullHoldVerifier (slim default).

Slim no tiene tabla ``caso_disciplinario`` (esa vive en la rama full,
migracion 0002, que NO se aplica en produccion Railway). Por eso el
HoldVerifier por defecto en slim es Null: nunca reporta hold. La
implementacion SQL real sobre ``caso_disciplinario`` se difiere a c-69.

Este tipo de "implementacion null" es legitimo en hexagonal: el puerto
mantiene el contrato, la implementacion default no causa efecto, y el
sucesor c-69 reemplaza ``NullHoldVerifier`` por ``SqlHoldVerifier`` sin
tocar dominio ni application.
"""

from __future__ import annotations

import pytest

from app.domain.retention.hold import HoldDecision
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier


def test_hold_decision_es_enum_con_dos_valores() -> None:
    assert HoldDecision.HOLD.value == "hold"
    assert HoldDecision.NO_HOLD.value == "no_hold"
    assert len(list(HoldDecision)) == 2


@pytest.mark.asyncio
async def test_null_verifier_siempre_devuelve_no_hold() -> None:
    """En slim no hay forma de saber si una sesion esta en revision (no
    existe tabla de casos). El verificador null no tiene info -> NO_HOLD."""
    verifier = NullHoldVerifier()
    assert await verifier.verify("session-id-cualquiera") == HoldDecision.NO_HOLD
    assert await verifier.verify("otra-sesion") == HoldDecision.NO_HOLD
    assert await verifier.verify("") == HoldDecision.NO_HOLD


@pytest.mark.asyncio
async def test_null_verifier_no_falla_con_id_vacio_o_invalido() -> None:
    """El verificador null NO valida el id — es responsabilidad del caller.
    Esto evita que un id mal formado rompa el pipeline de retencion."""
    verifier = NullHoldVerifier()
    # Estos no deben tirar excepciones:
    assert await verifier.verify("00000000-0000-0000-0000-000000000000") == HoldDecision.NO_HOLD
    assert await verifier.verify("not-a-uuid") == HoldDecision.NO_HOLD
