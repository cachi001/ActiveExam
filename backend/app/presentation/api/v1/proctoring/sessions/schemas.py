"""Schemas Pydantic para endpoints de sesiones de proctoring activeexam.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: screenshot_base64 y biometria son datos sensibles.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FinalizarSesionOut(BaseModel):
    """Respuesta de PATCH /sessions/{id}/finalizar → 200."""

    model_config = ConfigDict(extra="forbid")

    id: str
    finalizada_en: Any  # datetime o str segun el ORM


class CrearSesionIn(BaseModel):
    """Body de POST /sessions."""

    model_config = ConfigDict(extra="forbid")

    modo: str = Field(..., description="'test' o 'examen'")
    exam_id: str | None = Field(None, description="ID del examen (referencia externa)")
    etiqueta: str | None = Field(None, description="Etiqueta libre para la sesion")
    # C-69: vinculo REAL con el examen de contenido importado de Moodle XML.
    # NULLABLE — sesion sin contenido (modo 'test' o examen sin contenido) sigue valida.
    examen_contenido_id: str | None = Field(
        None, description="FK a examen_contenido(id). NULL = sesion sin contenido vinculado."
    )


class CrearSesionOut(BaseModel):
    """Respuesta de POST /sessions → 201."""

    model_config = ConfigDict(extra="forbid")

    id: str
    creada_en: Any  # datetime o str segun el ORM
    # C-69: eco del vinculo persistido. El front lo usa para confirmar contra qué
    # examen_contenido quedó atada la sesion (round-trip por la sesion real).
    examen_contenido_id: str | None = None


class EventoDetalle(BaseModel):
    """Detalle de un evento de deteccion para GET /sessions/{id}.

    Incluye screenshot base64, sha256, veredicto de re-inferencia y conteos
    de rostros (cliente vs servidor) para la revision humana (tutor/coordinador).

    PRODUCCION: screenshot_base64 es dato sensible (Ley 25.326).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    tipo: str
    severidad: str
    ts_cliente: Any
    ts_backend: Any
    payload: dict | None = None
    screenshot_base64: str | None = None
    screenshot_sha256: str | None = None
    face_count_cliente: int | None = None
    face_count_servidor: int | None = None
    veredicto_reinferencia: str
    # C-15 (6.4): True si el evento cayo dentro de una ventana de pausa autorizada.
    # El score del detalle EXCLUYE estos eventos (L2.5: contextualiza, no borra).
    en_pausa_autorizada: bool = False


class BiometriaDetalle(BaseModel):
    """Resultado biometrico para GET /sessions/{id}."""

    model_config = ConfigDict(extra="forbid")

    liveness_ok: bool
    retos_resueltos: list
    resultado: str
    registrada_en: Any


