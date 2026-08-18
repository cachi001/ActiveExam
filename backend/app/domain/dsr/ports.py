"""Puertos del DSR (c-17 activeexam).

Hexagonal: dominio define contratos, infrastructure los implementa contra
activeexam DB.
"""

from __future__ import annotations

from typing import Protocol


class UserDsrRepository(Protocol):
    """Operaciones sobre el usuario y sus datos asociados (activeexam)."""

    async def get_user(self, usuario_id: str) -> dict | None: ...

    async def update_user_fields(
        self,
        usuario_id: str,
        *,
        email: str | None,
        nombre: str | None,
        apellido: str | None,
    ) -> None: ...

    async def list_sessions_for_user(self, usuario_id: str) -> list[str]:
        """Lista IDs de proctoring_session asociadas al usuario.

        ActiveExam no tiene tabla `asignacion` ni FK directa entre usuario y
        proctoring_session — devuelve lista vacia o IDs si existe alguna
        relacion (e.g. via username o columna que se agregue en
        futuro). El servicio debe degradar gracefully si esta lista es vacia.
        """
        ...

    async def delete_session(self, session_id: str) -> None: ...

    async def delete_embeddings(self, usuario_id: str) -> int:
        """Devuelve filas borradas."""
        ...

    async def delete_fotos(self, usuario_id: str) -> int: ...

    async def delete_consent_perfil(self, usuario_id: str) -> int:
        """Purga el consentimiento de perfil del usuario (eliminacion al egreso,
        Ley 25.326). Devuelve filas borradas. Degrada a 0 si la tabla no existe."""
        ...

    async def anonymize_user(self, usuario_id: str) -> None:
        """Anonimiza el usuario (sustituye PII por seudonimo irreversible).

        ActiveExam: setea `eliminado_en = now()`, blanquea email/nombre/apellido,
        conserva username como seudonimo (es opaco, no es PII directa).
        """
        ...


class DsrAuditor(Protocol):
    """Asienta cada operacion DSR en el audit log con proposito declarado."""

    async def log_dsr(
        self, usuario_id: str, *, actor: str, tipo: str, proposito: str
    ) -> None: ...
