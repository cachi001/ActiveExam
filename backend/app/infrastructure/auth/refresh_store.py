"""Rotacion de refresh tokens (infraestructura, C-06 D2).

``POST /api/v1/auth/refresh`` delega en Keycloak el grant ``refresh_token``; pero
la POLITICA de ROTACION (un refresh usado queda invalidado, no se puede reusar) se
modela aqui como un store con jti+rotacion. En produccion Keycloak ya rota los
refresh si el cliente esta configurado para ello; este store ofrece una capa local
de defensa (detecta reuso de un refresh ya rotado) y es lo que los tests ejercen
sin red.

Interfaz minima: ``rotate(old)`` valida que ``old`` este vigente, lo invalida y
emite uno nuevo; ``is_valid(token)`` consulta vigencia. La implementacion en
memoria sirve para tests; la de produccion se respalda en Keycloak/almacen
persistente (fuera del scope de C-06, que fija el contrato).
"""

from __future__ import annotations

import secrets
from abc import ABC, abstractmethod


class RefreshTokenError(Exception):
    """El refresh token es invalido o ya fue rotado (-> 401 en el endpoint)."""


class RefreshTokenStore(ABC):
    """Puerto de rotacion de refresh tokens."""

    @abstractmethod
    def issue(self) -> str:
        """Emite un refresh token nuevo y lo marca como vigente."""

    @abstractmethod
    def is_valid(self, token: str) -> bool:
        """``True`` si el token esta vigente (no rotado/invalidado)."""

    @abstractmethod
    def rotate(self, old: str) -> str:
        """Invalida ``old`` y emite uno nuevo. Lanza ``RefreshTokenError`` si
        ``old`` no esta vigente (reuso de un refresh ya rotado)."""


class InMemoryRefreshTokenStore(RefreshTokenStore):
    """Store en memoria con rotacion (para tests / instancia unica).

    NO persiste entre instancias (mono-hilo, DD-10): la version de produccion se
    respalda en Keycloak/almacen compartido. La SEMANTICA de rotacion (un refresh
    usado no se reusa) es la misma y es lo que se prueba."""

    def __init__(self) -> None:
        self._vigentes: set[str] = set()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self._vigentes.add(token)
        return token

    def is_valid(self, token: str) -> bool:
        return token in self._vigentes

    def rotate(self, old: str) -> str:
        if old not in self._vigentes:
            raise RefreshTokenError("Refresh token invalido o ya rotado.")
        self._vigentes.discard(old)  # invalida el usado (rotacion)
        return self.issue()
