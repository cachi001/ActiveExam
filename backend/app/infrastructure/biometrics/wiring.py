"""Cableado del subsistema de biometria (C-09): motor de vision + KMS + secreto.

Construye los adaptadores concretos de los puertos de C-09 a partir de la config:
- ``VisionEnginePort``: motor de vision server-side (re-inferencia). El
  inferenciador concreto (MediaPipe Tasks / ONNX) se inyecta en produccion; si no
  esta disponible, se levanta para que ``create_app`` deje el subsistema en None.
- ``KmsCipher``: cifrado at-rest del embedding (Vault Transit / KMS). El cliente
  cripto se inyecta en produccion.
- ``SecretProviderPort``: lee el secreto maestro del entorno/Vault (tmpfs). NUNCA
  hardcodeado: si la env var no esta, el provider falla al usarse.

Este modulo NO trae dependencias de vision/cripto a import-time: solo cablea
contratos. La pieza concreta se conecta en el deploy (DD-17, `08` Secretos).
"""

from __future__ import annotations

from app.config import Settings
from app.domain.biometrics.ports import (
    SecretProviderPort,
    VisionEnginePort,
)
from app.infrastructure.biometrics.crypto import (
    InjectedKmsCipher,
    KmsCipher,
    VaultSecretProvider,
)


def build_biometrics_subsystem(
    settings: Settings,
) -> tuple[VisionEnginePort, KmsCipher, SecretProviderPort]:
    """Construye (vision_engine, kms_cipher, secret_provider) desde la config.

    En el MVP sin la libreria de vision real ni el cliente KMS cableado, esta
    construccion se hace con los hooks de produccion inyectados por el deploy. Si
    falta cualquiera, lanza para que ``create_app`` deje el subsistema en None y
    las dependencias devuelvan 500 explicito (twelve-factor)."""
    # El inferenciador de vision y el cliente KMS reales los provee el deploy
    # (DD-17). Hasta entonces, esta funcion lanza NotImplementedError para que el
    # app.state quede en None sin romper el arranque (los tests inyectan overrides).
    raise NotImplementedError(
        "El motor de vision (DD-17) y el cliente KMS/Vault se cablean en el deploy. "
        "Los tests inyectan adaptadores en memoria por override de dependencia."
    )


def build_secret_provider_from_env(secreto_maestro: bytes) -> SecretProviderPort:
    """Helper: provider del secreto maestro a partir de bytes ya leidos (Vault)."""
    return VaultSecretProvider(lambda: secreto_maestro)


def build_kms_cipher(encryptor, decryptor) -> KmsCipher:
    """Helper: arma el ``KmsCipher`` desde los callables del cliente KMS real."""
    return InjectedKmsCipher(encryptor=encryptor, decryptor=decryptor)
