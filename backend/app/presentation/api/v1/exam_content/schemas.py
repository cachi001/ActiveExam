"""Schemas Pydantic para los endpoints de exam_content (C-69).

Todos con extra='forbid' (regla dura de código).
D3: es_correcta NO aparece en ningún schema de respuesta al cliente.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.domain.exam_content.entities import PoliticaIntentos


class PeriodoEnum(str, Enum):
    primer_cuatrimestre = "1C"
    segundo_cuatrimestre = "2C"


class OmitidaItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    nombre: str
    motivo: str = ""


class ImportReporteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examen_id: str
    importadas: int
    omitidas: list[OmitidaItemResponse]


class PreguntaImportadaItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enunciado: str
    tipo: str


class ImportarBancoXmlResponse(BaseModel):
    """Resultado de importar un XML directo al banco de preguntas (sin examen)."""

    model_config = ConfigDict(extra="forbid")

    preguntas_nuevas: int
    preguntas_actualizadas: int
    omitidas: list[OmitidaItemResponse]
    nuevas: list[PreguntaImportadaItemResponse] = []
    actualizadas: list[PreguntaImportadaItemResponse] = []


class PreviewCategoriaResponse(BaseModel):
    """Una categoría del árbol detectado en el XML, con conteo de preguntas por tipo."""

    model_config = ConfigDict(extra="forbid")

    ruta: list[str]
    preguntas_por_tipo: dict[str, int]
    preguntas: list[PreguntaImportadaItemResponse] = []


class PreviewImportBancoResponse(BaseModel):
    """Preview del import: qué trae el XML, SIN persistir nada en la DB."""

    model_config = ConfigDict(extra="forbid")

    categorias: list[PreviewCategoriaResponse]
    sin_categoria_por_tipo: dict[str, int]
    omitidas: list[OmitidaItemResponse]
    total_preguntas: int
    sin_categoria_preguntas: list[PreguntaImportadaItemResponse] = []


# ---------------------------------------------------------------------------
# Schema de catálogo para el alumno — D3: es_correcta AUSENTE
# ---------------------------------------------------------------------------


class ExamenContenidoResumenResponse(BaseModel):
    """Resumen de examen para el catálogo del alumno/admin.

    Metadatos: id, titulo, cantidad de preguntas y, si el examen tiene comisión
    asociada (D11, NULLABLE), comision_id/comision_nombre/materia_nombre.
    D3: es_correcta AUSENTE — opciones y preguntas no viajan en el listado.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    cantidad_preguntas: int
    comision_id: str | None = None
    comision_nombre: str | None = None
    comision_codigo: str | None = None
    materia_nombre: str | None = None
    materia_codigo: str | None = None
    # Config por examen para gatear "Rendir" por ventana/intentos (migración 0032).
    apertura: datetime | None = None
    cierre: datetime | None = None
    tiempo_limite_min: int | None = None
    intentos_permitidos: int = 1


class ExamenesContenidoPaginadosResponse(BaseModel):
    """Catálogo de exámenes paginado (C-69 admin-sync, tarea 4).

    Forma estándar de paginación serverside: la página de items + el total global
    filtrado (no solo el de la página). El frontend usa `items`; `total` permite
    construir el paginador. D3: es_correcta AUSENTE en cada item.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ExamenContenidoResumenResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Schemas de rendición — D3: es_correcta AUSENTE en todos (nunca viaja al cliente)
# ---------------------------------------------------------------------------


class OpcionRendicionResponse(BaseModel):
    """Opción de respuesta para la rendición del alumno (sin es_correcta — D3)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    orden: int
    # D3: es_correcta AUSENTE — la opción correcta NUNCA viaja al cliente


