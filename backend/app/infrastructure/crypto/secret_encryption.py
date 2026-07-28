"""Cifrado at-rest de secretos operativos guardados en la base (Fernet).

Hoy lo usa la credencial de servicio de Moodle (token de Web Services). Se separa
de ``EvidenceCipher`` a proposito: ese tiene fallback a texto plano para poder
seguir leyendo evidencia historica sin cifrar. Un SECRETO no puede tener ese
fallback — si el valor guardado no es un token Fernet valido, es un error, no un
"legacy en claro" que se devuelve alegremente.

La clave es la misma ``EMBEDDING_ENCRYPTION_KEY`` del despliegue: un unico secreto
raiz inyectado por entorno, nunca en codigo ni en la imagen.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


class SecretCipherError(Exception):
    """Error irrecuperable al cifrar/descifrar un secreto almacenado."""


class SecretCipher:
    """Cifra/descifra secretos operativos con Fernet.

    Args:
        key: clave Fernet (32 bytes base64-urlsafe).
    """

    def __init__(self, *, key: str) -> None:
        if not key:
            raise SecretCipherError(
                "Clave de cifrado ausente. Inyectala por env var "
                "(EMBEDDING_ENCRYPTION_KEY). NUNCA en el codigo ni en la imagen."
            )
        try:
            self._fernet = Fernet(key.encode())
        except Exception as exc:  # noqa: BLE001
            raise SecretCipherError(
                f"Clave de cifrado invalida (Fernet 32 bytes base64-urlsafe): {exc}"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        """Cifra un secreto. Cadena vacia → error: no se guarda un secreto vacio."""
        if not plaintext:
            raise SecretCipherError("No se puede cifrar un secreto vacio.")
        try:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            raise SecretCipherError(f"Error al cifrar el secreto: {exc}") from exc

    def decrypt(self, stored: str | None) -> str | None:
        """Descifra el valor almacenado. None/vacio → None.

        A diferencia de la evidencia, NO hay fallback a texto plano: si el valor no
        descifra, se eleva. Devolver el dato crudo podria filtrar basura como si
        fuera un token valido, y un token corrupto tiene que fallar ruidosamente."""
        if not stored:
            return None
        try:
            return self._fernet.decrypt(stored.encode("ascii")).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise SecretCipherError(
                "El secreto guardado no se pudo descifrar con la clave actual "
                "(¿rotaron EMBEDDING_ENCRYPTION_KEY sin re-cifrar?)."
            ) from exc


def pista_de_secreto(plaintext: str, *, ultimos: int = 4) -> str:
    """Ultimos ``ultimos`` caracteres del secreto, para que el admin lo reconozca.

    No permite reconstruirlo: un token de Moodle es un hash de 32 caracteres."""
    return plaintext[-ultimos:] if len(plaintext) > ultimos else "*" * len(plaintext)
