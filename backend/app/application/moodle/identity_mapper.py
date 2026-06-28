"""Mapeo de identidad alumno ↔ usuario Moodle (C-69, D9, tarea 7.5-7.6).

D9: idnumber (default) → fallback email.
Sin match único → IdentityResolutionError: NO se envía a un usuario arbitrario.
"""

from __future__ import annotations

from app.infrastructure.moodle.client import MoodleGradeWriteError, MoodleRestClient


class IdentityResolutionError(Exception):
    """No se pudo resolver un usuario Moodle único para el alumno."""


class MoodleIdentityMapper:
    """Resuelve la identidad de un alumno en el usuario Moodle correspondiente.

    Estrategia D9:
    1. Buscar por idnumber (campo id_institucional del alumno).
    2. Si no hay match, buscar por email.
    3. Si no hay match único → IdentityResolutionError.
    """

    def __init__(self, moodle_client: MoodleRestClient) -> None:
        self._client = moodle_client

    async def resolve(self, *, idnumber: str, email: str) -> int:
        """Devuelve el userid de Moodle. Lanza IdentityResolutionError si no puede.

        Args:
            idnumber: el id_institucional del alumno (legajo/padrón).
            email: el email institucional del alumno.

        Returns:
            El userid (int) de Moodle del alumno.

        Raises:
            IdentityResolutionError: si no se puede resolver un usuario único.
        """
        # Intento 1: por idnumber
        if idnumber:
            try:
                userid = await self._client.lookup_userid_by_idnumber(idnumber)
                if userid is not None:
                    return userid
            except MoodleGradeWriteError as exc:
                raise IdentityResolutionError(
                    f"Error al buscar por idnumber={idnumber!r}: {exc}"
                ) from exc

        # Intento 2: fallback por email
        if email:
            try:
                userid = await self._client.lookup_userid_by_email(email)
                if userid is not None:
                    return userid
            except MoodleGradeWriteError as exc:
                raise IdentityResolutionError(
                    f"Error al buscar por email={email!r}: {exc}"
                ) from exc

        raise IdentityResolutionError(
            f"No se encontró usuario Moodle para idnumber={idnumber!r} ni email={email!r}"
        )


async def resolve_moodle_userid(
    *,
    moodle_client: MoodleRestClient,
    idnumber: str,
    email: str,
) -> int:
    """Función pública: delega a MoodleIdentityMapper.resolve."""
    mapper = MoodleIdentityMapper(moodle_client=moodle_client)
    return await mapper.resolve(idnumber=idnumber, email=email)
