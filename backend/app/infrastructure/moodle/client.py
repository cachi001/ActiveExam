"""Cliente Moodle REST para write-back de nota vía core_grades_update_grades (C-69, D7).

El token se toma de MoodleClientConfig — NUNCA se loguea ni se expone al cliente.
Schema Pydantic extra='forbid'.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssignmentGradeConfig:
    """Como califica una TAREA de Moodle, leido de ``mod_assign_get_assignments``.

    ``instance_id`` es el ``assign.id`` (tabla assign), NO el ``cmid`` que aparece en
    la URL del curso y que es lo que guardamos en `examen_contenido.moodle_cmid`.
    ``mod_assign_save_grade`` pide el instance id: confundirlos escribe la nota en
    otra actividad.

    Interpretacion del campo ``grade`` del assignment (confirmada E2E en campustest):
        grade > 0   -> numerica, ``grade_max = grade``
        grade < 0   -> escala cualitativa, ``scale_id = abs(grade)``
        grade == 0  -> la actividad no califica
    """

    instance_id: int
    tipo: str  # "numerica" | "escala" | "sin_calificacion"
    grade_max: float | None = None
    scale_id: int | None = None


class MoodleClientConfig(BaseModel):
    """Credencial del campus. extra='forbid' — regla dura de código.

    Acá va SOLO lo que es institucional: una URL de campus y una cuenta de servicio.
    El DESTINO (curso y actividad) NO vive acá: es de cada examen. Antes había un
    `courseid`/`cmid` global que se usaba como fallback, y eso convertía "examen sin
    destino configurado" en "nota escrita en la libreta de otra materia", sin error
    visible — el write-back reportaba 'enviado'.

    `component` sí es un default institucional razonable (con qué tipo de actividad
    trabaja la institución); cada examen puede sobreescribirlo.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str
    ws_token: str
    component: str = "mod_assign"  # 'mod_assign' | 'mod_quiz'


class MoodleGradeWriteError(Exception):
    """Fallo en el write-back de la nota a Moodle (red, token inválido, error WS)."""


class MoodleDestinoNoConfiguradoError(MoodleGradeWriteError):
    """El examen no tiene curso/actividad de destino en el campus.

    Es un error EXPLÍCITO a propósito: antes se caía a un destino global y la nota
    terminaba en la libreta equivocada sin que nadie se enterara. Preferimos que la
    nota quede retenida y visible a que se escriba en otra materia.
    """

    def __init__(self) -> None:
        super().__init__(
            "El examen no tiene configurado el curso y la actividad de destino en "
            "el campus. Cargalos en el examen para poder enviar la nota."
        )


