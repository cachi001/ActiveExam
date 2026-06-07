"""Cifrado at-rest del embedding biometrico de referencia (C-56, D2).

El embedding 128-d es DATO SENSIBLE (Ley 25.326, IN-04): se cifra at-rest con
Fernet (AES-128-CBC + HMAC-SHA256) antes de persistirse en la base de datos.
El ciphertext se almacena en la columna ``embedding_cifrado`` (TEXT) de la
tabla ``embedding_referencia``.

Fernet provee cifrado autenticado (integridad + confidencialidad) con una API
simple y sin necesidad de gestionar IV por separado. La clave maestra es
rotable: ante un compromiso, re-encriptar todos los embeddings con la nueva
clave. La clave se inyecta desde Vault / env var; NUNCA se hardcodea.

RESPONSABILIDAD: este modulo SOLO cifra/descifra. La gestion del ciclo de vida
de la clave (rotacion, inyeccion desde Vault) es responsabilidad del entorno.
"""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EmbeddingEncryptionError(Exception):
    """Error al cifrar o descifrar el embedding."""


class ConfigurationError(Exception):
    """La clave de cifrado no esta configurada."""


class EmbeddingEncryptionService:
    """Servicio de cifrado at-rest del embedding biometrico de referencia.

    Encapsula el ciclo encrypt/decrypt con Fernet. La clave maestra se lee
    de ``settings.EMBEDDING_ENCRYPTION_KEY`` al instanciar; si no esta
    configurada, lanza ``ConfigurationError`` inmediatamente (sin default
    inseguro, regla dura del proyecto).

    Uso tipico:
        service = EmbeddingEncryptionService()
        token = service.encrypt([0.1, 0.2, ..., 0.128])   # 128 floats
        vector = service.decrypt(token)                    # round-trip
    """

    def __init__(self, *, _key: str | None = None) -> None:
        """Inicializa el servicio de cifrado con la clave Fernet.

        Args:
            _key: clave Fernet en string. Si se provee, se usa directamente
                  (modo slim, c-57: la clave viene de SlimSettings sin cargar
                  la config del full). Si es None, se lee de ``get_settings()``
                  del full (modo produccion completo, retrocompatible).
        """
        if _key is not None:
            # Modo slim: clave inyectada directamente (sin cargar Settings del full).
            clave = _key
        else:
            # Modo full: leer de la config completa.
            settings = get_settings()
            clave = getattr(settings, "embedding_encryption_key", None)

        if not clave:
            raise ConfigurationError(
                "EMBEDDING_ENCRYPTION_KEY no esta configurada. "
                "Inyectala desde Vault / env var (32 bytes en base64-urlsafe). "
                "NUNCA incluyas la clave real en el codigo ni en la imagen Docker."
            )
        try:
            self._fernet = Fernet(clave.encode())
        except Exception as exc:
            raise ConfigurationError(
                f"EMBEDDING_ENCRYPTION_KEY invalida (debe ser 32 bytes base64-urlsafe "
                f"generados con Fernet.generate_key()): {exc}"
            ) from exc

    def encrypt(self, embedding: list[float]) -> str:
        """Cifra el embedding 128-d y devuelve el Fernet token (base64-urlsafe).

        El embedding se serializa como JSON antes de cifrar. El ciphertext es
        un string opaco (Fernet token) que se puede persistir en TEXT.

        Args:
            embedding: lista de 128 floats (descriptor facial).

        Returns:
            Fernet token (str, base64-urlsafe). Nunca es el embedding en claro.

        Raises:
            EmbeddingEncryptionError: si el cifrado falla por algun motivo.
        """
        try:
            plaintext = json.dumps(embedding).encode("utf-8")
            ciphertext_bytes = self._fernet.encrypt(plaintext)
            return ciphertext_bytes.decode("ascii")
        except Exception as exc:
            raise EmbeddingEncryptionError(f"Error al cifrar el embedding: {exc}") from exc

    def decrypt(self, ciphertext: str) -> list[float]:
        """Descifra el Fernet token y devuelve el vector de floats original.

        Args:
            ciphertext: Fernet token (str) almacenado en ``embedding_cifrado``.

        Returns:
            Lista de floats (el embedding original cifrado en ``encrypt``).

        Raises:
            EmbeddingEncryptionError: si el ciphertext es invalido o la clave
                no coincide (tampered / rotacion de clave sin re-encripcion).
        """
        try:
            plaintext_bytes = self._fernet.decrypt(ciphertext.encode("ascii"))
            return json.loads(plaintext_bytes.decode("utf-8"))
        except InvalidToken as exc:
            raise EmbeddingEncryptionError(
                "Ciphertext invalido o clave incorrecta. "
                "Si se roto la clave, re-encriptar todos los embeddings primero."
            ) from exc
        except Exception as exc:
            raise EmbeddingEncryptionError(f"Error al descifrar el embedding: {exc}") from exc
