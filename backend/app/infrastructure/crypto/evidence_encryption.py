"""Cifrado at-rest de la evidencia sensible (screenshots) del proctoring (C-72 §deploy).

El screenshot de un evento muestra la cara del alumno y su entorno: DATO PERSONAL
SENSIBLE (Ley 25.326, regla dura #7). Antes se guardaba como base64 EN CLARO en la
columna ``screenshot_b64``. Este servicio lo cifra at-rest con Fernet (AES-128-CBC +
HMAC-SHA256) antes de persistir, y lo descifra solo en el camino de lectura del
expediente (server-side, en memoria).

Reusa la MISMA clave maestra que el embedding (``EMBEDDING_ENCRYPTION_KEY``): es la
clave de "dato sensible at-rest" del despliegue activeexam. Inyectada desde env var / Vault;
NUNCA hardcodeada. Ver [[embedding_encryption]] para el patrón espejo.

FALLBACK LEGACY: los eventos escritos ANTES de este cambio están en claro. ``decrypt``
detecta ese caso (no es un token Fernet válido) y devuelve el valor tal cual — así el
expediente viejo se sigue leyendo sin migración de datos. Los eventos NUEVOS quedan
cifrados. Una migración de re-cifrado del histórico es opcional y aparte.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken


class EvidenceCipherError(Exception):
    """Error irrecuperable al cifrar la evidencia."""


class EvidenceCipher:
    """Cifra/descifra strings de evidencia (screenshot base64) con Fernet.

    Args:
        key: clave Fernet (32 bytes base64-urlsafe). En el activeexam se pasa la misma
            ``settings.embedding_encryption_key``.
    """

    #: Prefijo de todo token Fernet v1 ("gAAAAA..."). Se usa como heurística barata
    #: para NO intentar descifrar valores legacy en claro (que no empiezan así).
    _FERNET_PREFIX = "gA"

    def __init__(self, *, key: str) -> None:
        if not key:
            raise EvidenceCipherError(
                "Clave de cifrado de evidencia ausente. Inyectala por env var "
                "(la misma EMBEDDING_ENCRYPTION_KEY). NUNCA en el código ni la imagen."
            )
        try:
            self._fernet = Fernet(key.encode())
        except Exception as exc:  # noqa: BLE001
            raise EvidenceCipherError(
                f"Clave de cifrado inválida (Fernet 32 bytes base64-urlsafe): {exc}"
            ) from exc

    def encrypt_bytes(self, plaintext: bytes | None) -> bytes | None:
        """Cifra BYTES y devuelve el token Fernet sin su base64 externo (c-78).

        Fernet siempre devuelve su token en base64 urlsafe. Guardarlo tal cual en
        una columna `bytea` seria pagar de nuevo el 33% de expansion que la
        columna binaria vino justamente a sacar: medido, 113.420 bytes contra
        85.065 para la misma captura. Se le saca ese base64 externo y se guarda el
        token crudo; `decrypt_bytes` se lo vuelve a poner antes de descifrar, asi
        que es exactamente el mismo token, solo que sin envoltorio.
        """
        if plaintext is None:
            return None
        try:
            return base64.urlsafe_b64decode(self._fernet.encrypt(plaintext))
        except Exception as exc:  # noqa: BLE001
            raise EvidenceCipherError(f"Error al cifrar la evidencia: {exc}") from exc

    def decrypt_bytes(self, stored: bytes | None) -> bytes | None:
        """Inverso de ``encrypt_bytes``. None → None.

        A diferencia de ``decrypt``, NO tiene fallback legacy: la columna binaria
        nacio con este change, asi que todo lo que hay ahi esta cifrado. Si el
        token no es valido es un problema real y tiene que doler.
        """
        if stored is None:
            return None
        try:
            return self._fernet.decrypt(base64.urlsafe_b64encode(stored))
        except Exception as exc:  # noqa: BLE001
            raise EvidenceCipherError(f"Error al descifrar la evidencia: {exc}") from exc

    def encrypt(self, plaintext: str | None) -> str | None:
        """Cifra un string (screenshot base64). None → None (evento sin captura)."""
        if plaintext is None:
            return None
        try:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            raise EvidenceCipherError(f"Error al cifrar la evidencia: {exc}") from exc

    def decrypt(self, stored: str | None) -> str | None:
        """Descifra el valor almacenado. None → None.

        Fallback legacy: si ``stored`` no es un token Fernet válido (evento viejo en
        claro), se devuelve tal cual — el expediente histórico se sigue leyendo.
        """
        if stored is None:
            return None
        if not stored.startswith(self._FERNET_PREFIX):
            return stored  # legacy en claro
        try:
            return self._fernet.decrypt(stored.encode("ascii")).decode("utf-8")
        except InvalidToken:
            # No era un token nuestro (o clave rotada sin re-cifrar): trato como legacy.
            return stored
        except Exception as exc:  # noqa: BLE001
            raise EvidenceCipherError(f"Error al descifrar la evidencia: {exc}") from exc