class MoodleEscalaNoSoportadaError(MoodleGradeWriteError):
    """La actividad destino usa una escala CUALITATIVA y no sabemos su orden.

    Una escala de Moodle es una lista de textos y el WS no expone cual corresponde a
    cada indice. El orden NO es inferible: en `tup.sied.utn.edu.ar` la escala id 5
    tiene 1=Aprobado y 2=Desaprobado, o sea INVERTIDO respecto de lo intuitivo.
    Adivinar mal no produce un error, produce algo peor: desaprueba a todos los
    aprobados, en la libreta oficial y con la firma del docente.

    Por eso se corta. Un examen de ActiveExam califica numericamente; si el destino
    usa escala cualitativa, la actividad esta mal elegida o hace falta mapear la
    escala explicitamente.
    """

    def __init__(self, scale_id: int | None = None) -> None:
        super().__init__(
            f"La actividad destino usa una escala cualitativa (id {scale_id}) y no una "
            "nota numerica. No se envia la nota para no calificar mal: elegi una "
            "actividad con puntuacion numerica."
        )


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
        return MoodleClientConfig(base_url="", ws_token="")

    async def write_grade(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None = None,
        cmid: int | None = None,
        component: str | None = None,
        nota_maxima: float | None = None,
        ws_token: str | None = None,
        source: str | None = None,
    ) -> None:
        """Escribe la nota del alumno en Moodle vía core_grades_update_grades.

        ws_token (C-73 §10): token del DOCENTE a cargo de la comisión. Cuando viene,
        la nota se escribe con SU identidad — Moodle registra a la persona y le impone
        sus propios permisos (no puede escribir donde no da clase). Sin él se usa el
        institucional, que es el respaldo.

        source (C-73 §10.6): queda en el historial de calificaciones de Moodle. Sirve
        para saber, mirando la libreta, qué examen produjo la nota y si se devolvió con
        credencial personal o institucional.

        D12 (parte B): courseid/cmid son el destino POR EXAMEN y son OBLIGATORIOS.
        Ya no hay fallback a un destino global: sin destino se eleva
        MoodleDestinoNoConfiguradoError en vez de escribir en la libreta de otra
        materia.

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

        # Destino OBLIGATORIO por examen. Sin fallback global: escribir en un curso
        # que no es el del examen es peor que no escribir (ver
        # MoodleDestinoNoConfiguradoError).
        if not courseid or not cmid:
            raise MoodleDestinoNoConfiguradoError()
        target_courseid = courseid
        target_cmid = cmid
        target_component = component if component is not None else cfg.component  # default institucional

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
                # Misma credencial que la escritura: si se lee la escala con el token
                # institucional y se escribe con el del docente, se puede estar
                # leyendo un item que ese docente ni siquiera ve.
                ws_token=ws_token,
            )
            nota_a_enviar = nota / nota_maxima * grademax

        # Payload del WS. El token va en wstoken (protocolo Moodle REST WS).
        # NUNCA se loguea ni aparece en campos de audit.
        data = {
            # El token del docente PISA al institucional cuando existe: la nota debe
            # figurar puesta por la persona, no por una cuenta de servicio.
            "wstoken": ws_token or cfg.ws_token,
            "wsfunction": "core_grades_update_grades",
            "moodlewsrestformat": "json",
            "source": source or "activeexam",
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
        ws_token: str | None = None,
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
        # Destino OBLIGATORIO por examen. Sin fallback global: escribir en un curso
        # que no es el del examen es peor que no escribir (ver
        # MoodleDestinoNoConfiguradoError).
        if not courseid or not cmid:
            raise MoodleDestinoNoConfiguradoError()
        target_courseid = courseid
        target_cmid = cmid

        data = {
            "wstoken": ws_token or cfg.ws_token,
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

    # ------------------------------------------------------------------
    # C-73 Fase 1 — write-back por mod_assign_save_grade (servicio movil)
    #
    # POR QUE HAY UN SEGUNDO CAMINO DE ESCRITURA:
    #   `core_grades_update_grades` NO esta en el servicio movil de fabrica de Moodle,
    #   asi que exige un servicio externo custom con lista blanca de usuarios: alguien
    #   tiene que tocar la configuracion del campus, y de forma recurrente.
    #   `mod_assign_save_grade` SI esta en el servicio de fabrica. Como
    #   `createmobiletoken` tambien es default, el docente se autoemite su token y la
    #   nota queda registrada con SU identidad — la columna *Calificador* de la libreta
    #   dice su nombre — sin que nadie configure nada.
    #
    #   Verificado E2E en campustest (curso 7, cmid 537 -> assign.id 39): Calificador
    #   = "Profesor Prueba". La sonda que lo confirmo: `mod_assign_save_grade` con
    #   `assignmentid=0` devuelve `invalidrecord`, no `accessexception`.
    #
    # EL PRECIO: solo sirve para TAREAS (mod_assign). Para `mod_quiz` no existe
    #   equivalente y hay que seguir por `write_grade`.
    #
    # NOTA SOBRE LA ATRIBUCION: en este camino el campo *Fuente* del historial lo pone
    #   Moodle (`mod/assign`); el parametro `source` que usa `write_grade` no aplica.
    #   No se pierde nada: la atribucion pasa de autodeclarada por nosotros a
    #   registrada por Moodle, que es mas fuerte.
    # ------------------------------------------------------------------

    async def lookup_userid_en_curso(
        self,
        *,
        courseid: int,
        idnumber: str,
        email: str,
        ws_token: str | None = None,
    ) -> int | None:
        """Resuelve el userid del alumno entre los MATRICULADOS del curso.

        POR QUE EXISTE (C-73 Fase 2): `lookup_userid_by_idnumber` / `_by_email` usan
        `core_user_get_users_by_field` con la credencial INSTITUCIONAL, asi que el
        write-back dependia de un token institucional vivo aunque el docente ya tuviera
        su cuenta conectada. `core_enrol_get_enrolled_users` esta en el servicio movil
        de fabrica y el docente ve a los matriculados de SU curso: con esto ActiveExam
        deja de necesitar credencial institucional para devolver notas.

        Beneficio extra que no hay que subestimar: el alcance lo pone Moodle. Un docente
        no puede resolver identidades en cursos donde no da clase, porque el WS
        directamente no se lo permite.

        Orden de resolucion: `idnumber` (clave institucional) y luego `email`. El legajo
        gana porque dos personas pueden compartir un email (cuentas de catedra) pero no
        un legajo. El email se compara en minuscula: Moodle los normaliza y el padron
        puede no venir asi, y comparar sensible a mayusculas dejaba a un alumno sin nota
        por como se escribio su direccion.

        Returns:
            El userid, o ``None`` si el alumno NO esta matriculado en el curso.

        Raises:
            MoodleGradeWriteError: error de red / WS, o mas de un matriculado con el
                mismo idnumber (no se elige uno arbitrario: escribirle la nota al que
                no es, es peor que no escribirla).
        """
        body = await self._post_ws(
            wsfunction="core_enrol_get_enrolled_users",
            data={"courseid": str(courseid)},
            ws_token=ws_token,
            que_falla="listar los matriculados del curso",
        )

        usuarios = body if isinstance(body, list) else []

        if idnumber:
            coincidencias = [
                u for u in usuarios if (u.get("idnumber") or "").strip() == idnumber
            ]
            if len(coincidencias) > 1:
                raise MoodleGradeWriteError(
                    f"Hay {len(coincidencias)} matriculados en el curso {courseid} con "
                    f"idnumber={idnumber!r} — no se puede resolver a quien corresponde "
                    "la nota."
                )
            if coincidencias:
                return int(coincidencias[0]["id"])

        if email:
            objetivo = email.strip().lower()
            coincidencias = [
                u for u in usuarios if (u.get("email") or "").strip().lower() == objetivo
            ]
            if len(coincidencias) > 1:
                raise MoodleGradeWriteError(
                    f"Hay {len(coincidencias)} matriculados en el curso {courseid} con "
                    f"email={email!r} — no se puede resolver a quien corresponde la nota."
                )
            if coincidencias:
                return int(coincidencias[0]["id"])

        return None

    async def escribir_nota(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None,
        cmid: int | None,
        component: str | None = None,
        nota_maxima: float | None = None,
        ws_token: str | None = None,
        source: str | None = None,
        feedback_html: str | None = None,
    ) -> None:
        """UNICO punto de entrada para escribir una nota. Rutea segun ``component``.

        - ``mod_assign``  -> ``write_grade_assign`` (servicio movil de fabrica, cero
          configuracion en el campus, *Calificador* = el docente).
        - cualquier otro  -> ``write_grade`` (``core_grades_update_grades``, que exige
          un servicio externo habilitado en el campus).

        El ruteo vive ACA y no en el servicio de write-back porque hay tres lugares que
        escriben notas (envio, anulacion y restitucion): con el `if` en el servicio
        habria que repetirlo en los tres y el proximo camino se olvidaria en alguno.

        ``source`` solo aplica al camino viejo: en ``mod_assign_save_grade`` la *Fuente*
        del historial la pone Moodle (`mod/assign`). No se pierde atribucion — la
        identidad del calificador la registra Moodle, que es mas fuerte que un string
        declarado por nosotros.
        """
        cfg = await self._resolver_config()
        target_component = component if component is not None else cfg.component

        if target_component == "mod_assign":
            await self.write_grade_assign(
                moodle_userid=moodle_userid,
                nota=nota,
                courseid=courseid,
                cmid=cmid,
                nota_maxima=nota_maxima,
                ws_token=ws_token,
                feedback_html=feedback_html,
            )
            return

        await self.write_grade(
            moodle_userid=moodle_userid,
            nota=nota,
            courseid=courseid,
            cmid=cmid,
            component=target_component,
            nota_maxima=nota_maxima,
            ws_token=ws_token,
            source=source,
        )

    async def _post_ws(
        self,
        *,
        wsfunction: str,
        data: dict[str, str],
        ws_token: str | None,
        que_falla: str,
    ) -> dict | list | None:
        """POST a la REST API de Moodle con el manejo de errores comun.

        ``que_falla`` se usa para construir el mensaje: sin eso, todos los fallos de
        red dicen lo mismo y no se sabe en que paso se rompio.

        El token va solo en el form-data y NUNCA se loguea.
        """
        cfg = await self._resolver_config()
        url = f"{cfg.base_url.rstrip('/')}/webservice/rest/server.php"
        payload = {
            "wstoken": ws_token or cfg.ws_token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **data,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(url, data=payload)
        except Exception as exc:
            raise MoodleGradeWriteError(
                f"Error de red al {que_falla}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise MoodleGradeWriteError(
                f"Moodle devolvio HTTP {response.status_code} al {que_falla}"
            )

        # Cuerpo vacio = exito sin datos. `mod_assign_save_grade` devuelve el literal
        # `null`, pero un 200 sin contenido significa lo mismo, y tratarlo como
        # "respuesta ilegible" convertiria una nota BIEN escrita en un fallo — y el
        # reintento la escribiria de nuevo.
        if not response.content.strip():
            return None

        try:
            body = response.json()
        except Exception as exc:
            raise MoodleGradeWriteError(
                f"Respuesta de Moodle no es JSON valido al {que_falla}: {exc}"
            ) from exc

        # Moodle contesta 200 con {"exception": ...} incluso cuando fallo: el status
        # HTTP no alcanza para saber si salio bien.
        if isinstance(body, dict) and ("exception" in body or "errorcode" in body):
            errorcode = body.get("errorcode", "unknown")
            message = body.get("message", "")
            raise MoodleGradeWriteError(
                f"Moodle WS error al {que_falla} ({errorcode}): {message}"
            )

        return body

    async def resolver_assignment_config(
        self,
        *,
        courseid: int,
        cmid: int,
        ws_token: str | None = None,
    ) -> AssignmentGradeConfig | None:
        """Traduce ``cmid`` -> ``assign.id`` y lee como califica la actividad.

        Returns:
            La config, o ``None`` si el cmid no corresponde a una TAREA de ese curso
            (por ejemplo, si es un Cuestionario). ``None`` significa exactamente eso:
            un error del WS se propaga como excepcion, para no confundir "no es una
            tarea" con "no pude preguntar".

        Raises:
            MoodleGradeWriteError: error de red o del WS.
        """
        body = await self._post_ws(
            wsfunction="mod_assign_get_assignments",
            data={"courseids[0]": str(courseid)},
            ws_token=ws_token,
            que_falla="resolver la actividad destino",
        )

        for curso in (body or {}).get("courses", []):
            for assignment in curso.get("assignments", []):
                if int(assignment.get("cmid") or 0) != int(cmid):
                    continue

                instance_id = int(assignment.get("id"))
                grade = assignment.get("grade")

                if grade is None or float(grade) == 0:
                    return AssignmentGradeConfig(
                        instance_id=instance_id, tipo="sin_calificacion"
                    )
                if float(grade) > 0:
                    return AssignmentGradeConfig(
                        instance_id=instance_id,
                        tipo="numerica",
                        grade_max=float(grade),
                    )
                # Negativo = id de escala cualitativa. NO es un error: es un dato.
                return AssignmentGradeConfig(
                    instance_id=instance_id,
                    tipo="escala",
                    scale_id=abs(int(grade)),
                )

        return None

    async def hay_nota_cargada(
        self,
        *,
        instance_id: int,
        moodle_userid: int,
        ws_token: str | None = None,
    ) -> bool:
        """``True`` si ese alumno YA tiene nota en esa tarea.

        Anti-pisado: si un docente califico a mano, sobreescribirle la nota es
        destructivo y no se puede deshacer desde aca. Quien llame decide que hacer;
        este metodo solo informa.

        Criterio de "nota real": ``timemodified > 0`` y la nota no es negativa. Moodle
        usa ``-1`` para "sin calificar", asi que un -1 no es una nota que alguien puso.
        Un 0 legitimo SI cuenta (es una nota, y pisarla seria igual de destructivo).
        """
        body = await self._post_ws(
            wsfunction="mod_assign_get_grades",
            data={"assignmentids[0]": str(instance_id)},
            ws_token=ws_token,
            que_falla="leer las notas ya cargadas",
        )

        for assignment in (body or {}).get("assignments", []):
            for nota in assignment.get("grades", []) or []:
                if int(nota.get("userid") or 0) != int(moodle_userid):
                    continue
                if not int(nota.get("timemodified") or 0) > 0:
                    continue
                valor = nota.get("grade")
                if valor is None:
                    continue
                if float(valor) >= 0:
                    return True

        return False

    async def write_grade_assign(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None,
        cmid: int | None,
        nota_maxima: float | None = None,
        ws_token: str | None = None,
        feedback_html: str | None = None,
    ) -> None:
        """Escribe la nota en una TAREA via ``mod_assign_save_grade``.

        ``ws_token``: token del DOCENTE. Moodle registra como *Calificador* al dueno
        del token, asi que este parametro es lo que hace que la nota lleve el nombre
        de la persona y no de una cuenta de servicio. Ademas Moodle le aplica SUS
        permisos: no puede calificar en un curso donde no da clase.

        ``nota_maxima``: escala de ORIGEN (``examen_contenido.nota_maxima``). Se usa
        para convertir a la escala del item: sin esto un 8 sobre 10 se escribia como
        8 sobre 100. El ``grade_max`` destino sale del propio assignment, no de una
        copia nuestra que se desincronizaria en silencio.

        Raises:
            MoodleDestinoNoConfiguradoError: sin curso/actividad de destino.
            MoodleEscalaNoSoportadaError: la actividad usa escala cualitativa.
            MoodleGradeWriteError: el cmid no es una tarea, la actividad no califica,
                o fallo la red / el WS.
        """
        # Destino OBLIGATORIO por examen. Sin fallback global: escribir en un curso
        # que no es el del examen es peor que no escribir.
        if not courseid or not cmid:
            raise MoodleDestinoNoConfiguradoError()

        # La MISMA credencial para resolver y para escribir: leer la escala con el
        # token institucional y escribir con el del docente puede estar leyendo un
        # item que ese docente ni siquiera ve.
        config = await self.resolver_assignment_config(
            courseid=courseid, cmid=cmid, ws_token=ws_token
        )

        if config is None:
            raise MoodleGradeWriteError(
                f"El cmid {cmid} no es una tarea del curso {courseid}. Si es un "
                "cuestionario, este camino no aplica."
            )
        if config.tipo == "sin_calificacion":
            raise MoodleGradeWriteError(
                f"La actividad destino (cmid {cmid}) no califica: no tiene puntuacion "
                "configurada en Moodle."
            )
        if config.tipo == "escala":
            raise MoodleEscalaNoSoportadaError(config.scale_id)

        # Conversion de escala. Sin `nota_maxima` no hay nada que convertir y se manda
        # tal cual (compat con sesiones sin examen asociado).
        nota_a_enviar = nota
        if nota_maxima and nota_maxima > 0 and config.grade_max:
            nota_a_enviar = round(nota / nota_maxima * config.grade_max, 2)

        data = {
            # El INSTANCE id, no el cmid.
            "assignmentid": str(config.instance_id),
            "userid": str(moodle_userid),
            "grade": str(float(nota_a_enviar)),
            "attemptnumber": "-1",  # ultimo intento
            "addattempt": "0",
            "workflowstate": "",
            "applytoall": "1",
        }
        if feedback_html:
            data["plugindata[assignfeedbackcomments_editor][text]"] = feedback_html
            data["plugindata[assignfeedbackcomments_editor][format]"] = "1"  # 1 = HTML

        # `mod_assign_save_grade` devuelve null en exito; _post_ws ya levanta si vino
        # un `exception`.
        await self._post_ws(
            wsfunction="mod_assign_save_grade",
            data=data,
            ws_token=ws_token,
            que_falla="enviar la nota",
        )
