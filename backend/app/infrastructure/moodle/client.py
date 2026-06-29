"""Cliente Moodle REST para write-back de nota vía core_grades_update_grades (C-69, D7).

El token se toma de MoodleClientConfig — NUNCA se loguea ni se expone al cliente.
Schema Pydantic extra='forbid'.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class MoodleClientConfig(BaseModel):
    """Config del cliente Moodle REST. extra='forbid' — regla dura de código."""

    model_config = ConfigDict(extra="forbid")

    base_url: str
    ws_token: str
    courseid: int
    cmid: int


class MoodleGradeWriteError(Exception):
    """Fallo en el write-back de la nota a Moodle (red, token inválido, error WS)."""


class MoodleRestClient:
    """Cliente async para la Web Service core_grades_update_grades de Moodle.

    El token nunca se loguea: se usa sólo en el campo wstoken del form-data.
    """

    def __init__(self, config: MoodleClientConfig) -> None:
        self._config = config

    async def write_grade(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None = None,
        cmid: int | None = None,
    ) -> None:
        """Escribe la nota del alumno en Moodle vía core_grades_update_grades.

        D12 (parte B): courseid/cmid son el destino POR EXAMEN. Si se pasan, se usan;
        si son None, se cae al global de config (compat con exámenes sin destino).

        Raises:
            MoodleGradeWriteError: si Moodle devuelve un error, token inválido,
                fallo de red o respuesta HTTP no-2xx.
        """
        url = f"{self._config.base_url.rstrip('/')}/webservice/rest/server.php"

        # Destino: valor por examen si vino; si no, fallback al global de config.
        target_courseid = courseid if courseid is not None else self._config.courseid
        target_cmid = cmid if cmid is not None else self._config.cmid

        # Payload del WS. El token va en wstoken (protocolo Moodle REST WS).
        # NUNCA se loguea ni aparece en campos de audit.
        data = {
            "wstoken": self._config.ws_token,
            "wsfunction": "core_grades_update_grades",
            "moodlewsrestformat": "json",
            "source": "activeexam",
            "courseid": str(target_courseid),
            "component": "mod_assign",
            "activityid": str(target_cmid),
            "itemnumber": "0",
            "grades[0][studentid]": str(moodle_userid),
            "grades[0][grade]": str(round(nota, 2)),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(url, data=data)
        except Exception as exc:
            raise MoodleGradeWriteError(f"Error de red al contactar Moodle: {exc}") from exc

        if response.status_code >= 400:
            raise MoodleGradeWriteError(
                f"Moodle devolvió HTTP {response.status_code}"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise MoodleGradeWriteError(
                f"Respuesta de Moodle no es JSON válido: {exc}"
            ) from exc

        # La WS de Moodle devuelve {"exception": ...} para errores incluso con 200
        if isinstance(body, dict) and "exception" in body:
            errorcode = body.get("errorcode", "unknown")
            message = body.get("message", "")
            raise MoodleGradeWriteError(
                f"Moodle WS error ({errorcode}): {message}"
            )

    async def lookup_userid_by_idnumber(self, idnumber: str) -> int | None:
        """Busca el userid de Moodle dado un idnumber vía core_user_get_users_by_field.

        Devuelve el userid si hay exactamente un match, None si no hay match.
        Raises MoodleGradeWriteError si hay múltiples matches o error de red/WS.
        """
        url = f"{self._config.base_url.rstrip('/')}/webservice/rest/server.php"
        data = {
            "wstoken": self._config.ws_token,
            "wsfunction": "core_user_get_users_by_field",
            "moodlewsrestformat": "json",
            "field": "idnumber",
            "values[0]": idnumber,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(url, data=data)
        except Exception as exc:
            raise MoodleGradeWriteError(f"Error de red buscando usuario: {exc}") from exc

        if response.status_code >= 400:
            raise MoodleGradeWriteError(
                f"Moodle devolvió HTTP {response.status_code} al buscar usuario"
            )

        try:
            body = response.json()
        except Exception as exc:
            raise MoodleGradeWriteError(f"Respuesta JSON inválida: {exc}") from exc

        if isinstance(body, dict) and "exception" in body:
            raise MoodleGradeWriteError(f"Moodle WS error: {body.get('message', '')}")

        if not isinstance(body, list):
            raise MoodleGradeWriteError("Respuesta inesperada de core_user_get_users_by_field")

        if len(body) == 0:
            return None
        if len(body) > 1:
            raise MoodleGradeWriteError(
                f"Múltiples usuarios Moodle con idnumber={idnumber!r} — no se puede resolver"
            )

        return int(body[0]["id"])

    async def lookup_userid_by_email(self, email: str) -> int | None:
        """Busca el userid de Moodle por email. None si no hay match único."""
        url = f"{self._config.base_url.rstrip('/')}/webservice/rest/server.php"
        data = {
            "wstoken": self._config.ws_token,
            "wsfunction": "core_user_get_users_by_field",
            "moodlewsrestformat": "json",
            "field": "email",
            "values[0]": email,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(url, data=data)
        except Exception as exc:
            raise MoodleGradeWriteError(f"Error de red buscando usuario por email: {exc}") from exc

        if response.status_code >= 400:
            raise MoodleGradeWriteError(f"HTTP {response.status_code} al buscar por email")

        try:
            body = response.json()
        except Exception as exc:
            raise MoodleGradeWriteError(f"Respuesta JSON inválida: {exc}") from exc

        if isinstance(body, dict) and "exception" in body:
            raise MoodleGradeWriteError(f"Moodle WS error: {body.get('message', '')}")

        if not isinstance(body, list):
            raise MoodleGradeWriteError("Respuesta inesperada de lookup por email")

        if len(body) == 0:
            return None
        if len(body) > 1:
            raise MoodleGradeWriteError(
                f"Múltiples usuarios Moodle con email={email!r} — no se puede resolver"
            )

        return int(body[0]["id"])
