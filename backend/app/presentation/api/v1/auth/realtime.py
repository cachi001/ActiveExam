"""Auth de handshake WS/SSE y revalidacion periodica (presentacion, C-06 D5).

Los canales de larga vida (WebSocket del estudiante, SSE del panel) no pueden
confiar para siempre en el token inicial:
- ``authenticate_handshake``: valida el JWT al CONECTAR; sin token valido el
  handshake se rechaza (no se establece el canal).
- ``RealtimeRevalidator``: durante la conexion, cada ``periodo`` revalida el token;
  si expiro/se revoco, la revalidacion falla y el canal debe cortarse.

El token en el handshake llega por query param (``?access_token=...``) o por
subprotocolo, porque el navegador no permite cabeceras custom en el handshake WS.
Esta pieza es de presentacion; delega la validacion al ``JwtValidator`` (infra) y
la politica al dominio.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.auth.jwt_validator import JwtValidator


def extract_token_from_query(query_params: dict[str, str]) -> str | None:
    """Toma el token del handshake (``access_token`` o ``token`` en el query)."""
    return query_params.get("access_token") or query_params.get("token")


def authenticate_handshake(
    validator: JwtValidator,
    token: str | None,
) -> AuthenticatedPrincipal:
    """Valida el JWT del handshake; sin token valido levanta 401 (rechazo, D5)."""
    if not token:
        raise UnauthenticatedError("Handshake WS/SSE sin token: rechazado.")
    return validator.validar(token)


class RealtimeRevalidator:
    """Revalida periodicamente el token de una conexion de larga vida (D5).

    Mantiene el ultimo token validado y el timestamp de la ultima revalidacion. En
    cada ``tick`` decide si toca revalidar; si el token dejo de ser valido, propaga
    el error para que el canal se corte."""

    def __init__(
        self,
        validator: JwtValidator,
        *,
        periodo_seg: int,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._validator = validator
        self._periodo = periodo_seg
        self._time = time_fn
        self._ultima_revalidacion: float = self._time()

    def debe_revalidar(self) -> bool:
        """``True`` si paso el periodo de revalidacion desde la ultima."""
        return (self._time() - self._ultima_revalidacion) >= self._periodo

    def revalidar(self, token: str) -> AuthenticatedPrincipal:
        """Revalida el token; si dejo de ser valido, propaga ``UnauthenticatedError``
        (el caller corta la conexion). En exito, reinicia el reloj del periodo."""
        principal = self._validator.validar(token)  # lanza si expiro/revoco
        self._ultima_revalidacion = self._time()
        return principal
