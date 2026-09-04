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

import uuid
from collections.abc import Iterable
from dataclasses import replace

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text as sa_text

from app.domain.auth import authorization
from app.domain.auth.errors import (
    ForbiddenError,
    MfaRequiredError,
    UnauthenticatedError,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol, parse_rol
from app.infrastructure.auth.estado_cuenta import CACHE_ESTADO_CUENTA, EstadoCuenta
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


#: Lo único que puede hacer quien todavía no definió sus credenciales: enterarse de
#: que está en ese estado y salir de él. Se compara por sufijo para no atarse al
#: prefijo con el que esté montado el router.
_RUTAS_PERMITIDAS_SIN_CREDENCIALES = (
    "/auth/me",              # la app necesita saber que debe mostrar la pantalla
    "/auth/change-password", # la salida del estado
    "/auth/refresh",         # renovar la sesión mientras la resuelve
    "/auth/logout",          # irse siempre tiene que poder
)


def _puede_sin_credenciales_definidas(path: str) -> bool:
    return any(path.endswith(sufijo) for sufijo in _RUTAS_PERMITIDAS_SIN_CREDENCIALES)


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
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    validator: JwtValidator = Depends(get_validator),
) -> AuthenticatedPrincipal:
    """Valida el Bearer y devuelve el principal (401 si falta/invalido, D2).

    Además corta con 403 a quien todavía no definió sus credenciales propias, salvo
    en las rutas que le permiten resolverlo. Antes ese gate vivía SOLO en el
    navegador (``RequireAuth``): con el token del launch LTI se podía operar la API
    entera sin haber elegido usuario ni contraseña. Regla dura #6 — un control que
    solo corre en el cliente no es un control.

    Va acá y no endpoint por endpoint a propósito: todos los guards
    (``require_roles``, ``require_capability``, ``require_mfa``) pasan por esta
    función, así que el que se agregue mañana queda cubierto solo.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Falta el Bearer token.")
    try:
        principal = validator.validar(credentials.credentials)
    except UnauthenticatedError as exc:
        raise _unauthorized(str(exc)) from exc

    if principal.credenciales_pendientes and not _puede_sin_credenciales_definidas(
        request.url.path
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "credenciales_pendientes",
                "mensaje": (
                    "Tenés que elegir tu usuario y contraseña antes de usar el "
                    "sistema."
                ),
            },
        )

    return await _con_estado_vigente(request, principal)


def _es_uuid(valor: str | None) -> bool:
    """El ``sub`` solo se usa como id de usuario si de verdad es un UUID.

    Un subject que no lo es (otro emisor, un token de servicio) reventaría la
    consulta con un DataError de asyncpg. Mismo patrón que el resto del proyecto.
    """
    if not valor:
        return False
    try:
        uuid.UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


async def _con_estado_vigente(
    request: Request, principal: AuthenticatedPrincipal
) -> AuthenticatedPrincipal:
    """Contrasta el token contra la BASE: baja y roles vigentes.

    El token dura 15 minutos y lleva los roles adentro. Sin esto, dar de baja a
    alguien o quitarle un rol no surtía efecto hasta que su token venciera.

    Dos decisiones deliberadas:

    - **Solo se rechaza ante evidencia POSITIVA de revocación** (la fila existe y
      tiene ``eliminado_en``). Si no hay fila que mirar, no hay nada que afirmar:
      el token está firmado y es válido, y no todo emisor usa el id local como
      subject. Inventar un 401 ahí cerraría caminos legítimos sin ganar nada.
    - **Si la consulta falla, se deja pasar.** Es una verificación EXTRA sobre un
      token que ya fue validado criptográficamente; que un hipo de la base saque a
      una comisión entera de su examen sería un remedio peor que la enfermedad.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None or not _es_uuid(principal.subject):
        return principal

    usuario_id = str(principal.subject)

    async def _cargar() -> EstadoCuenta | None:
        async with session_factory() as session:
            fila = (
                await session.execute(
                    sa_text(
                        "SELECT eliminado_en, roles FROM usuario WHERE id = :id"
                    ),
                    {"id": usuario_id},
                )
            ).first()
        if fila is None:
            return None
        eliminado_en, roles = fila
        return EstadoCuenta(
            activa=eliminado_en is None,
            roles=tuple(roles or ()),
        )

    try:
        estado = await CACHE_ESTADO_CUENTA.obtener(usuario_id, _cargar)
    except Exception:  # noqa: BLE001 — ver docstring: se deja pasar.
        return principal

    if estado is None:
        return principal
    if not estado.activa:
        raise _unauthorized("La cuenta fue dada de baja.")

    # La base manda sobre el token: un rol quitado hace efecto ya, sin esperar los
    # 15 minutos. Se reemplazan SIEMPRE (no solo al quitar): si le agregaron un rol
    # tampoco tiene por qué esperar.
    #
    # SALVO que la fila no tenga roles cargados. Una lista vacía no es "le quitaron
    # todo": es un dato ausente, y dejar sin permisos a alguien por eso es inventar
    # una revocación que nadie decidió. Mismo criterio que el `sub` sin fila.
    if not estado.roles:
        return principal

    roles_vigentes = tuple(
        r for r in (parse_rol(nombre) for nombre in estado.roles) if r is not None
    )
    if roles_vigentes == principal.roles:
        return principal
    return replace(principal, roles=roles_vigentes)


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


def require_capability(capacidad: str):
    """Factory de dependencia: exige la ``capacidad`` indicada (403 si no,
    c-71 slice 2 D8). Config-driven via ``CAPABILITY_ROLES`` -- reasignar la
    capacidad a otro rol no requiere tocar el endpoint que usa este guard."""

    async def _guard(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        try:
            authorization.exigir_capacidad(principal, capacidad)
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
