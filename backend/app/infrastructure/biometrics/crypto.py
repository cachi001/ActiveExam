"""Cifrado at-rest del embedding y proveedor de secreto maestro (C-09, D5).

El embedding es dato SENSIBLE (IN-04, Ley 25.326): se cifra at-rest. El cifrado
real lo hace un KMS (Vault Transit / KMS cloud); este modulo define el PUERTO
``KmsCipher`` y un adaptador de produccion que delega en un cifrador inyectado.
Asi el dominio nunca ve la clave y el adaptador no se ata a un SDK concreto.

NUNCA se hardcodea una clave: el secreto maestro y las claves de cifrado se
inyectan en runtime desde Vault en tmpfs efimero (`08` Gestion de secretos).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.domain.biometrics.ports import SecretProviderPort


class KmsCipher(ABC):
    """Puerto de cifrado simetrico at-rest (KMS). Cifra/descifra bytes opacos."""

    @abstractmethod
    def cifrar(self, plaintext: bytes) -> bytes:
        """Devuelve el ciphertext del ``plaintext`` (clave gestionada por el KMS)."""

    @abstractmethod
    def descifrar(self, ciphertext: bytes) -> bytes:
        """Devuelve el plaintext del ``ciphertext`` (clave gestionada por el KMS)."""


class InjectedKmsCipher(KmsCipher):
    """Adaptador KMS que delega en callables inyectados (SDK real en produccion).

    Los callables ``encryptor``/``decryptor`` envuelven la API del KMS (Vault
    Transit / AWS KMS). Nunca reciben la clave en claro en el codigo de la app: el
    KMS la custodia; aqui solo se invocan las operaciones."""

    def __init__(
        self,
        *,
        encryptor: Callable[[bytes], bytes],
        decryptor: Callable[[bytes], bytes],
    ) -> None:
        self._encryptor = encryptor
        self._decryptor = decryptor

    def cifrar(self, plaintext: bytes) -> bytes:
        return self._encryptor(plaintext)

    def descifrar(self, ciphertext: bytes) -> bytes:
        return self._decryptor(ciphertext)


class VaultSecretProvider(SecretProviderPort):
    """Proveedor del secreto maestro de derivacion de claves de sesion (Vault).

    Recibe un callable que lee el secreto del backend de secretos (Vault/tmpfs).
    NUNCA embebe el secreto en codigo: es responsabilidad del entorno inyectarlo."""

    def __init__(self, lector_secreto: Callable[[], bytes]) -> None:
        self._lector = lector_secreto

    async def secreto_maestro(self) -> bytes:
        secreto = self._lector()
        if not secreto:
            raise RuntimeError(
                "secreto maestro vacio: no inyectado por Vault/tmpfs (8 Secretos)"
            )
        return secreto