class BlankRendicionResponse(BaseModel):
    """Hueco de una pregunta cloze para la rendición.

    D3: sin la respuesta correcta. En un blank SHORTANSWER ``opciones`` viene vacío
    a propósito — sus opciones SON las respuestas aceptadas.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    orden: int
    tipo: str
    texto_antes: str
    texto_despues: str
    opciones: list[OpcionRendicionResponse]


class PreguntaRendicionResponse(BaseModel):
    """Pregunta para la rendición del alumno."""

    model_config = ConfigDict(extra="forbid")

    id: str
    enunciado: str
    tipo: str
    orden: int
    opciones: list[OpcionRendicionResponse]
    # Solo poblado en preguntas cloze.
    blanks: list[BlankRendicionResponse] = []


class ExamenRendicionResponse(BaseModel):
    """Examen de contenido proyectado para la rendición del alumno.

    Incluye la config POR EXAMEN que el front usa al rendir: ``tiempo_limite_min``
    (timer; null = sin límite), ``mezclar_preguntas`` (shuffle) y la escala de la
    nota (``nota_maxima``/``nota_aprobacion``) para mostrarla. D3: SIN es_correcta.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    preguntas: list[PreguntaRendicionResponse]
    tiempo_limite_min: int | None = None
    mezclar_preguntas: bool = False
    nota_maxima: float = 10.0
    nota_aprobacion: float = 6.0


# ---------------------------------------------------------------------------
# Schemas de REVISIÓN post-examen — SÍ exponen es_correcta (excepción a D3):
# solo al dueño y con el intento YA FINALIZADO (como "Review options" de Moodle).
# ---------------------------------------------------------------------------


class OpcionRevisionResponse(BaseModel):
    """Opción en la revisión: marca la correcta y la que eligió el alumno."""

    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    orden: int
    es_correcta: bool
    elegida: bool


class BlankRevisionResponse(BaseModel):
    """Blank (hueco) de una pregunta cloze en la revisión."""

    model_config = ConfigDict(extra="forbid")

    blank_id: str
    orden: int
    tipo: str
    texto_antes: str | None = None
    texto_despues: str | None = None
    respuesta_alumno: str | None = None
    es_correcta: bool


class PreguntaRevisionResponse(BaseModel):
    """Pregunta en la revisión con su corrección."""

    model_config = ConfigDict(extra="forbid")

    id: str
    enunciado: str
    orden: int
    opciones: list[OpcionRevisionResponse]
    respondida: bool
    acertada: bool
    tipo: str = "multichoice"
    blanks_revisados: list[BlankRevisionResponse] = []


class RevisionExamenResponse(BaseModel):
    """Revisión completa del intento finalizado del alumno (corrección + contadores)."""

    model_config = ConfigDict(extra="forbid")

    examen_id: str
    titulo: str
    nota: float | None = None
    nota_maxima: float | None = None
    aprobado: bool = False
    total_preguntas: int
    correctas: int
    incorrectas: int
    sin_responder: int
    finalizada_en: datetime | None = None
    preguntas: list[PreguntaRevisionResponse]
    # Visibilidad (C-69). disponible=False → sin resultados (nota no visible aún).
    # revision_disponible=False → contadores sí, preguntas vacío (corrección oculta).
    disponible: bool = True
    revision_disponible: bool = True
    cierre: datetime | None = None


# ---------------------------------------------------------------------------
# Pool de preguntas seleccionables (C-69, opción B) — endpoints admin
# ---------------------------------------------------------------------------


