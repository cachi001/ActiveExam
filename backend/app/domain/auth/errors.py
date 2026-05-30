"""Errores de auth de DOMINIO (PURO).

El dominio expresa los fallos de autorizacion/autenticacion como excepciones
PROPIAS, sin acoplarse a ``fastapi.HTTPException`` (eso traduce la capa de
presentacion a 401/403). Asi la regla de negocio (proctor fuera de asignacion,
MFA no satisfecho) se testea sin framework.

Mapeo en presentacion:
- ``UnauthenticatedError`` -> 401 (no hay principal valido).
- ``ForbiddenError``       -> 403 (hay principal pero no le alcanza el contexto).
- ``MfaRequiredError``     -> 403 (falta segundo factor; subtipo de Forbidden).
"""

from __future__ import annotations


class AuthError(Exception):
    """Raiz de los errores de auth de dominio."""


class UnauthenticatedError(AuthError):
    """No hay un principal autenticado valido (-> 401)."""


class ForbiddenError(AuthError):
    """El principal existe pero no esta autorizado para el recurso/contexto (-> 403)."""


class MfaRequiredError(ForbiddenError):
    """El principal no satisfizo el segundo factor exigido por su rol (-> 403)."""