class SesionResumen(BaseModel):
    """Resumen de sesion para GET /sessions (lista)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    modo: str
    # ID del examen (referencia externa). La Cola de revision lo usa para vincular
    # la sesion con la materia/comision/examen. Sin esto, la cola descarta la sesion.
    exam_id: str | None = None
    etiqueta: str | None = None
    creada_en: Any
    finalizada_en: Any = None
    # ts del ultimo evento (o creada_en si no hubo eventos). La UI lo usa para
    # distinguir actividad reciente de sesiones calmas/abandonadas.
    ultimo_evento_en: Any = None
    total_eventos: int
    total_discrepancias: int
    score: int
    # Contexto academico resuelto server-side (examen_contenido -> comision ->
    # materia). El frontend los usa para agrupar la Cola de revision y etiquetar las
    # sesiones grabadas SIN depender de catalogos mock. NULL si la sesion no tiene
    # contenido vinculado o el examen no esta asociado a comision/materia.
    examen_contenido_id: str | None = None
    examen_titulo: str | None = None
    comision_nombre: str | None = None
    materia_nombre: str | None = None
    # Identidad del alumno (C-76 tarea 17: columna "Alumno" del Registro de
    # sesiones). Ausente/None en listados que no la resuelven (compat).
    alumno_idnumber: str | None = None
    alumno_email: str | None = None
    alumno_nombre: str | None = None


class RegistroSesionesOut(BaseModel):
    """Respuesta paginada de GET /sessions/registro (C-76 tarea 17).

    Envelope de paginacion real (mismo shape que ``ResultadosExamenPaginadosResponse``
    de exam-content/resultados): items de la pagina actual + total GLOBAL filtrado.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[SesionResumen]
    total: int
    page: int
    page_size: int
    # Agregados sobre el TOTAL filtrado (C-76 tarea 19.3/20.4) — calculados ANTES
    # de paginar, sobre las sesiones que matchean q/exam_id/fecha/nivel_riesgo/
    # materia_id/comision_id. NUNCA se derivan de `items` (que solo trae la
    # pagina actual): el frontend los usa tal cual para las stat cards.
    #
    # `total_eventos`/`total_discrepancias` (tarea 19) se retiraron en la tarea 20
    # (feedback del dueño: no son decisivos como stat general) — reemplazados por
    # `en_cola_revision`.
    riesgo_bajo: int
    riesgo_medio: int
    riesgo_alto: int
    # Sesiones con score >= umbral de la Cola de revision (`obtener_umbral_alto`,
    # el MISMO umbral que usa la Cola de revision — no uno reinventado). C-76
    # tarea 20.4/20.6, stat card "Sobre el umbral de riesgo".
    en_cola_revision: int


class ExamenConSesionesOut(BaseModel):
    """Una entrada del catalogo de filtro "Examen" (C-76 tarea 17.2).

    El frontend arma el <select> de "Examen" 100% desde este catalogo — nunca
    hardcodea una lista de examenes/estados.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str


class SesionDetalle(BaseModel):
    """Detalle completo de sesion para GET /sessions/{id} — vista del tutor."""

    model_config = ConfigDict(extra="forbid")

    id: str
    modo: str
    etiqueta: str | None = None
    # C-69: contra qué examen_contenido (Moodle XML) rindió el alumno. NULL si la
    # sesion no tiene contenido vinculado.
    examen_contenido_id: str | None = None
    # Contexto académico resuelto server-side (examen_contenido → comisión →
    # materia), igual que en SesionResumen (listar_sesiones) — el detalle también
    # lo necesita para el header ("qué examen rindió, de qué materia/comisión").
    examen_titulo: str | None = None
    comision_nombre: str | None = None
    materia_nombre: str | None = None
    # Identidad del alumno dueño de la sesión (C-76 fix UX): el header del detalle
    # necesita destacar QUIÉN rindió, no solo el modo de la sesión. nombre_completo
    # resuelto contra `usuario`; idnumber/email crudos como fallback si no matchea.
    alumno_nombre: str | None = None
    alumno_idnumber: str | None = None
    alumno_email: str | None = None
    creada_en: Any
    finalizada_en: Any = None
    score: int
    eventos: list[EventoDetalle]
    biometria: BiometriaDetalle | None = None
    # C-15 (3.3): cierre forzado (operativo, NO disciplinario). Se exponen para que
    # la UI del tutor refleje el estado al RECARGAR el detalle (no solo en la
    # accion). NULL si la sesion no fue cerrada de forma forzada.
    cierre_forzado_en: Any = None
    cierre_forzado_motivo: str | None = None


# --- C-15 (3.2): observaciones del tutor (insumo de C-16) ---


class ObservacionIn(BaseModel):
    """Body de POST /sessions/{id}/observaciones (tutor)."""

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(..., min_length=1, max_length=2000)
    tutor_actor: str | None = Field(
        None, description="Subject del JWT del tutor que escribe (audit trail)."
    )


class ObservacionOut(BaseModel):
    """Observacion del tutor (respuesta de POST y elemento del GET)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    tutor_actor: str | None = None
    creada_en: Any