class PreguntaPoolItemResponse(BaseModel):
    """Pregunta del pool para la pantalla de selección del docente (opción B).

    D3: es_correcta y opciones AUSENTES — el docente identifica por enunciado.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    enunciado: str
    tipo: str
    orden: int
    seleccionada: bool


class PreguntasPoolResponse(BaseModel):
    """Pool completo de un examen + conteos (total del pool y seleccionadas)."""

    model_config = ConfigDict(extra="forbid")

    items: list[PreguntaPoolItemResponse]
    total: int
    seleccionadas: int
    # True si el examen ya tiene un intento FINALIZADO: la selección queda CONGELADA
    # (cambiarla alteraría retroactivamente la nota, que cuenta solo las seleccionadas).
    # La UI usa esto para deshabilitar el editor de selección con un aviso.
    bloqueada: bool = False


class PreguntasSeleccionRequest(BaseModel):
    """Body para fijar qué preguntas del pool forman el examen (opción B).

    ``seleccionadas`` = ids de las preguntas que quedan seleccionadas; el resto del
    pool del examen queda deseleccionado. Debe resultar en >= 1 seleccionada (422).
    """

    model_config = ConfigDict(extra="forbid")

    seleccionadas: list[str]


class SorteoRequest(BaseModel):
    """Body para armar examen por sorteo aleatorio de categorías (C-74 §3).

    ``categoria_ids``: lista de ids de categorías de las que se sortea.
    ``cantidad_por_categoria``: cuántas preguntas se sortean de CADA categoría.
    """

    model_config = ConfigDict(extra="forbid")

    categoria_ids: list[str]
    cantidad_por_categoria: int


class SorteoCategoriaItem(BaseModel):
    """Un tramo del sorteo: categoría + cantidad de preguntas a extraer del banco."""

    model_config = ConfigDict(extra="forbid")

    categoria_id: str | None = None  # None = "Sin clasificar"
    cantidad: int = Field(ge=1)
    # Elegir "Unidad 1" normalmente significa "todo lo de Unidad 1", incluidos sus
    # temas. Por eso el default incluye la descendencia completa. En False, sortea
    # SOLO lo que cuelga directo de esa categoría, sin bajar a las subcategorías.
    incluir_subcategorias: bool = True
    # None = cualquier tipo de la categoría. Con lista, solo sortea de esos tipos
    # (ej. ["multichoice"] para dejar afuera las cloze de la misma categoría).
    tipos: list[str] | None = None


class CrearDesdebancoRequest(BaseModel):
    """Crea un examen de contenido extrayendo preguntas aleatoriamente del banco.

    El examen se genera en un solo paso: no requiere importar XML ni hacer sorteo
    por separado. Cada item de ``sorteo`` indica cuántas preguntas extraer de
    una categoría del banco (None = sin clasificar).
    """

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=1, max_length=200)
    materia_id: str
    comision_id: str | None = None
    sorteo: list[SorteoCategoriaItem] = Field(min_length=1)
    limite_preguntas: int | None = Field(default=None, ge=1)
    # Escala de calificación: configurable por examen (migración 0061). Default
    # 100/60 si no se manda — nunca cae silenciosamente en "sobre 10". El docente
    # puede elegir otra escala acá mismo, al crear, sin un PATCH /config aparte.
    nota_maxima: float = Field(default=100.0, gt=0)
    nota_aprobacion: float = Field(default=60.0, ge=0)


class CrearDesdebancoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examen_id: str
    titulo: str
    total_preguntas: int


# ---------------------------------------------------------------------------
# Materia + comisión (C-69 sección 6, D11) — endpoints admin
# ---------------------------------------------------------------------------


class MateriaInlineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str


class ComisionInlineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    periodo: PeriodoEnum | None = None
    anio: int | None = None


class AltaInlineRequest(BaseModel):
    """Alta inline de materia + comisión; opcionalmente asocia un examen."""

    model_config = ConfigDict(extra="forbid")

    materia: MateriaInlineRequest
    comision: ComisionInlineRequest
    examen_id: str | None = None


class MateriaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    codigo: str
    nombre: str
    # C-72 §17: estado de la materia (true = activa; false = congelada).
    activa: bool = True
    # Conteos para que la UI oculte "Eliminar" cuando la materia NO está vacía
    # (mismo criterio que el guard de borrado: se elimina solo con ambos en 0).
    total_inscriptos: int = 0
    total_examenes: int = 0


class ComisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    materia_id: str
    codigo: str
    nombre: str
    periodo: str | None = None
    anio: int | None = None
    # C-70: código de matriculación (enrolment key) — el docente lo comparte.
    codigo_matriculacion: str
    # C-72 §17 (nivel comisión): true = activa; false = congelada (baja lógica).
    activa: bool = True
    # Conteos para que la UI oculte "Eliminar" cuando la comisión NO está vacía
    # (mismo criterio que el guard de borrado: se elimina solo con ambos en 0).
    total_inscriptos: int = 0
    total_examenes: int = 0
    # C-73 §9: docente a cargo. Es quien devuelve la nota de los exámenes de esta
    # comisión y contra quién se valida "lo suyo" del rol DOCENTE. None = sin asignar
    # (el write-back cae a la credencial institucional). El nombre viaja resuelto para
    # que la UI no tenga que pedir el usuario aparte.
    docente_id: str | None = None
    docente_nombre: str | None = None


class AltaInlineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materia: MateriaResponse
    comision: ComisionResponse
    examen_id: str | None = None


class ComisionConMateriaResponse(BaseModel):
    """Comisión + su materia embebida, para un selector combinado único
    ("CÓDIGO - Materia") que no requiere elegir materia primero."""

    model_config = ConfigDict(extra="forbid")

    id: str
    codigo: str
    nombre: str
    periodo: str | None = None
    anio: int | None = None
    materia_id: str
    materia_nombre: str
    materia_codigo: str


class MateriaCrearRequest(BaseModel):
    """Body del POST /materias: alta de una materia (gestión independiente)."""

    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str


class MateriaActivaRequest(BaseModel):
    """Body del PATCH /materias/{id}/activa: activar (true) o desactivar (false)."""

    model_config = ConfigDict(extra="forbid")

    activa: bool


class MateriaActualizarRequest(BaseModel):
    """Body del PATCH /materias/{id}: nombre y (opcionalmente) codigo.

    `codigo` es editable: no es la identidad de la fila (esa es el id UUID) sino un
    atributo único. Si se omite, el codigo vigente se preserva. Un codigo repetido
    lo rechaza el service con 409 'duplicado'.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str
    codigo: str | None = None


