"""Transporte HTTP y tipos compartidos del cliente Moodle.

Aca vive lo que NO es una operacion de negocio: la credencial del campus, las
excepciones, y el unico lugar que hace POST contra `webservice/rest/server.php`.

Los modulos `notas`, `identidad` y `actividad` aportan las operaciones y se
apoyan en `MoodleTransporte` via herencia (ver `client.py`). El token nunca se
loguea: viaja solo en el form-data.
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


class MoodleTransporte:
    """Resolucion de credencial + POST a la REST API. Sin logica de negocio."""

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
