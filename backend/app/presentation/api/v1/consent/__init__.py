"""Presentacion del consentimiento informado (FastAPI, C-08).

Endpoints para el estudiante autenticado (C-06):
- ``GET  /api/v1/consent/text``         -> texto vigente (cinco bloques + version).
- ``POST /api/v1/consent``              -> registra el acuse (422 sin accion afirmativa).
- ``POST /api/v1/consent/alternative``  -> elige via alternativa (escala a proctor).
- ``GET  /api/v1/consent/gate``         -> estado del gate (consumible por C-09).

Pydantic ``extra='forbid'`` (regla dura). Errores de dominio -> 422/403.
"""

from __future__ import annotations
