"""Dependencias FastAPI de auth: extraccion del principal y guards (C-06).

- ``get_current_principal``: extrae el Bearer, valida el JWT localmente (D2) y
  devuelve el ``AuthenticatedPrincipal``. 401 si falta/invalido.
- ``require_roles(...)``: guard por rol (403 si no lo tiene).
- ``require_mfa``: guard de segundo factor para acceso a evidencia/administracion (D4).

Los errores de DOMINIO (``UnauthenticatedError``/``ForbiddenError``/``MfaRequiredError``)
se traducen a ``HTTPException`` 401/403. El ``JwtValidator`` se toma de
``request.app.state.jwt_validator`` (cableado en ``create_app``), de modo que el
dominio nunca depende de FastAPI y los tests inyectan un validador propio.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.auth import authorization
from app.domain.auth.errors import (
    ForbiddenError,
    MfaRequiredError,
    UnauthenticatedError,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.auth.jwt_validator import JwtValidator

# auto_error=False: gestionamos el 401 nosotros para devolver el WWW-Authenticate
# y un cuerpo coherente, sin depender del default de FastAPI.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_validator(request: Request) -> JwtValidator:
    """Toma el ``JwtValidator`` cableado en el app state (o 500 si falta)."""
    validator = getattr(request.app.state, "jwt_validator", None)
    if validator is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subsistema de auth no inicializado.",
        )
    return validator


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    validator: JwtValidator = Depends(get_validator),
) -> AuthenticatedPrincipal:
    """Valida el Bearer y devuelve el principal (401 si falta/invalido, D2)."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Falta el Bearer token.")
    try:
        return validator.validar(credentials.credentials)
    except UnauthenticatedError as exc:
        raise _unauthorized(str(exc)) from exc


def require_roles(*roles: Rol):
    """Factory de dependencia: exige al menos uno de los roles (403 si no)."""
    permitidos = frozenset(roles)

    async def _guard(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        try:
            authorization.exigir_roles(principal, permitidos)
        except ForbiddenError as exc:
            raise _forbidden(str(exc)) from exc
        return principal

    return _guard


async def require_mfa(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """Exige el segundo factor si el rol del principal lo requiere (403, D4)."""
    try:
        authorization.verificar_mfa(principal)
    except MfaRequiredError as exc:
        raise _forbidden(str(exc)) from exc
    return principal


def map_auth_error(exc: Exception) -> HTTPException:
    """Traduce un error de dominio de auth a ``HTTPException`` (401/403).

    Reutilizable por los endpoints/servicios que invocan el RBAC contextual de la
    capa de aplicacion fuera de una dependencia."""
    if isinstance(exc, UnauthenticatedError):
        return _unauthorized(str(exc))
    if isinstance(exc, (ForbiddenError, MfaRequiredError)):
        return _forbidden(str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def require_any_role(roles: Iterable[Rol]):
    """Igual que ``require_roles`` pero recibe un iterable (azucar para listas)."""
    return require_roles(*roles)
