"""Cliente Moodle REST para write-back de nota vía core_grades_update_grades (C-69, D7).

El token se toma de MoodleClientConfig — NUNCA se loguea ni se expone al cliente.
Schema Pydantic extra='forbid'.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

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
    component: str = "mod_assign"  # C-73: módulo destino global ('mod_assign'|'mod_quiz')


class MoodleGradeWriteError(Exception):
    """Fallo en el write-back de la nota a Moodle (red, token inválido, error WS)."""


class MoodleRestClient:
    """Cliente async para la Web Service core_grades_update_grades de Moodle.

    El token nunca se loguea: se usa sólo en el campo wstoken del form-data.
    """

    def __init__(
        self,
        config: MoodleClientConfig | None = None,
        *,
        config_provider: "Callable[[], Awaitable[MoodleClientConfig]] | None" = None,
    ) -> None:
        """Config fija, o un ``config_provider`` que la resuelve en cada llamada.

        El provider existe porque la credencial ahora vive en la base y el admin
        puede rotarla en caliente (migracion 0047): con la config congelada al
        arrancar, cambiar el token exigia reiniciar el backend. El provider se
        consulta por llamada y el resolver cachea, asi que no agrega viajes a la DB.
        """
        if config is None and config_provider is None:
            raise ValueError("MoodleRestClient necesita config o config_provider.")
        self._config_estatico = config
        self._config_provider = config_provider

    async def _resolver_config(self) -> MoodleClientConfig:
        """Config vigente para esta llamada (provider si hay, si no la estatica)."""
        if self._config_provider is not None:
            return await self._config_provider()
        assert self._config_estatico is not None
        return self._config_estatico

    @property
    def _config(self) -> MoodleClientConfig:
        """Config estatica. Solo para consumidores sincronicos (p.ej. la redaccion
        del token en los mensajes de error). Con provider puro devuelve una config
        vacia: quien necesite el valor vivo debe usar ``_resolver_config``."""
        if self._config_estatico is not None:
            return self._config_estatico
        return MoodleClientConfig(base_url="", ws_token="", courseid=0, cmid=0)

    async def write_grade(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None = None,
        cmid: int | None = None,
        component: str | None = None,
        nota_maxima: float | None = None,
    ) -> None:
        """Escribe la nota del alumno en Moodle vía core_grades_update_grades.

        D12 (parte B): courseid/cmid son el destino POR EXAMEN. Si se pasan, se usan;
        si son None, se cae al global de config (compat con exámenes sin destino).

        component: módulo de la actividad destino en Moodle ('mod_assign' para tareas,
        'mod_quiz' para cuestionarios). El write-back es a nivel del grade item, así que
        funciona con cualquier tipo; el component debe coincidir con la actividad real
        (validado E2E en campustest). Default 'mod_assign' (compat con exámenes previos).

        Raises:
            MoodleGradeWriteError: si Moodle devuelve un error, token inválido,
                fallo de red o respuesta HTTP no-2xx.
        """
        cfg = await self._resolver_config()
        url = f"{cfg.base_url.rstrip('/')}/webservice/rest/server.php"

        # Destino: valor por examen si vino; si no, fallback al global de config.
        target_courseid = courseid if courseid is not None else cfg.courseid
        target_cmid = cmid if cmid is not None else cfg.cmid
        target_component = component if component is not None else cfg.component

        # CONVERSION DE ESCALA. ActiveExam califica sobre `nota_maxima` (10 por
        # defecto) y el item de Moodle suele venir sobre 100: mandar el numero crudo
        # escribia un 8/10 como 8/100 = 8%. Se lee el grademax REAL del item y se
        # convierte. Sin `nota_maxima` no hay nada que convertir (compat) y se manda
        # tal cual, que es el comportamiento previo.
        nota_a_enviar = nota
        if nota_maxima and nota_maxima > 0:
            grademax = await self.get_grademax(
                moodle_userid=moodle_userid,
                courseid=target_courseid,
                cmid=target_cmid,
            )
            nota_a_enviar = nota / nota_maxima * grademax

        # Payload del WS. El token va en wstoken (protocolo Moodle REST WS).
        # NUNCA se loguea ni aparece en campos de audit.
        data = {
            "wstoken": cfg.ws_token,
            "wsfunction": "core_grades_update_grades",
            "moodlewsrestformat": "json",
            "source": "activeexam",
            "courseid": str(target_courseid),
            "component": target_component,
            "activityid": str(target_cmid),
            "itemnumber": "0",
            "grades[0][studentid]": str(moodle_userid),
            "grades[0][grade]": str(round(nota_a_enviar, 2)),
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
        cfg = await self._resolver_config()
        url = f"{cfg.base_url.rstrip('/')}/webservice/rest/server.php"
        data = {
            "wstoken": cfg.ws_token,
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
        cfg = await self._resolver_config()
        url = f"{cfg.base_url.rstrip('/')}/webservice/rest/server.php"
        data = {
            "wstoken": cfg.ws_token,
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

    async def get_grademax(
        self,
        *,
        moodle_userid: int,
        courseid: int | None = None,
        cmid: int | None = None,
    ) -> float:
        """Nota MAXIMA del item destino en Moodle (``grademax``).

        Hace falta porque las escalas NO tienen por que coincidir: ActiveExam
        califica sobre ``examen_contenido.nota_maxima`` (10 por defecto) y una tarea
        de Moodle viene sobre 100 de fabrica. Mandar el 8 crudo lo escribia como
        8/100 = 8%: un alumno aprobado quedaba casi desaprobado en la libreta
        oficial. Con el grademax real, el write-back convierte antes de enviar.

        Se lee del propio Moodle en vez de configurarlo aparte: es un dato que ya
        vive alla y que el docente puede cambiar desde la actividad en cualquier
        momento. Una copia nuestra se desincronizaria en silencio.

        ``gradereport_user_get_grade_items`` exige un userid — se usa el del alumno
        que se esta calificando, que ya viene resuelto en este punto del flujo.

        Raises:
            MoodleGradeWriteError: si no se puede determinar. NO se asume 100: con
                la escala equivocada la nota queda MAL en la libreta, y una nota
                faltante es preferible a una nota incorrecta.
        """
        cfg = await self._resolver_config()
        url = f"{cfg.base_url.rstrip('/')}/webservice/rest/server.php"
        target_courseid = courseid if courseid is not None else cfg.courseid
        target_cmid = cmid if cmid is not None else cfg.cmid

        data = {
            "wstoken": cfg.ws_token,
            "wsfunction": "gradereport_user_get_grade_items",
            "moodlewsrestformat": "json",
            "courseid": str(target_courseid),
            "userid": str(moodle_userid),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(url, data=data)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            raise MoodleGradeWriteError(
                f"No se pudo leer la escala del item destino: {exc}"
            ) from exc

        if isinstance(body, dict) and "exception" in body:
            raise MoodleGradeWriteError(
                f"Moodle WS error al leer la escala: {body.get('message', '')}"
            )

        for usergrade in (body or {}).get("usergrades", []):
            for item in usergrade.get("gradeitems", []):
                # El item se identifica por su cmid; `itemid` es del grade item, otro id.
                if int(item.get("cmid") or 0) != int(target_cmid or 0):
                    continue
                grademax = item.get("grademax")
                if grademax is None:
                    break
                grademax = float(grademax)
                if grademax <= 0:
                    # Un grademax 0 o negativo significa escala personalizada de
                    # Moodle (grademax negativo = id de escala): no es una nota
                    # numerica y convertir a ciegas pondria cualquier cosa.
                    raise MoodleGradeWriteError(
                        f"El item cmid={target_cmid} no usa nota numerica "
                        f"(grademax={grademax}): no se puede convertir la nota."
                    )
                return grademax

        raise MoodleGradeWriteError(
            f"No se encontro el item cmid={target_cmid} en el curso {target_courseid} "
            "para leer su nota maxima."
        )
