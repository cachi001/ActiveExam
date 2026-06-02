"""Integridad liviana por screenshot (D9).

SHA-256 del contenido base64 tal como llega del cliente. Criterio determinista:
el hash se calcula sobre los bytes UTF-8 del string base64, no sobre los bytes
decodificados de la imagen. Esto es consistente (mismo input = mismo hash) y
evita convertir el base64 solo para hashear.

PRODUCCION: este SHA-256 es integridad basica de alcance demo. La cadena de
custodia completa requiere:
  - HMAC con clave maestra (Vault) sobre los bytes de la imagen decodificada
  - Firma encadenada server-side
  - Almacenamiento WORM (MinIO/S3 Object Lock)
  - Re-inferencia diferida en worker con resultado firmado
Ver knowledge-base/08_arquitectura_propuesta.md §Cadena de custodia.
"""

from __future__ import annotations

import hashlib


def sha256_hex(screenshot_b64: str | None) -> str | None:
    """Calcula el SHA-256 hex del screenshot base64.

    Args:
        screenshot_b64: Screenshot en base64 tal como llega del cliente.
            None o string vacio → devuelve None (la columna queda NULL).

    Returns:
        String hex de 64 caracteres, o None si no hay screenshot.

    Note:
        El hash se calcula sobre los bytes UTF-8 del string base64 (no sobre
        los bytes de la imagen decodificada). Criterio documentado y determinista.
        PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada).
    """
    if not screenshot_b64:
        return None
    return hashlib.sha256(screenshot_b64.encode("utf-8")).hexdigest()
