"""Cliente Moodle REST — fachada.

Este archivo tenia 809 lineas y NUEVE metodos publicos haciendo tres trabajos
distintos: escribir notas, resolver identidades y leer metadata de la actividad.
El largo era el sintoma; el problema era una clase con tres responsabilidades.

Ahora cada responsabilidad vive en su modulo y `MoodleRestClient` solo las
compone:

    transporte.py  credencial, excepciones y el unico POST al WS de Moodle
    notas.py       escritura de la nota (los dos caminos + el selector)
    identidad.py   alumno -> moodle_userid
    actividad.py   instance id, escala y notas ya cargadas

POR QUE UNA FACHADA Y NO COMPOSICION EXPLICITA:
  Con `self._notas.escribir_nota(...)` habria que tocar todos los llamadores
  (`writeback_service`, `wiring`, y los tests). Componiendo por herencia, la
  superficie publica no cambia ni una linea: el split es un refactor puro y los
  tests existentes son la prueba de que no rompio nada.

Los nombres se re-exportan desde aca a proposito: `from ...moodle.client import
MoodleClientConfig, MoodleGradeWriteError, ...` sigue funcionando igual.
"""

from __future__ import annotations

from app.infrastructure.moodle.actividad import ActividadMixin
from app.infrastructure.moodle.identidad import IdentidadMixin
from app.infrastructure.moodle.notas import NotasMixin
from app.infrastructure.moodle.transporte import (
    AssignmentGradeConfig,
    MoodleClientConfig,
    MoodleDestinoNoConfiguradoError,
    MoodleEscalaNoSoportadaError,
    MoodleGradeWriteError,
    MoodleTransporte,
    logger,
)

__all__ = [
    "AssignmentGradeConfig",
    "MoodleClientConfig",
    "MoodleDestinoNoConfiguradoError",
    "MoodleEscalaNoSoportadaError",
    "MoodleGradeWriteError",
    "MoodleRestClient",
    "logger",
]


class MoodleRestClient(NotasMixin, IdentidadMixin, ActividadMixin, MoodleTransporte):
    """Cliente async para las Web Services de Moodle.

    El orden de la MRO importa poco (los mixins no se pisan entre si), pero
    `MoodleTransporte` va ULTIMO porque es quien aporta `__init__`,
    `_resolver_config` y `_post_ws` — la base concreta sobre la que los mixins
    se apoyan.

    El token nunca se loguea: se usa solo en el campo `wstoken` del form-data.
    """
