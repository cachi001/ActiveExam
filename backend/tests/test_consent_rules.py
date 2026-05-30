"""Tests de las reglas PURAS del consentimiento (C-08).

Verifica D1/D2/D4 sin DB:
- accion afirmativa exigida server-side (RN-CO-02): sin marca -> 422.
- hash que sella el TEXTO EXACTO + el acuse (D1): determinista y sensible al texto.
- gate (D4): consentido/alternativa -> avanza; no resuelto -> 403.
"""

from __future__ import annotations

import pytest

from app.domain.consent_flow import rules
from app.domain.consent_flow.errors import (
    ConsentNotResolvedError,
    MissingAffirmativeActionError,
    UnknownConsentVersionError,
)
from app.domain.consent_flow.rules import ResolucionConsentimiento
from app.domain.consent_flow.text_catalog import VERSION_VIGENTE, get_texto


def test_accion_afirmativa_ausente_rechazada() -> None:
    with pytest.raises(MissingAffirmativeActionError):
        rules.validar_accion_afirmativa(False)


def test_accion_afirmativa_presente_ok() -> None:
    rules.validar_accion_afirmativa(True)  # no levanta


def test_version_desconocida_rechazada() -> None:
    with pytest.raises(UnknownConsentVersionError):
        rules.resolver_texto("v999")


def test_hash_acuse_deterministico() -> None:
    texto = get_texto(VERSION_VIGENTE)
    args = dict(
        user_id="u1",
        exam_id="e1",
        texto=texto,
        timestamp="2026-05-30T10:00:00Z",
        affirmative_action=True,
    )
    assert rules.hash_acuse(**args) == rules.hash_acuse(**args)


def test_hash_acuse_sella_texto_exacto() -> None:
    # El hash incorpora el hash del cuerpo del texto: dos versiones de texto
    # distintas producen acuses distintos (prueba defendible, D1).
    texto = get_texto(VERSION_VIGENTE)

    class _Otro:
        version = texto.version
        def hash_texto(self) -> str:
            return "otro-hash-de-texto"

    h1 = rules.hash_acuse(
        user_id="u", exam_id="e", texto=texto, timestamp="t", affirmative_action=True
    )
    h2 = rules.hash_acuse(
        user_id="u", exam_id="e", texto=_Otro(), timestamp="t", affirmative_action=True
    )
    assert h1 != h2


def test_gate_consentido_avanza() -> None:
    assert rules.evaluar_gate(ResolucionConsentimiento.CONSENTIDO) is True
    assert rules.biometria_habilitada(ResolucionConsentimiento.CONSENTIDO) is True


def test_gate_alternativa_avanza_sin_biometria() -> None:
    assert rules.evaluar_gate(ResolucionConsentimiento.VIA_ALTERNATIVA) is True
    # La via alternativa NO exige biometria.
    assert rules.biometria_habilitada(ResolucionConsentimiento.VIA_ALTERNATIVA) is False


def test_gate_no_resuelto_bloquea() -> None:
    with pytest.raises(ConsentNotResolvedError):
        rules.evaluar_gate(ResolucionConsentimiento.NO_RESUELTO)


def test_texto_vigente_tiene_cinco_bloques() -> None:
    bloques = get_texto(VERSION_VIGENTE).bloques()
    assert set(bloques) == {
        "que_se_recolecta",
        "como_se_recolecta",
        "donde_se_almacena",
        "cuanto_tiempo",
        "derechos_titular",
    }
    assert all(v.strip() for v in bloques.values())