# --- C-15 (3.3): cierre forzado de sesion (operativo, NO disciplinario) ---


class CerrarForzadoIn(BaseModel):
    """Body de PATCH /sessions/{id}/cerrar-forzado (tutor).

    ``motivo`` es OBLIGATORIO (operativo): por que el tutor cierra la sesion.
    NO es un veredicto disciplinario (regla dura #5).
    """

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(..., min_length=1, max_length=500)
    tutor_actor: str | None = Field(
        None, description="Subject del JWT del tutor que fuerza el cierre (audit trail)."
    )


class CerrarForzadoOut(BaseModel):
    """Respuesta de PATCH /sessions/{id}/cerrar-forzado → 200."""

    model_config = ConfigDict(extra="forbid")

    id: str
    finalizada_en: Any
    cierre_forzado_en: Any
    cierre_forzado_por: str | None = None
    cierre_forzado_motivo: str | None = None


# --- C-69 sección 7: respuestas del alumno + write-back de nota ---


class RespuestaItem(BaseModel):
    """Respuesta del alumno para una pregunta (C-69 D8, sección 7; C-74 §6 cloze).

    Exactamente uno de los dos:
    - ``opcion_elegida_id``: preguntas multichoice/truefalse.
    - ``respuesta_cloze``: preguntas cloze/ddwtos — dict ``{blank_id: valor}``,
      donde ``valor`` es el id de la opción (blank MULTICHOICE) o el texto libre
      tipeado por el alumno (blank SHORTANSWER).
    """

    model_config = ConfigDict(extra="forbid")

    pregunta_id: str
    opcion_elegida_id: str | None = None
    respuesta_cloze: dict[str, str] | None = None

    @model_validator(mode="after")
    def _exactamente_uno(self) -> "RespuestaItem":
        tiene_opcion = self.opcion_elegida_id is not None
        tiene_cloze = self.respuesta_cloze is not None
        if tiene_opcion == tiene_cloze:  # ambos ausentes o ambos presentes
            raise ValueError(
                "Cada respuesta necesita exactamente uno de "
                "'opcion_elegida_id' o 'respuesta_cloze'."
            )
        return self


class SubmitRespuestasIn(BaseModel):
    """Body de POST /sessions/{id}/respuestas.

    El alumno envía sus respuestas antes de finalizar.

    Seguridad (H4): NO se aceptan campos de identidad del cliente. La identidad
    del alumno se persiste server-side al CREAR la sesión (desde el JWT) y es la
    única fuente para el write-back de la nota. Con ``extra='forbid'`` cualquier
    ``alumno_idnumber``/``alumno_email`` enviado por el cliente es rechazado (422)
    para cerrar la superficie de spoofing de identidad de la nota.
    """

    model_config = ConfigDict(extra="forbid")

    respuestas: list[RespuestaItem]


class SubmitRespuestasOut(BaseModel):
    """Respuesta de POST /sessions/{id}/respuestas → 201."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    respuestas_guardadas: int


class RespuestaGuardadaOut(BaseModel):
    """Una respuesta ya guardada de la sesion (para reanudacion, GET .../respuestas).

    Mismo contrato exactamente-uno que ``RespuestaItem``.
    """

    model_config = ConfigDict(extra="forbid")

    pregunta_id: str
    opcion_elegida_id: str | None = None
    respuesta_cloze: dict[str, str] | None = None


class ListarRespuestasOut(BaseModel):
    """Respuesta de GET /sessions/{id}/respuestas → 200.

    Vuln reload/restart: al reanudar una sesion activa (misma id, mismo timer), el
    cliente necesita recuperar lo que YA habia contestado antes del F5. Solo el
    DUEÑO de la sesion puede leerlas (mismo gate de propiedad que submit_respuestas).
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    respuestas: list[RespuestaGuardadaOut]
