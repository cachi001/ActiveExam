"""Escritura de la nota en Moodle: los dos caminos y el selector.

`escribir_nota` es el UNICO punto de entrada. Rutea por `component`:
  - `mod_assign` -> `mod_assign_save_grade` (servicio movil de fabrica, cero
    configuracion en el campus, *Calificador* = el docente).
  - cualquier otro -> `core_grades_update_grades` (exige un servicio externo
    habilitado en el campus).

Se apoya en `MoodleTransporte` (`_resolver_config`, `_post_ws`) y en
`ActividadMixin` (`resolver_assignment_config`, `get_grademax`), que la clase
concreta `MoodleRestClient` compone.
"""

from __future__ import annotations

import httpx

from app.infrastructure.moodle.transporte import (
    MoodleDestinoNoConfiguradoError,
    MoodleEscalaNoSoportadaError,
    MoodleGradeWriteError,
)


class NotasMixin:
    """Operaciones de escritura de nota."""

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
        base_url: str | None = None,
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
                base_url=base_url,
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
        base_url: str | None = None,
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
                base_url=base_url,
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
            base_url=base_url,
            source=source,
        )

    async def write_grade_assign(
        self,
        *,
        moodle_userid: int,
        nota: float,
        courseid: int | None,
        cmid: int | None,
        nota_maxima: float | None = None,
        ws_token: str | None = None,
        base_url: str | None = None,
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
            courseid=courseid, cmid=cmid, ws_token=ws_token, base_url=base_url
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
            base_url=base_url,
            que_falla="enviar la nota",
        )
