"""Puertos (Protocols) que el motor de retencion necesita.

Hexagonal: el dominio define los contratos, infraestructura los implementa.
En slim las implementaciones son SQL contra tablas existentes en la
migracion slim head (0012); cuando llegue c-67/c-69, se agregan
implementaciones nuevas SIN tocar dominio ni application.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class SessionAgingRepository(Protocol):
    """Lista ids de sesiones cuya ``creada_en`` es anterior a un cutoff."""

    async def find_older_than(self, cutoff: datetime) -> list[str]: ...


class UserEgressRepository(Protocol):
    """Lista ids de usuarios que egresaron (``usuario.eliminado_en`` no nulo)
    y todavia tienen biometria persistida (foto_referencia / embedding_referencia)
    vigente. La query solo devuelve usuarios con biometria asociada para
    evitar trabajo inutil."""

    async def find_egressed_with_biometry(self) -> list[str]: ...


class SessionDeleter(Protocol):
    """Borra una sesion por id. El cascade DELETE (FK ondelete CASCADE) ya
    elimina los eventos asociados — no hace falta borrarlos manualmente."""

    async def delete(self, session_id: str) -> None: ...


class EmbeddingDeleter(Protocol):
    """Borra todos los embeddings de referencia de un usuario."""

    async def delete_for_user(self, usuario_id: str) -> int:
        """Devuelve la cantidad de filas borradas (>= 0)."""
        ...


class FotoDeleter(Protocol):
    """Borra todas las fotos de referencia de un usuario.

    Slim: borra solo la fila en DB. La purga del binario en MinIO/S3 es
    responsabilidad de un job aparte (Object Lock difiere la eliminacion
    fisica — c-67 se ocupa cuando llegue WORM real).
    """

    async def delete_for_user(self, usuario_id: str) -> int: ...


class RetentionAuditor(Protocol):
    """Asienta en el audit log cada accion del motor de retencion.

    Cada metodo escribe una entrada inmutable con propopsito declarado, sin
    re-exponer PII. La cadena de hash se mantiene a nivel de motor SQL (no
    en la aplicacion).
    """

    async def log_session_deleted(
        self, session_id: str, *, actor: str, reason: str
    ) -> None: ...

    async def log_hold_deferred(
        self, session_id: str, *, actor: str
    ) -> None: ...

    async def log_biometric_egress(
        self,
        usuario_id: str,
        *,
        actor: str,
        embeddings_deleted: int,
        fotos_deleted: int,
    ) -> None: ...
