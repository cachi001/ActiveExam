"""Casos de uso de configuracion de examen (aplicacion, C-07).

Orquestan las entidades de C-05 (``Examen``, ``Asignacion``) y los puertos de
repositorio para implementar el CRUD admin, habilitados, asignacion de proctores,
foto de referencia y calendarizacion. La validacion de parametros (D4) vive aqui,
no en la presentacion. No reabren el modelo de datos (C-05).
"""

from __future__ import annotations
