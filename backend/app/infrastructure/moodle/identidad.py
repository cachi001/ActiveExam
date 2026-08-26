"""Resolucion de la identidad del alumno en Moodle (alumno -> moodle_userid).

Dos familias:
  - `lookup_userid_by_idnumber` / `_by_email`: `core_user_get_users_by_field` con
    la credencial INSTITUCIONAL. Camino historico.
  - `lookup_userid_en_curso`: `core_enrol_get_enrolled_users` con el token del
    DOCENTE. No necesita credencial institucional y el alcance lo impone Moodle.

Se apoya en `MoodleTransporte` (`_resolver_config`, `_post_ws`).
"""

from __future__ import annotations

import httpx

from app.infrastructure.moodle.transporte import MoodleGradeWriteError


class IdentidadMixin:
    """Operaciones de resolucion de identidad."""

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

    async def lookup_userid_en_curso(
        self,
        *,
        courseid: int,
        idnumber: str,
        email: str,
        ws_token: str | None = None,
        base_url: str | None = None,
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
            base_url=base_url,
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
