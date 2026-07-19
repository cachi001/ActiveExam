"""EvidenceCipher — cifrado at-rest de la evidencia (screenshots). Puro, sin DB."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.infrastructure.crypto.evidence_encryption import EvidenceCipher, EvidenceCipherError

_KEY = Fernet.generate_key().decode()


def test_roundtrip_cifra_y_descifra():
    c = EvidenceCipher(key=_KEY)
    plano = "data:image/png;base64,AAAABBBBCCCC=="
    token = c.encrypt(plano)
    assert token != plano  # ya no está en claro
    assert token.startswith("gA")  # token Fernet
    assert c.decrypt(token) == plano


def test_none_pasa_como_none():
    c = EvidenceCipher(key=_KEY)
    assert c.encrypt(None) is None
    assert c.decrypt(None) is None


def test_fallback_legacy_en_claro():
    # Un registro viejo en claro (no es token Fernet) se devuelve tal cual.
    c = EvidenceCipher(key=_KEY)
    legacy = "screenshot-viejo-en-claro-base64"
    assert c.decrypt(legacy) == legacy


def test_clave_de_otra_instancia_no_descifra_pero_no_rompe():
    # Token de otra clave (rotación sin re-cifrar): se trata como legacy, no explota.
    otro = EvidenceCipher(key=Fernet.generate_key().decode())
    token = otro.encrypt("secreto")
    c = EvidenceCipher(key=_KEY)
    # No puede descifrarlo con otra clave → devuelve el token tal cual (no crashea).
    assert c.decrypt(token) == token


def test_clave_ausente_falla():
    with pytest.raises(EvidenceCipherError):
        EvidenceCipher(key="")