class ComisionCrearRequest(BaseModel):
    """Body del POST /materias/{id}/comisiones: alta de una comisión en la materia."""

    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    periodo: PeriodoEnum | None = None
    anio: int | None = None
    # C-70: código de matriculación opcional. Si no viene → se autogenera único
    # ({materia.codigo}-{sufijo}); si viene → se usa tal cual (unicidad al persistir).
    codigo_matriculacion: str | None = None


class ComisionDocenteRequest(BaseModel):
    """Body del PUT /comisiones/{id}/docente: asigna el docente a cargo (C-73 §9).

    ``docente_id = None`` DESASIGNA. No es un caso de error: una comisión puede quedar
    sin docente (el write-back de sus exámenes cae a la credencial institucional).
    """

    model_config = ConfigDict(extra="forbid")

    docente_id: str | None = None


class ComisionActivaRequest(BaseModel):
    """Body del PATCH /comisiones/{id}/activa: activar (true) o desactivar (false)."""

    model_config = ConfigDict(extra="forbid")

    activa: bool


class ComisionActualizarRequest(BaseModel):
    """Body del PATCH /comisiones/{id}: nombre/periodo/anio mutables; codigo y
    materia_id inmutables."""

    model_config = ConfigDict(extra="forbid")

    nombre: str
    periodo: PeriodoEnum | None = None
    anio: int | None = None
    # C-70: el docente puede fijar/editar el código de matriculación (unicidad al
    # persistir). None → no se toca el código vigente.
    codigo_matriculacion: str | None = None


class AsociarComisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comision_id: str


class AsociarComisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examen_id: str
    comision_id: str


# ---------------------------------------------------------------------------
# Inscripción de alumnos a comisiones + elegibilidad (C-69) — endpoints admin
# ---------------------------------------------------------------------------


class InscribirAlumnoRequest(BaseModel):
    """Body del POST /comisiones/{id}/inscripciones: inscribe un alumno."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: str


class InscripcionResponse(BaseModel):
    """Inscripción creada (alumno↔comisión)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    usuario_id: str
    comision_id: str


class InscribirPorCodigoRequest(BaseModel):
    """Body del POST /inscribirme: el alumno se auto-matricula con un código (C-70).

    El ``usuario_id`` NO viaja en el body — sale del principal autenticado (D3,
    cliente no confiable). Solo el código de matriculación.
    """

    model_config = ConfigDict(extra="forbid")

    codigo_matriculacion: str


class InscribirPorCodigoResponse(BaseModel):
    """Resultado de la auto-matriculación por código (C-70).

    ``ya_inscripto`` = True cuando el alumno ya estaba matriculado en esa comisión
    (respuesta idempotente amistosa, no error). ``comision_*``/``materia_nombre``
    identifican a qué quedó (o ya estaba) matriculado.
    """

    model_config = ConfigDict(extra="forbid")

    comision_id: str
    comision_nombre: str
    materia_nombre: str
    ya_inscripto: bool


class AlumnoElegibilidadResponse(BaseModel):
    """Alumno inscripto a una comisión + su elegibilidad para rendir.

    ``puede_rendir`` = consentimiento_vigente AND biometria_vigente. ``razon`` es
    null cuando puede rendir; cuando no, describe qué falta.
    """

    model_config = ConfigDict(extra="forbid")

    usuario_id: str
    id_institucional: str
    nombre: str | None = None
    apellido: str | None = None
    email: str
    consentimiento_vigente: bool
    biometria_vigente: bool
    puede_rendir: bool
    razon: str | None = None


