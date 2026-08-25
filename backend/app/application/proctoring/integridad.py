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

import base64
import binascii
import hashlib
import secrets


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


def sha256_de_imagen(screenshot_b64: str | None) -> str | None:
    """SHA-256 hex de los BYTES DECODIFICADOS de la imagen.

    Distinto de ``sha256_hex``, que hashea el string base64 tal cual llega. Los
    dos son validos y miden cosas distintas; este existe porque es el que calcula
    EL CLIENTE (`hashClip(bytes)` sobre el binario), y es el unico con el que se
    puede comparar lo que el cliente afirma.

    Saca el prefijo `data:image/...;base64,` antes de decodificar: el cliente lo
    manda en el string pero hashea solo la imagen.

    Devuelve None si no hay screenshot o si el base64 es ilegible — un payload
    roto no puede tumbar la ingesta (el veredicto queda 'no_verificable').
    """
    if not screenshot_b64:
        return None
    _, _, crudo = screenshot_b64.rpartition(",")
    crudo = crudo or screenshot_b64
    try:
        binario = base64.b64decode(crudo, validate=True)
    except (binascii.Error, ValueError):
        return None
    return hashlib.sha256(binario).hexdigest()


#: Veredictos de la primera capa de la cadena de custodia (cliente -> backend).
CUSTODIA_COINCIDE = "coincide"
CUSTODIA_DISCREPANCIA = "discrepancia"
CUSTODIA_NO_VERIFICABLE = "no_verificable"


def verificar_custodia_cliente(
    screenshot_b64: str | None, sha256_cliente: str | None
) -> str:
    """Compara el hash que AFIRMA el cliente contra el que calcula el servidor.

    Es la primera capa de la cadena de custodia de la regla dura #6: el backend
    nunca confia en el dato crudo del cliente, lo re-hashea. Hasta c-78 el campo
    se aceptaba en el schema y se descartaba, asi que la comparacion no existia.

    Veredictos:
      - ``coincide``: el hash del cliente corresponde a la imagen que llego.
      - ``discrepancia``: no corresponde. El contenido cambio entre el cliente y
        el servidor, o el cliente informo cualquier cosa. Es una SENAL para el
        revisor humano — **nunca** una sancion (L2.5, regla dura #5).
      - ``no_verificable``: falta el hash del cliente (cliente viejo, WebCrypto no
        disponible), falta el screenshot, o el base64 es ilegible. NO es una
        acusacion: seria acusar por una carencia tecnica.
    """
    if not sha256_cliente:
        return CUSTODIA_NO_VERIFICABLE
    calculado = sha256_de_imagen(screenshot_b64)
    if calculado is None:
        return CUSTODIA_NO_VERIFICABLE
    # compare_digest para no filtrar por tiempo cuantos caracteres acerto quien
    # este probando hashes; en minusculas porque el hex del cliente puede venir
    # en mayusculas segun la implementacion de WebCrypto, y eso no es manipulacion.
    if secrets.compare_digest(sha256_cliente.strip().lower(), calculado):
        return CUSTODIA_COINCIDE
    return CUSTODIA_DISCREPANCIA
