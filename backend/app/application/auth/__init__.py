"""Casos de uso de auth (capa de aplicacion, C-06).

Orquestan dominio + puertos de repositorio: JIT provisioning del Usuario al primer
login federado, y los gates de autorizacion contextual que necesitan resolver
``Asignacion`` (C-05) contra el repositorio. No tocan framework directamente.
"""

from __future__ import annotations