# ---------------------------------------------------------------------------
# Destino del write-back a Moodle POR EXAMEN (C-69, D12 parte B)
# ---------------------------------------------------------------------------


class MoodleTargetRequest(BaseModel):
    """Body para fijar el destino de write-back de un examen.

    Ambos NULLABLE: enviar null limpia el destino y vuelve al fallback global.
    extra='forbid' (regla dura de código).
    """

    model_config = ConfigDict(extra="forbid")

    moodle_courseid: int | None = None
    moodle_cmid: int | None = None


class MoodleTargetResponse(BaseModel):
    """Destino de write-back a Moodle de un examen (estado actual tras el update)."""

    model_config = ConfigDict(extra="forbid")

    examen_id: str
    moodle_courseid: int | None = None
    moodle_cmid: int | None = None


# ---------------------------------------------------------------------------
# Configuración del examen POR EXAMEN (C-69, migración 0032) — endpoints admin
# ---------------------------------------------------------------------------


class ExamenConfigResponse(BaseModel):
    """Los campos de configuración de un examen (GET /{id}/config)."""

    model_config = ConfigDict(extra="forbid")

    tiempo_limite_min: int | None = None
    intentos_permitidos: int
    apertura: datetime | None = None
    cierre: datetime | None = None
    nota_maxima: float
    nota_aprobacion: float
    # Siempre true (migración 0046). Se sigue exponiendo para que la UI pueda
    # informarlo, pero ya no es editable.
    mezclar_preguntas: bool
    limite_preguntas: int | None = None
    # Visibilidad de resultados (C-69, migración 0036).
    mostrar_nota: str = "al_cerrar"
    revision_habilitada: bool = False
    politica_intentos: PoliticaIntentos = PoliticaIntentos.MAS_ALTA
    # True si el examen ya tiene >= 1 intento finalizado: la config de
    # mecánica/nota queda CONGELADA (el front deshabilita esos campos).
    bloqueada: bool = False
    # C-72 sección 6 (candado direccional): detalle para que el front sepa qué
    # deshabilitar y qué solo se puede ampliar. Vacíos si el examen no fue rendido.
    campos_congelados: list[str] = []          # congelado duro: no editables
    campos_solo_ampliables: list[str] = []     # cierre (extender), intentos (aumentar)


class ExamenConfigPatchRequest(BaseModel):
    """Body del PATCH /{id}/config: los 7 campos, TODOS opcionales (update parcial).

    extra='forbid' (regla dura de código). Solo los campos presentes en el body se
    actualizan; los demás conservan su valor actual. Validaciones (→ 422) sobre el
    resultado mergeado las hace la capa de aplicación/dominio.
    """

    model_config = ConfigDict(extra="forbid")

    tiempo_limite_min: int | None = None
    intentos_permitidos: int | None = None
    apertura: datetime | None = None
    cierre: datetime | None = None
    nota_maxima: float | None = None
    nota_aprobacion: float | None = None
    # `mezclar_preguntas` NO se acepta: es siempre true (migracion 0046). Con
    # extra='forbid', mandarlo devuelve 422 en vez de aceptarlo en silencio.
    # Tope de preguntas del examen. None en el body = no se toca; para sacar el
    # tope se manda 0 (se normaliza a NULL en la capa de aplicacion).
    limite_preguntas: int | None = Field(default=None, ge=0)
    # Visibilidad de resultados (C-69). mostrar_nota: 'al_cerrar' | 'inmediata'.
    mostrar_nota: Literal["al_cerrar", "inmediata"] | None = None
    revision_habilitada: bool | None = None
    politica_intentos: PoliticaIntentos | None = None


# ---------------------------------------------------------------------------
# Resultados del examen + sincronización a Moodle (C-69 admin-sync, tareas 2-3)
# ---------------------------------------------------------------------------


