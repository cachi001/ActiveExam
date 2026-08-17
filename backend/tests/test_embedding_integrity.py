"""Tests del validador de integridad del embedding de referencia (C-70 hardening).

Regla dura #6 (cliente = sensor no confiable): el endpoint de enrollment recibe
el embedding 128-d del cliente. Sin re-inferencia server-side (fuera de alcance),
esta validación PURA rechaza los vectores inyectados triviales: no-finitos,
todo-ceros, magnitudes absurdas y el vector FAKE de desarrollo.

PURO: no DB, no async — corre con cualquier pytest.

Contrato clave: NO debe rechazar los embeddings sintéticos que usan los tests
existentes de enrollment (C-56 rampa `[i/128]`, C-57 `[0.1]*128`), ni un
descriptor real (valores chicos y variados). Solo corta la basura inyectada.
"""

from __future__ import annotations

import math

import pytest

from app.domain.biometrics.embedding_integrity import (
    MAX_ABS_COMPONENTE,
    EmbeddingIntegridadError,
    validar_integridad_embedding,
)

# Vector FAKE de desarrollo del front (devConfig.ts):
#   Array.from({length:128}, (_, i) => Math.sin(i + 1))
FAKE_EMBEDDING_128D = [math.sin(i + 1) for i in range(128)]


def _descriptor_realista() -> list[float]:
    """Descriptor face-api-128d plausible: valores chicos y variados en ~[-0.3, 0.3]."""
    return [0.3 * math.cos(i * 0.7) for i in range(128)]


# --- Casos que DEBEN PASAR (no levantan) -----------------------------------


def test_descriptor_realista_pasa():
    validar_integridad_embedding(_descriptor_realista())  # no debe levantar


def test_constante_01_pasa_no_rompe_c57():
    # test_c57_activeexam_enrollment_e2e postea [0.1]*128 y espera éxito.
    validar_integridad_embedding([0.1] * 128)


def test_rampa_pasa_no_rompe_c56():
    # test_c56_enrollment_endpoints usa [i/128 for i in range(128)] (empieza en 0).
    validar_integridad_embedding([float(i) / 128.0 for i in range(128)])


# --- Casos que DEBEN RECHAZARSE (levantan EmbeddingIntegridadError) ---------


def test_nan_rechazado():
    vec = _descriptor_realista()
    vec[10] = float("nan")
    with pytest.raises(EmbeddingIntegridadError):
        validar_integridad_embedding(vec)


def test_inf_rechazado():
    vec = _descriptor_realista()
    vec[0] = float("inf")
    with pytest.raises(EmbeddingIntegridadError):
        validar_integridad_embedding(vec)


def test_todo_ceros_rechazado():
    with pytest.raises(EmbeddingIntegridadError):
        validar_integridad_embedding([0.0] * 128)


def test_magnitud_absurda_rechazada():
    vec = _descriptor_realista()
    vec[5] = MAX_ABS_COMPONENTE + 1.0
    with pytest.raises(EmbeddingIntegridadError):
        validar_integridad_embedding(vec)


def test_vector_fake_de_dev_rechazado():
    # El vector de bypass de desarrollo NUNCA debe poder enrolarse en prod.
    with pytest.raises(EmbeddingIntegridadError):
        validar_integridad_embedding(list(FAKE_EMBEDDING_128D))
