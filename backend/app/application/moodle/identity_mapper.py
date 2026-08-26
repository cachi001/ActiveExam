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
    1. Buscar por idnumber (campo username del alumno).
    2. Si no hay match, buscar por email.
    3. Si no hay match único → IdentityResolutionError.
    """

    def __init__(self, moodle_client: MoodleRestClient) -> None:
        self._client = moodle_client

    async def resolve(
        self,
        *,
        idnumber: str,
        email: str,
        courseid: int | None = None,
        ws_token: str | None = None,
        # c-78: el campus contra el que el docente conecto su cuenta. Va junto al
        # token: usar la URL institucional con el token del docente dejaba la URL
        # vacia y el envio moria sin decir por que.
        base_url: str | None = None,
        # c-78: en este campus no hay legajo. El userid de Moodle llega en el
        # launch LTI y es el identificador fuerte; el username es el del campus.
        moodle_userid: int | str | None = None,
        username: str | None = None,
    ) -> int:
        """Devuelve el userid de Moodle. Lanza IdentityResolutionError si no puede.

        DOS CAMINOS (C-73 Fase 2):

        1. Con ``courseid`` Y ``ws_token`` (el token del docente) resuelve entre los
           MATRICULADOS del curso. Es el camino preferido: no necesita credencial
           institucional —que hoy en campustest esta muerta— y el alcance lo impone
           Moodle (un docente no ve cursos donde no da clase).

        2. Sin esos datos cae al camino institucional
           (``core_user_get_users_by_field``). Lo usan la anulacion por fraude y la
           restitucion, que las decide un revisor y van con la credencial de la
           institucion a proposito.

        Args:
            idnumber: el username del alumno (legajo/padrón).
            email: el email institucional del alumno.
            courseid: curso destino en Moodle. Habilita el camino 1.
            ws_token: token del docente. Habilita el camino 1.

        Returns:
            El userid (int) de Moodle del alumno.

        Raises:
            IdentityResolutionError: si no se puede resolver un usuario único.
        """
        if courseid and ws_token:
            try:
                userid = await self._client.lookup_userid_en_curso(
                    courseid=courseid,
                    idnumber=idnumber,
                    email=email,
                    ws_token=ws_token,
                    base_url=base_url,
                    moodle_userid=moodle_userid,
                    username=username,
                )
            except MoodleGradeWriteError as exc:
                raise IdentityResolutionError(
                    f"Error al buscar al alumno entre los matriculados del curso "
                    f"{courseid}: {exc}"
                ) from exc

            if userid is not None:
                return userid

            # NO se cae al camino institucional. No seria un rescate: escribir la nota
            # de alguien que no esta matriculado falla igual del otro lado. Caer solo
            # cambiaria un diagnostico accionable por un error opaco de Moodle, y
            # reintroduciria la dependencia del token institucional que este camino
            # vino a eliminar.
            raise IdentityResolutionError(
                f"El alumno (idnumber={idnumber!r}, email={email!r}) no esta "
                f"matriculado en el curso {courseid} del campus. Verificá la "
                "matriculación en Moodle o el destino configurado en el examen."
            )

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
