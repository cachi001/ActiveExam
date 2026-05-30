"""Puerto + adaptador del bucket WORM (Object Lock modo Compliance) — C-12 (D4, DD-07).

El binario de evidencia se deposita en un bucket con **Object Lock en modo
Compliance**: inmutable durante la retencion, sin que NADIE (ni la cuenta root)
pueda modificarlo o borrarlo antes del ``retain-until`` (RN-CC-06). El modo
Compliance (no Governance) cierra el vector de repudio por override privilegiado.

El SDK real (boto3/minio) aplica el ``ObjectLockMode='COMPLIANCE'`` y el
``ObjectLockRetainUntilDate`` en produccion; aqui se define el PUERTO y un adaptador
que delega en callables inyectados, de modo que el dominio/aplicacion no se aten al
SDK y los tests ejerzan el contrato sin red. El worker tambien re-descarga el binario
por este puerto (3.a verificacion de hash).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

# Modo de Object Lock exigido por el dominio: Compliance, NUNCA Governance (D4).
OBJECT_LOCK_MODE = "COMPLIANCE"


@dataclass(frozen=True, slots=True)
class WormObject:
    """Referencia a un objeto depositado en el bucket WORM."""

    object_key: str
    uri: str
    retain_until: str
    mode: str = OBJECT_LOCK_MODE


class WormStoragePort(ABC):
    """Puerto del storage WORM (Object Lock Compliance)."""

    @abstractmethod
    def deposit(
        self, *, object_key: str, data: bytes, retain_until: str
    ) -> WormObject:
        """Deposita ``data`` con Object Lock Compliance hasta ``retain_until``."""

    @abstractmethod
    def fetch(self, *, object_key: str) -> bytes:
        """Re-descarga el binario (worker etapa 3): para la 3.a verificacion de hash."""


class ComplianceWormStorage(WormStoragePort):
    """Adaptador WORM que delega en el SDK de storage (Object Lock Compliance).

    ``put_fn`` envuelve ``put_object(..., ObjectLockMode='COMPLIANCE',
    ObjectLockRetainUntilDate=retain_until)``; ``get_fn`` envuelve ``get_object``.
    El modo se FIJA a Compliance: este adaptador rechaza cualquier intento de
    configurarlo en Governance (D4)."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        put_fn: Callable[[str, bytes, str], None],
        get_fn: Callable[[str], bytes],
        mode: str = OBJECT_LOCK_MODE,
    ) -> None:
        if mode != OBJECT_LOCK_MODE:
            raise ValueError(
                "el bucket de evidencia DEBE usar Object Lock modo Compliance, "
                f"no '{mode}' (D4/RN-CC-06)"
            )
        self._endpoint = endpoint.rstrip("/")
        self._bucket = bucket
        self._put = put_fn
        self._get = get_fn

    def deposit(
        self, *, object_key: str, data: bytes, retain_until: str
    ) -> WormObject:
        self._put(object_key, data, retain_until)
        uri = f"{self._endpoint}/{self._bucket}/{object_key}"
        return WormObject(object_key=object_key, uri=uri, retain_until=retain_until)

    def fetch(self, *, object_key: str) -> bytes:
        return self._get(object_key)
