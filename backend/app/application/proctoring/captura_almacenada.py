"""Conversion entre el data URL que manda el cliente y el binario que se guarda.

## Por que existe (c-78, task 16.4)

Medido contra Postgres real (`pg_column_size`), una captura de 85 KB ocupaba
**151.224 bytes** en `proctoring_event.screenshot_b64`. Es una doble expansion
base64:

    imagen 85.000 -> data URL base64 113.359 (133%) -> token Fernet 151.224 (178%)

Fernet devuelve su token en base64, asi que el cifrado vuelve a inflar lo que ya
venia inflado. Y TOAST no lo salva: lo cifrado es incompresible y Postgres lo
guarda tal cual. Guardando el token Fernet CRUDO sobre los BYTES de la imagen, la
misma captura ocupa **85.065 bytes**: 44% menos. Un examen de 100 alumnos pasa de
577 MB a 325 MB en una base de 1024 MB.

## La propiedad que este modulo NO puede romper

`screenshot_sha256` se calcula sobre el string base64 tal como llega del cliente,
y `verify-chain` lo recalcula para peritar la evidencia. Si el ida y vuelta no
devuelve EXACTAMENTE el mismo string, ese hash deja de verificar y toda la
evidencia queda marcada como manipulada.

Por eso se guarda el PREFIJO COMPLETO tal cual vino (`data:image/jpeg;base64`) y
no un mime normalizado: la reconstruccion tiene que ser byte a byte, aunque el
cliente cambie el formato de la captura mas adelante.
"""

from __future__ import annotations

import base64
import binascii
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.crypto.evidence_encryption import EvidenceCipher


def separar_data_url(screenshot_base64: str | None) -> tuple[str | None, bytes | None]:
    """Parte el data URL en (prefijo, bytes de la imagen).

    - ``"data:image/jpeg;base64,AAAA"`` -> ``("data:image/jpeg;base64", b"...")``
    - ``"AAAA"`` (base64 pelado, sin prefijo) -> ``(None, b"...")``
    - sin captura, o base64 ilegible -> ``(None, None)``

    Un base64 roto NO levanta: devuelve ``(None, None)`` y el evento se persiste
    igual sin binario. El registro de que algo pasó vale por si mismo (L2.5).
    """
    if not screenshot_base64:
        return (None, None)
    prefijo, separador, crudo = screenshot_base64.rpartition(",")
    if not separador:
        prefijo, crudo = None, screenshot_base64
    try:
        return (prefijo or None, base64.b64decode(crudo, validate=True))
    except (binascii.Error, ValueError):
        return (None, None)


def reconstruir_data_url(prefijo: str | None, binario: bytes | None) -> str | None:
    """Inverso exacto de ``separar_data_url``. Sin binario devuelve None."""
    if binario is None:
        return None
    codificado = base64.b64encode(binario).decode("ascii")
    return f"{prefijo},{codificado}" if prefijo else codificado


def leer_captura(
    *,
    screenshot_bin: bytes | None,
    screenshot_prefijo: str | None,
    screenshot_b64_legacy: str | None,
    cipher: "EvidenceCipher | None",
) -> str | None:
    """Devuelve la captura como data URL, venga de donde venga.

    UNICO camino de lectura, para que ninguna pantalla resuelva por su cuenta de
    que columna sacarla ni si hay que descifrar. Tres casos, en este orden:

      1. Fila NUEVA (desde la migracion 0097): esta en ``screenshot_bin``, cifrada
         y en binario. Se descifra y se reconstruye el data URL exacto.
      2. Fila LEGACY: esta en ``screenshot_b64``, cifrada o en claro segun cuando
         se escribio. ``cipher.decrypt`` ya devuelve tal cual lo que no es un token
         Fernet, asi que el mismo camino cubre las dos.
      3. Sin captura (evento de contexto, o purgada por retencion): None.

    Sin ``cipher`` devuelve lo almacenado sin descifrar: es el caso de los tests y
    de un despliegue sin clave, donde la evidencia esta en claro.
    """
    if screenshot_bin is not None:
        binario = (
            cipher.decrypt_bytes(screenshot_bin) if cipher is not None else screenshot_bin
        )
        return reconstruir_data_url(screenshot_prefijo, binario)
    if screenshot_b64_legacy is not None:
        return (
            cipher.decrypt(screenshot_b64_legacy)
            if cipher is not None
            else screenshot_b64_legacy
        )
    return None
