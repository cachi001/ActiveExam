"""Presentacion de configuracion de examen (FastAPI, C-07).

Routers admin-only + MFA (guards de C-06) sobre los casos de uso de
``application.exam_config``. La validacion de parametros vive en aplicacion/dominio
(D4); aqui solo se deserializa (Pydantic ``extra='forbid'``) y se mapean los
errores de dominio a HTTP (422 ante config invalida).
"""

from __future__ import annotations
