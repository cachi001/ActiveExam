"""Tests unitarios de sha256_hex() — sin DB, sin red.

Verifica comportamiento determinista del hash y manejo de None.
"""

from __future__ import annotations

import hashlib

import pytest

from app.application.proctoring.integridad import sha256_hex


def test_sha256_determinista() -> None:
    """El mismo screenshot produce siempre el mismo hash."""
    b64 = "aGVsbG8gd29ybGQ="  # base64 de "hello world"
    h1 = sha256_hex(b64)
    h2 = sha256_hex(b64)
    assert h1 == h2
    assert h1 is not None


def test_sha256_64_hex_chars() -> None:
    """SHA-256 es siempre 64 caracteres hex."""
    b64 = "dGVzdA=="  # base64 de "test"
    h = sha256_hex(b64)
    assert h is not None
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_sha256_correcto() -> None:
    """El hash calculado coincide con hashlib.sha256 de los bytes UTF-8 del b64."""
    b64 = "aVBPUlI0eUJnZ0FBQUFOU1VoRXVnQUFBQUVBQUFBQkNBWUFBQUFmRmNTSkFBQUFEVWxFUVZSNDJtTms"
    expected = hashlib.sha256(b64.encode("utf-8")).hexdigest()
    assert sha256_hex(b64) == expected


def test_sha256_none_si_no_hay_screenshot() -> None:
    """None como input → None como output (columna queda NULL)."""
    assert sha256_hex(None) is None


def test_sha256_string_vacio_devuelve_none() -> None:
    """String vacio → None (sin screenshot, columna NULL)."""
    assert sha256_hex("") is None


def test_sha256_distintos_screenshots_distintos_hashes() -> None:
    """Screenshots distintos producen hashes distintos (no colision trivial)."""
    b64_a = "aGVsbG8="  # "hello"
    b64_b = "d29ybGQ="  # "world"
    assert sha256_hex(b64_a) != sha256_hex(b64_b)


def test_sha256_con_data_url() -> None:
    """Tambien hashea correctamente si el b64 incluye el prefijo data:image/..."""
    # El sha256 se calcula sobre el string completo (incluyendo el prefijo)
    b64_con_prefijo = "data:image/jpeg;base64,/9j/4AAQSkZJRgAB"
    h = sha256_hex(b64_con_prefijo)
    assert h is not None
    assert len(h) == 64
    expected = hashlib.sha256(b64_con_prefijo.encode("utf-8")).hexdigest()
    assert h == expected
