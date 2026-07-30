"""Lectura de metadata de la actividad destino en Moodle.

Todo lo que hay que SABER de la actividad antes de escribirle una nota: su
instance id, como califica, y si ya tiene una nota puesta.

Se apoya en `MoodleTransporte` (`_resolver_config`, `_post_ws`).
"""

from __future__ import annotations

import httpx

from app.infrastructure.moodle.transporte import (
    AssignmentGradeConfig,
    MoodleDestinoNoConfiguradoError,
    MoodleGradeWriteError,
)


class ActividadMixin:
    """Operaciones de lectura sobre la actividad destino."""

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
