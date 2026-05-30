"""Capa de presentacion de auth (FastAPI, C-06).

Traduce el dominio de auth a HTTP:
- ``dependencies``: extrae y valida el JWT (Bearer), construye el principal y
  expone guards reutilizables (``require_roles``, ``require_mfa``). Mapea los
  errores de dominio a 401/403.
- ``router``: ``POST /api/v1/auth/refresh`` (rotacion) y endpoints de auth.
- ``realtime``: guard de handshake WS/SSE (validacion + revalidacion periodica).
"""

from __future__ import annotations
