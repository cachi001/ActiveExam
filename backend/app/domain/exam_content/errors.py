"""Errores de dominio del módulo exam_content."""

from __future__ import annotations


class ExamenContenidoError(Exception):
    """Error base del dominio de contenido de examen."""


class PreguntaInvalidaError(ExamenContenidoError):
    """Pregunta no cumple las reglas de dominio (opciones, correcta, tipo)."""


class MateriaInvalidaError(ExamenContenidoError):
    """Materia no cumple las reglas de dominio (codigo/nombre requeridos)."""


class ComisionInvalidaError(ExamenContenidoError):
    """Comisión no cumple las reglas de dominio.

    Incluye el caso de una comisión sin materia: toda comisión pertenece a
    EXACTAMENTE una materia (D11).
    """


class SeleccionInvalidaError(ExamenContenidoError):
    """La selección del pool dejaría el examen sin ninguna pregunta seleccionada.

    Opción B: un examen necesita al menos 1 pregunta seleccionada para ser rendible.
    """


class ConfigExamenInvalidaError(ExamenContenidoError):
    """La configuración del examen viola una regla de validación (→ 422).

    Reglas: intentos_permitidos >= 1; nota_maxima > 0; 0 <= nota_aprobacion <=
    nota_maxima; si apertura y cierre están seteados, apertura < cierre;
    tiempo_limite_min null o > 0.
    """


class MateriaDuplicadaError(ExamenContenidoError):
    """Ya existe una materia con el mismo codigo (unicidad de codigo)."""


class ComisionDuplicadaError(ExamenContenidoError):
    """Ya existe una comisión con el mismo codigo dentro de la materia.

    Viola la unicidad de (materia_id, codigo).
    """
