"""Puertos PUROS de la verificacion biometrica (C-09, Hexagonal/DD-17).

El motor de vision (MediaPipe en cliente, ONNX self-hosted server-side) y el KMS
viven en INFRAESTRUCTURA. La aplicacion depende de estos puertos, nunca de un
adaptador concreto (DD-17: motor abstraido detras de interfaz):

- ``VisionEnginePort``: re-inferencia server-side del clip (RN-GLB-01) -> produce
  el embedding y la evidencia de liveness desde el CLIP EXACTO, sin confiar en el
  veredicto del cliente.
- ``ReferenceEmbeddingPort``: lee el embedding de REFERENCIA cifrado (C-07) y lo
  descifra via KMS para la comparacion server-side (D5); el dominio recibe el
  vector en claro solo el tiempo de la comparacion, nunca el ciphertext ni la clave.
- ``SecretProviderPort``: entrega el secreto maestro (Vault) del que se deriva la
  clave de sesion rotativa; NUNCA un secreto hardcodeado.

PUREZA (D1): solo ABCs y tipos de dominio; sin SQLAlchemy/FastAPI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.biometrics.liveness import EvidenciaLiveness


class ReinferenciaResultado:
    """Resultado de la re-inferencia server-side sobre el clip (valor de dominio).

    Contiene el embedding recalculado por el backend y la evidencia de liveness
    re-derivada del clip exacto. Es la VERSION CONFIABLE (RN-GLB-01)."""

    __slots__ = ("embedding", "liveness")

    def __init__(self, embedding: tuple[float, ...], liveness: EvidenciaLiveness) -> None:
        self.embedding = embedding
        self.liveness = liveness


class VisionEnginePort(ABC):
    """Puerto del motor de vision server-side (re-inferencia, DD-17, RN-GLB-01)."""

    @abstractmethod
    async def reinferir(self, *, clip_uri: str, clip_hash: str) -> ReinferenciaResultado:
        """Re-infiere sobre el clip EXACTO (embedding + liveness) sin confiar en el
        cliente. ``clip_hash`` permite verificar integridad del clip recuperado."""


class ReferenceEmbeddingPort(ABC):
    """Puerto de lectura del embedding de referencia cifrado (C-07, D5)."""

    @abstractmethod
    async def leer_referencia(
        self, *, user_id: str, exam_id: str
    ) -> tuple[float, ...] | None:
        """Lee y DESCIFRA (via KMS) el embedding de referencia del estudiante.

        Devuelve el vector en claro para la comparacion server-side, o ``None`` si
        no hay referencia (la 1:1 no opera -> via alternativa de C-08). El
        ciphertext y la clave NUNCA salen de infraestructura."""


class SecretProviderPort(ABC):
    """Puerto del secreto maestro de derivacion de claves de sesion (Vault)."""

    @abstractmethod
    async def secreto_maestro(self) -> bytes:
        """Devuelve el secreto maestro inyectado (tmpfs/Vault), NUNCA hardcodeado."""
