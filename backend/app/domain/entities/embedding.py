"""Entidad de dominio Embedding facial (PURA, dato SENSIBLE).

Vector biometrico tratado como dato sensible por defecto (SU-08, Ley 25.326): se
almacena CIFRADO at-rest (la columna de persistencia guarda el ciphertext, nunca
el vector en claro) y se ELIMINA al egreso del estudiante (DD-13).

PUREZA (D1): el dominio modela el contrato del campo cifrado (``vector_cifrado``
es bytes opacos para el dominio) y su version/fecha. El algoritmo de cifrado y la
rotacion de claves los opera infraestructura (KMS, `08`); aqui NO se hardcodea
ninguna clave ni se importa cripto concreta. Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Embedding:
    """Embedding facial cifrado at-rest (`04` Embedding, SU-08).

    ``vector_cifrado`` es el ciphertext (bytes) producido por la capa de
    infraestructura con KMS; el dominio lo trata como opaco y nunca lo descifra.
    """

    user_id: str
    vector_cifrado: bytes
    version: str
    fecha: str
    id: str | None = None
