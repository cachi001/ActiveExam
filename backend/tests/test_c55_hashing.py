"""Tests unitarios de hashing de passwords (C-55, infraestructura).

Sin DB ni red — puro hashing bcrypt via passlib.
"""

from __future__ import annotations

from app.infrastructure.auth.hashing import hashear_password, verificar_password


def test_hash_es_verificable() -> None:
    hashed = hashear_password("MiPassword123")
    assert verificar_password("MiPassword123", hashed) is True


def test_password_incorrecto_rechazado() -> None:
    hashed = hashear_password("Correcto123")
    assert verificar_password("Incorrecto456", hashed) is False


def test_hashes_distintos_para_mismo_password() -> None:
    """bcrypt genera salt aleatorio: dos hashes del mismo password son distintos."""
    pw = "MismoPassword"
    h1 = hashear_password(pw)
    h2 = hashear_password(pw)
    assert h1 != h2
    # Pero ambos verifican.
    assert verificar_password(pw, h1) is True
    assert verificar_password(pw, h2) is True


def test_password_vacio_hasheable_y_verificable() -> None:
    """Passlib acepta strings vacios; la validacion de longitud minima es en la presentacion."""
    hashed = hashear_password("")
    assert verificar_password("", hashed) is True
    assert verificar_password("no-vacio", hashed) is False
