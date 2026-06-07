"""Tests unitarios del servicio de cifrado de embeddings biometricos (C-56).

Cubre:
- Round-trip encrypt → decrypt devuelve el vector original (128 floats).
- El ciphertext NO es el vector en claro (no se puede leer sin la clave).
- Ausencia de EMBEDDING_ENCRYPTION_KEY lanza ConfigurationError.
- Clave invalida (no es Fernet valido) lanza ConfigurationError.
- Ciphertext tampered lanza EmbeddingEncryptionError.

Estos tests son UNITARIOS: no requieren DB ni stack. Deben pasar siempre.
"""

from __future__ import annotations

import json
import math

import pytest
from cryptography.fernet import Fernet

from app.infrastructure.crypto.embedding_encryption import (
    ConfigurationError,
    EmbeddingEncryptionError,
    EmbeddingEncryptionService,
)


def _fernet_key() -> str:
    """Genera una clave Fernet valida para tests."""
    return Fernet.generate_key().decode("ascii")


def _vector_128() -> list[float]:
    """Vector de 128 floats determinista para tests."""
    return [float(i) / 128.0 for i in range(128)]


# ---------------------------------------------------------------------------
# 2.3 Test: round-trip encrypt → decrypt
# ---------------------------------------------------------------------------

def test_round_trip_devuelve_vector_original(monkeypatch: pytest.MonkeyPatch) -> None:
    """encrypt(v) → decrypt → misma lista de 128 floats (tolerancia float64)."""
    clave = _fernet_key()
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave)
    # Invalidar el cache de get_settings para que tome la nueva clave.
    from app import config as cfg
    cfg.get_settings.cache_clear()

    service = EmbeddingEncryptionService()
    vector = _vector_128()

    ciphertext = service.encrypt(vector)
    recovered = service.decrypt(ciphertext)

    assert len(recovered) == 128
    for original, dec in zip(vector, recovered):
        assert math.isclose(original, dec, rel_tol=1e-9), (
            f"Diferencia inesperada: {original} != {dec}"
        )


def test_ciphertext_no_es_vector_en_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    """El ciphertext no contiene el vector serializado en texto plano."""
    clave = _fernet_key()
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    service = EmbeddingEncryptionService()
    vector = _vector_128()

    ciphertext = service.encrypt(vector)
    vector_json = json.dumps(vector)

    # El Fernet token es base64-urlsafe opaco; no contiene el JSON del vector.
    assert vector_json not in ciphertext


def test_encrypt_es_determinista_entre_llamadas_diferentes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos llamadas a encrypt producen tokens distintos (Fernet usa IV aleatorio)."""
    clave = _fernet_key()
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    service = EmbeddingEncryptionService()
    vector = _vector_128()

    ct1 = service.encrypt(vector)
    ct2 = service.encrypt(vector)

    # Fernet agrega timestamp + IV aleatorio: tokens siempre distintos.
    assert ct1 != ct2
    # Pero ambos se descifran al mismo vector.
    assert service.decrypt(ct1) == service.decrypt(ct2)


# ---------------------------------------------------------------------------
# 2.3 Test: ausencia de clave lanza ConfigurationError
# ---------------------------------------------------------------------------

def test_sin_clave_lanza_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si EMBEDDING_ENCRYPTION_KEY no esta configurada, lanza ConfigurationError."""
    monkeypatch.delenv("EMBEDDING_ENCRYPTION_KEY", raising=False)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    with pytest.raises(ConfigurationError, match="EMBEDDING_ENCRYPTION_KEY"):
        EmbeddingEncryptionService()


def test_clave_invalida_lanza_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si la clave no es un Fernet valido, lanza ConfigurationError."""
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", "no-es-una-clave-fernet-valida")
    from app import config as cfg
    cfg.get_settings.cache_clear()

    with pytest.raises(ConfigurationError):
        EmbeddingEncryptionService()


# ---------------------------------------------------------------------------
# Test: ciphertext tampered lanza EmbeddingEncryptionError
# ---------------------------------------------------------------------------

def test_ciphertext_tampered_lanza_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un ciphertext alterado lanza EmbeddingEncryptionError al descifrar."""
    clave = _fernet_key()
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    service = EmbeddingEncryptionService()
    vector = _vector_128()
    ciphertext = service.encrypt(vector)

    # Alterar el ciphertext.
    tampered = ciphertext[:-5] + "XXXXX"

    with pytest.raises(EmbeddingEncryptionError):
        service.decrypt(tampered)


def test_ciphertext_con_clave_diferente_lanza_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un ciphertext cifrado con una clave distinta lanza EmbeddingEncryptionError."""
    clave_a = _fernet_key()
    clave_b = _fernet_key()
    assert clave_a != clave_b

    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave_a)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    service_a = EmbeddingEncryptionService()

    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", clave_b)
    cfg.get_settings.cache_clear()
    service_b = EmbeddingEncryptionService()

    vector = _vector_128()
    ciphertext = service_a.encrypt(vector)

    with pytest.raises(EmbeddingEncryptionError):
        service_b.decrypt(ciphertext)
