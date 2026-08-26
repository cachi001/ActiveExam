"""Cadena de custodia cliente -> backend del screenshot: la parte pura (c-78).

El cliente calcula el SHA-256 de la captura y lo manda en
`screenshot_sha256_cliente`. El schema lo acepta desde C-64... y el servicio lo
DESCARTABA: no habia columna donde guardarlo (comentario explicito en
`event_service.ingestar_evento`). O sea que la primera capa de la cadena de
custodia de la regla dura #6 ("el backend re-hashea lo que manda el cliente") no
existia: nadie comparaba nada.

Peor: los dos lados hasheaban COSAS DISTINTAS. El cliente hashea los bytes
decodificados de la imagen; `sha256_hex` hashea los bytes UTF-8 del string
base64 completo, prefijo `data:image/jpeg;base64,` incluido. Compararlos de
frente habria marcado TODOS los eventos como manipulados.

La persistencia se cubre en `tests/proctoring/test_c78_custodia_hash_cliente.py`
(Postgres real), que es donde vive la fixture `db_session`.
"""

from __future__ import annotations

import base64
import hashlib

from app.application.proctoring.integridad import (
    sha256_de_imagen,
    sha256_hex,
    verificar_custodia_cliente,
)

_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_DATA_URL = f"data:image/png;base64,{_PNG_1X1_B64}"
#: Lo que calcula el cliente: SHA-256 de los BYTES de la imagen, no del string.
_HASH_CLIENTE_OK = hashlib.sha256(base64.b64decode(_PNG_1X1_B64)).hexdigest()


def test_el_hash_de_imagen_es_sobre_los_bytes_no_sobre_el_string() -> None:
    """Es LA razon por la que la comparacion no existia: `sha256_hex` hashea el
    string base64 y el cliente hashea la imagen. Son dos hashes distintos del
    mismo screenshot, y ninguno de los dos esta mal — miden cosas distintas."""
    assert sha256_de_imagen(_DATA_URL) == _HASH_CLIENTE_OK
    assert sha256_hex(_DATA_URL) != _HASH_CLIENTE_OK


def test_el_prefijo_data_url_no_cambia_el_hash_de_imagen() -> None:
    """El cliente manda `data:image/jpeg;base64,...` pero hashea solo la imagen.
    Si el servidor no sacara el prefijo antes de decodificar, no coincidiria
    nunca."""
    assert sha256_de_imagen(_DATA_URL) == sha256_de_imagen(_PNG_1X1_B64)


def test_hash_de_imagen_sin_screenshot_es_none() -> None:
    assert sha256_de_imagen(None) is None
    assert sha256_de_imagen("") is None


def test_hash_de_imagen_con_base64_roto_es_none() -> None:
    """Un base64 invalido no puede tumbar la ingesta: devuelve None y el veredicto
    queda 'no_verificable'."""
    assert sha256_de_imagen("data:image/png;base64,esto-no-es-base64-@@@") is None


def test_veredicto_coincide_cuando_el_cliente_dice_la_verdad() -> None:
    assert verificar_custodia_cliente(_DATA_URL, _HASH_CLIENTE_OK) == "coincide"


def test_veredicto_discrepancia_cuando_el_hash_no_corresponde() -> None:
    assert verificar_custodia_cliente(_DATA_URL, "0" * 64) == "discrepancia"


def test_veredicto_no_verificable_sin_hash_del_cliente() -> None:
    """Cliente viejo, o WebCrypto no disponible: no hay nada que comparar. NO es
    una discrepancia — decir que lo es seria acusar por una carencia tecnica."""
    assert verificar_custodia_cliente(_DATA_URL, None) == "no_verificable"


def test_veredicto_no_verificable_sin_screenshot() -> None:
    assert verificar_custodia_cliente(None, _HASH_CLIENTE_OK) == "no_verificable"


def test_veredicto_no_verificable_con_screenshot_ilegible() -> None:
    assert verificar_custodia_cliente("no-es-base64-@@@", _HASH_CLIENTE_OK) == "no_verificable"


def test_la_comparacion_no_distingue_mayusculas() -> None:
    """El hex del cliente puede venir en mayusculas segun la implementacion de
    WebCrypto que use; eso no es una manipulacion."""
    assert verificar_custodia_cliente(_DATA_URL, _HASH_CLIENTE_OK.upper()) == "coincide"
