#!/usr/bin/env python3
"""Script utilitario: genera una EMBEDDING_ENCRYPTION_KEY valida para desarrollo.

C-56: la clave Fernet se usa para cifrar at-rest el embedding biometrico de
referencia. Es una clave de 32 bytes en base64-urlsafe generada con
``cryptography.fernet.Fernet.generate_key()``.

NUNCA usar esta clave en produccion sin pasarla por Vault. En produccion la clave
se inyecta desde Vault en tmpfs efimero (nunca en codigo ni imagen Docker).

Uso:
    python scripts/generar_embedding_key.py

Salida:
    EMBEDDING_ENCRYPTION_KEY=<clave-base64-urlsafe>

Agregar al .env de desarrollo local (gitignoreado). NUNCA commitear.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def main() -> None:
    clave = Fernet.generate_key().decode("ascii")
    print("=" * 60)
    print("EMBEDDING_ENCRYPTION_KEY para desarrollo local:")
    print("=" * 60)
    print(f"EMBEDDING_ENCRYPTION_KEY={clave}")
    print()
    print("ADVERTENCIA:")
    print("  - Solo para desarrollo local.")
    print("  - NUNCA commitear al repositorio.")
    print("  - En produccion: inyectar desde Vault en tmpfs efimero.")
    print("  - Rotar la clave requiere re-encriptar todos los embeddings.")
    print("=" * 60)


if __name__ == "__main__":
    main()
