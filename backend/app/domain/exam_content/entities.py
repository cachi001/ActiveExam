"""Entidades de dominio para el contenido de examen (C-69).

Reglas de dominio (NON-NEGOTIABLE):
- D3: es_correcta NUNCA sale al cliente; vive server-side.
- D11: comision_id NULLABLE — un examen sin comisión es válido.
- multichoice: >= 2 opciones, exactamente 1 correcta.
- truefalse: exactamente 2 opciones, exactamente 1 correcta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PoliticaIntentos(str, Enum):
    """Qué nota se envía a Moodle cuando el alumno tiene múltiples intentos."""
    MAS_ALTA = "mas_alta"
    ULTIMO   = "ultimo"
    PRIMERO  = "primero"
    MANUAL   = "manual"


from app.domain.exam_content.errors import (
    ComisionInvalidaError,
    MateriaInvalidaError,
    PreguntaInvalidaError,
)


@dataclass(frozen=True, slots=True)
class OpcionRespuesta:
    """Opción de respuesta de una pregunta.

    es_correcta: NUNCA se expone al cliente (D3 / regla dura #6).
    """

    texto: str
    es_correcta: bool
    id: str | None = None
    orden: int = 0


@dataclass(frozen=True, slots=True)
class Pregunta:
    """Pregunta de un examen de contenido.

    Validaciones de dominio en __post_init__ (frozen=True obliga a usar
    object.__setattr__ internamente, pero dataclass lo maneja solo en el init).
    """

    enunciado: str
    tipo: str
    opciones: tuple[OpcionRespuesta, ...]
    id: str | None = None
    orden: int = 0
    # Opción B (pool de preguntas): si el docente la seleccionó para el examen.
    # Default True (compat): una pregunta recién importada cuenta como seleccionada.
    seleccionada: bool = True

    def __post_init__(self) -> None:
        self._validar()

    def _validar(self) -> None:
        correctas = sum(1 for o in self.opciones if o.es_correcta)

        if self.tipo == "multichoice":
            if len(self.opciones) < 2:
                raise PreguntaInvalidaError(
                    f"multichoice requiere >= 2 opciones; tiene {len(self.opciones)}"
                )
            if correctas != 1:
                raise PreguntaInvalidaError(
                    f"multichoice exige exactamente 1 correcta; tiene {correctas}"
                )

        elif self.tipo == "truefalse":
            if len(self.opciones) != 2:
                raise PreguntaInvalidaError(
                    f"truefalse exige exactamente 2 opciones; tiene {len(self.opciones)}"
                )
            if correctas != 1:
                raise PreguntaInvalidaError(
                    f"truefalse exige exactamente 1 correcta; tiene {correctas}"
                )

        else:
            if correctas < 1:
                raise PreguntaInvalidaError(
                    f"Toda pregunta necesita al menos 1 opción correcta; tipo='{self.tipo}'"
                )


@dataclass(frozen=True, slots=True)
class ExamenContenido:
    """Examen de contenido con sus preguntas.

    comision_id es NULLABLE (D11): un examen sin comisión es válido y rendible.
    """

    titulo: str
    preguntas: tuple[Pregunta, ...]
    id: str | None = None
    comision_id: str | None = None
    # D12 (parte B): destino del write-back de nota a Moodle POR EXAMEN. NULLABLE —
    # si quedan en None, el write-back usa el valor global de config_slim (fallback).
    moodle_courseid: int | None = None
    moodle_cmid: int | None = None
    moodle_component: str | None = None
    # Configuración del examen POR EXAMEN (migración 0032). ActiveExam la opera; el
    # alumno rinde con estos parámetros. Defaults compat: 1 intento, nota sobre 10,
    # aprueba con 6, sin ventana ni límite, sin mezclar.
    tiempo_limite_min: int | None = None  # None = sin límite
    intentos_permitidos: int = 1
    apertura: datetime | None = None  # None = sin apertura
    cierre: datetime | None = None  # None = sin cierre
    nota_maxima: float = 10.0
    nota_aprobacion: float = 6.0
    # Siempre true: el orden aleatorio por alumno protege la integridad de la
    # rendicion y no altera la nota (solo cambia el ORDEN, no que preguntas entran).
    mezclar_preguntas: bool = True
    # Tope de preguntas del examen. None = sin tope.
    limite_preguntas: int | None = None
    # Visibilidad de resultados (migración 0036, gate estilo Moodle "Review options").
    mostrar_nota: str = "al_cerrar"  # 'al_cerrar' | 'inmediata'
    revision_habilitada: bool = False
    politica_intentos: PoliticaIntentos = PoliticaIntentos.MAS_ALTA


@dataclass(frozen=True, slots=True)
class PreguntaSeleccionItem:
    """Item del pool de preguntas para la pantalla de selección del docente (opción B).

    Read-model liviano: el docente identifica la pregunta por su ENUNCIADO.
    D3: es_correcta AUSENTE — no viaja al cliente ni en la selección.
    """

    id: str
    enunciado: str
    tipo: str
    orden: int
    seleccionada: bool


@dataclass(frozen=True, slots=True)
class Materia:
    """Materia académica (D11).

    `codigo` es único a nivel DB (no se modela aquí); el dominio exige que
    `codigo` y `nombre` estén presentes.
    """

    codigo: str
    nombre: str
    id: str | None = None
    # C-72 §17: estado de la materia (true = activa; false = congelada).
    activa: bool = True

    def __post_init__(self) -> None:
        if not (self.codigo and self.codigo.strip()):
            raise MateriaInvalidaError("La materia requiere un codigo no vacío.")
        if not (self.nombre and self.nombre.strip()):
            raise MateriaInvalidaError("La materia requiere un nombre no vacío.")


@dataclass(frozen=True, slots=True)
class Comision:
    """Comisión de una materia (D11).

    Una comisión pertenece a EXACTAMENTE una materia: `materia_id` es
    obligatorio. `periodo`/`cuatrimestre` y `anio` son opcionales. La unicidad
    de (`materia_id`, `codigo`) se garantiza a nivel DB.
    """

    codigo: str
    nombre: str
    materia_id: str | None = None
    periodo: str | None = None
    anio: int | None = None
    id: str | None = None
    # C-70: código de matriculación (enrolment key). None en el dominio hasta que
    # la capa de aplicación lo autogenere/valide antes de persistir; el modelo ORM
    # lo exige NOT NULL. Se guarda tal cual (solo strip externo, case-sensitive).
    codigo_matriculacion: str | None = None
    # C-72 §17 (nivel comisión): true = activa; false = congelada. Congelar UNA
    # comisión no congela la materia ni las demás comisiones.
    activa: bool = True

    def __post_init__(self) -> None:
        if not (self.materia_id and self.materia_id.strip()):
            raise ComisionInvalidaError(
                "Toda comisión pertenece a exactamente una materia: materia_id es obligatorio."
            )
        if not (self.codigo and self.codigo.strip()):
            raise ComisionInvalidaError("La comisión requiere un codigo no vacío.")
        if not (self.nombre and self.nombre.strip()):
            raise ComisionInvalidaError("La comisión requiere un nombre no vacío.")


@dataclass(frozen=True, slots=True)
class ExamenContenidoResumen:
    """Resumen de un examen de contenido para el catálogo del alumno/admin.

    Read-model liviano para el listado: solo metadatos, sin preguntas ni opciones.
    D3: es_correcta ausente (aplica al detalle; aquí no hay preguntas).

    comision_id / comision_nombre / materia_nombre son NULLABLE (D11): un examen
    sin comisión asociada los deja en None; con comisión, se derivan transitivamente
    (examen → comisión → materia).
    """

    id: str
    titulo: str
    cantidad_preguntas: int
    comision_id: str | None = None
    comision_nombre: str | None = None
    materia_nombre: str | None = None
    # Config por examen que el front usa para gatear "Rendir" por ventana/intentos
    # (migración 0032). apertura/cierre/tiempo_limite_min son NULLABLE.
    apertura: datetime | None = None
    cierre: datetime | None = None
    tiempo_limite_min: int | None = None
    intentos_permitidos: int = 1
