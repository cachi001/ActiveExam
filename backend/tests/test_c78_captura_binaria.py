"""Almacenamiento BINARIO de la captura (c-78, task 16.4). Parte pura.

## Por que

Medido contra Postgres real (`pg_column_size`), una captura de 85 KB ocupa HOY
**151.224 bytes** en `proctoring_event.screenshot_b64`. La cuenta es una doble
expansion base64:

    imagen 85.000 -> data URL base64 113.359 (133%) -> token Fernet 151.224 (178%)

Fernet devuelve su token en base64, asi que el cifrado vuelve a inflar lo que ya
estaba inflado. Y TOAST no lo salva: lo cifrado es incompresible, Postgres lo
guarda tal cual.

Guardando el token Fernet CRUDO (sin su base64 externo) sobre los BYTES de la
imagen, la misma captura ocupa **85.065 bytes**: 44% menos. Un examen de 100
alumnos pasa de 577 MB a 325 MB en una base de 1024 MB.

## La propiedad que NO se puede romper

`screenshot_sha256` se calcula sobre el string base64 tal como llega del cliente,
y `verify-chain` lo recalcula para peritar la evidencia. Si el ida y vuelta
binario no devuelve EXACTAMENTE el mismo string, ese hash deja de verificar y
toda la evidencia queda marcada como manipulada.

Por eso el test central de este modulo es el round-trip exacto, byte a byte.
"""

from __future__ import annotations

import base64
import os

from app.application.proctoring.captura_almacenada import (
    reconstruir_data_url,
    separar_data_url,
)
from app.application.proctoring.integridad import sha256_de_imagen, sha256_hex

_IMG = base64.b64encode(os.urandom(512)).decode("ascii")
_DATA_URL = f"data:image/jpeg;base64,{_IMG}"


def test_el_ida_y_vuelta_devuelve_EXACTAMENTE_el_mismo_string() -> None:
    """La propiedad que sostiene todo: si esto falla, `screenshot_sha256` deja de
    verificar y verify-chain marca toda la evidencia como manipulada."""
    prefijo, binario = separar_data_url(_DATA_URL)
    assert reconstruir_data_url(prefijo, binario) == _DATA_URL


def test_el_hash_registrado_no_cambia_al_pasar_por_binario() -> None:
    """Dicho sobre el hash mismo, que es lo que el perito compara."""
    prefijo, binario = separar_data_url(_DATA_URL)
    assert sha256_hex(reconstruir_data_url(prefijo, binario)) == sha256_hex(_DATA_URL)


def test_el_hash_de_custodia_tampoco_cambia() -> None:
    """El de custodia ya era independiente del formato (hashea la imagen), pero
    conviene dejarlo fijado: es el que sobrevive a 16.5 (captura binaria por la
    red), donde el string base64 deja de existir."""
    prefijo, binario = separar_data_url(_DATA_URL)
    assert sha256_de_imagen(reconstruir_data_url(prefijo, binario)) == sha256_de_imagen(
        _DATA_URL
    )


def test_separar_devuelve_los_BYTES_de_la_imagen_no_el_base64() -> None:
    _, binario = separar_data_url(_DATA_URL)
    assert binario == base64.b64decode(_IMG)


def test_base64_pelado_sin_data_url_tambien_da_la_vuelta() -> None:
    """No todo lo que llega trae el prefijo `data:`; el round-trip tiene que valer
    igual o esos eventos quedarian con el hash roto."""
    prefijo, binario = separar_data_url(_IMG)
    assert prefijo is None
    assert reconstruir_data_url(prefijo, binario) == _IMG


def test_sin_captura_no_hay_nada_que_guardar() -> None:
    assert separar_data_url(None) == (None, None)
    assert separar_data_url("") == (None, None)
    assert reconstruir_data_url(None, None) is None


def test_base64_ilegible_no_revienta_la_ingesta() -> None:
    """Un payload roto no puede tumbar el evento: se degrada a "sin binario" y el
    evento entra igual (L2.5: el registro de que pasó algo vale por si mismo)."""
    assert separar_data_url("data:image/png;base64,@@@no-es-base64@@@") == (None, None)


def test_conserva_el_prefijo_exacto_no_solo_el_mime() -> None:
    """Se guarda el prefijo tal cual vino (no un mime normalizado) justamente para
    que la reconstruccion sea identica aunque el cliente cambie el formato."""
    url = f"data:image/webp;charset=utf-8;base64,{_IMG}"
    prefijo, binario = separar_data_url(url)
    assert prefijo == "data:image/webp;charset=utf-8;base64"
    assert reconstruir_data_url(prefijo, binario) == url
