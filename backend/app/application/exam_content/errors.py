"""Errores de aplicación del módulo exam_content (importación Moodle)."""

from __future__ import annotations


class MoodleXmlInvalidoError(Exception):
    """El XML no pudo parsearse (malformado o no es XML)."""


class MoodleXmlVacioError(Exception):
    """El XML es válido pero no contiene preguntas de tipo soportado."""


class ExamenNoEncontradoError(Exception):
    """No existe un examen de contenido con el id indicado."""


class ComisionNoEncontradaError(Exception):
    """No existe una comisión con el id indicado."""


class MateriaNoEncontradaError(Exception):
    """No existe una materia con el id indicado."""


class UsuarioNoEncontradoError(Exception):
    """No existe un usuario activo con el id indicado."""


class InscripcionNoEncontradaError(Exception):
    """No existe una inscripción del usuario a la comisión indicada."""


class CodigoMatriculacionInvalidoError(Exception):
    """El codigo_matriculacion enviado no corresponde a ninguna comisión (C-70).

    Se eleva en la auto-matriculación del alumno cuando el código no mapea a una
    comisión existente. El endpoint lo traduce a 404 (no se crea ninguna inscripción).
    """