class ResultadoAlumnoResponse(BaseModel):
    """Fila de resultados de un examen para el admin.

    L2.5 / D3: NUNCA incluye es_correcta ni respuestas — solo identidad del alumno,
    nota académica y estado del envío a Moodle.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    alumno_idnumber: str | None = None
    alumno_email: str | None = None
    alumno_nombre: str | None = None
    nota: float | None = None
    estado_moodle: str  # pendiente | enviado | fallido | sin_token
    # Motivo por el que la nota queda RETENIDA y no se sincroniza (gate D15):
    # en_riesgo | anulada. None = nada la retiene.
    retenido_por: str | None = None
    actualizado_en: datetime | None = None


class ResultadosExamenPaginadosResponse(BaseModel):
    """Resultados de un examen paginados (forma estándar { items, total, page, page_size })."""

    model_config = ConfigDict(extra="forbid")

    items: list[ResultadoAlumnoResponse]
    total: int
    page: int
    page_size: int


class SincronizarMoodleResponse(BaseModel):
    """Resultado de la sincronización manual de notas a Moodle disparada por el admin."""

    model_config = ConfigDict(extra="forbid")

    enviadas: int
    fallidas: int
    sin_token: int
    total: int
    mensaje: str | None = None


# ---------------------------------------------------------------------------
# "Mis notas" del alumno (C-69, student-facing)
# ---------------------------------------------------------------------------


class MiNotaResponse(BaseModel):
    """Una nota finalizada del alumno + estado de envío a Moodle + estado L2.5.

    ``en_cola_revision`` (L2.5): True si el score de proctoring de la sesión supera
    el umbral de cola de revisión (``score >= umbral_revision``). El score PRIORIZA
    la revisión humana; NUNCA es una sanción.
    L2.5 / D3: NUNCA incluye es_correcta ni respuestas.
    """

    model_config = ConfigDict(extra="forbid")

    examen_id: str
    examen_titulo: str
    nota: float | None = None
    # Escala de la nota del examen (migración 0032) y si el alumno aprobó
    # (nota >= nota_aprobacion del examen). aprobado = False si no hay nota.
    nota_maxima: float | None = None
    aprobado: bool = False
    estado_moodle: str  # pendiente | enviado | fallido | sin_token
    en_cola_revision: bool
    score: float | None = None
    umbral_revision: float | None = None
    eventos: int
    finalizada_en: datetime | None = None
    # Visibilidad de resultados (C-69). Si nota_visible=False, ``nota`` viene None y
    # la UI muestra "disponible al cerrar el examen (cierre)".
    nota_visible: bool = True
    revision_disponible: bool = False
    cierre: datetime | None = None
    # Veredicto de resolución (C-71 slice 2, D11b/D12). El alumno lo ve por PULL.
    # ``nota_anulada``: efecto derivado del último acto (reversible, hook c-18).
    # ``informe_disponible``: True SOLO si la nota fue anulada por fraude —
    # habilita el informe de devolución (minimización, Ley 25.326).
    session_id: str
    nota_anulada: bool = False
    veredicto: str | None = None
    informe_disponible: bool = False


class MisNotasResponse(BaseModel):
    """Notas finalizadas del alumno autenticado (forma { items, total })."""

    model_config = ConfigDict(extra="forbid")

    items: list[MiNotaResponse]
    total: int


class SenalAnalisisResponse(BaseModel):
    """Una señal (detector) re-inferida server-side, agregada por tipo (C-71 D12)."""

    model_config = ConfigDict(extra="forbid")

    tipo: str
    severidad: str
    ocurrencias: int
    face_count_servidor: int | None = None
    veredicto_reinferencia: str


class CapturaFirmadaResponse(BaseModel):
    """Captura de evidencia accesible por URL firmada (C-71 D12).

    Incluye de QUÉ evento salió: sin eso el alumno recibe una lista de imágenes
    numeradas que no puede relacionar con ninguna de las señales que se le
    imputan — y son justamente la prueba con la que tendría que defenderse.
    """

    model_config = ConfigDict(extra="forbid")

    object_key: str
    url: str
    expires_in: int
    tipo_evento: str | None = None
    severidad: str | None = None
    ocurrio_en: object | None = None


class InformeDevolucionResponse(BaseModel):
    """Informe de devolución del alumno (SOLO nota anulada, C-71 D12, un solo paso).

    Disclosure de debido proceso: decisión + motivo + análisis por señal
    (server-side) + capturas firmadas (SOLO la evidencia que el revisor eligió
    al decidir, no toda la sesión). Minimización: este recurso solo existe
    para sesiones anuladas del propio titular (Ley 25.326).
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    decision: str
    motivo: str | None = None
    senales: list[SenalAnalisisResponse]
    capturas: list[CapturaFirmadaResponse]

