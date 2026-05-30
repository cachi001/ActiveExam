"""Cache del JWKS de Keycloak (infraestructura, C-06 D2).

El JWT se valida LOCALMENTE contra la clave publica de Keycloak; para no hacer un
round-trip por request, el JWKS (`KEYCLOAK_JWKS_URL`) se cachea con TTL y se
refresca de forma perezosa. Si llega un ``kid`` desconocido (rotacion de claves de
Keycloak), se fuerza un refresco unico antes de fallar.

Esta pieza vive en infraestructura (toca red/lib); el dominio nunca la importa.
La descarga concreta se inyecta como callable (``fetch_jwks``) para poder testear
el cache sin red.
"""

from __future__ import annotations

import time
from collections.abc import Callable

JwksDoc = dict  # {"keys": [ {kid, kty, n, e, ...}, ... ]}


class JwksCache:
    """Cache TTL del documento JWKS con refresco perezoso y por ``kid`` faltante."""

    def __init__(
        self,
        fetch_jwks: Callable[[], JwksDoc],
        *,
        ttl_seconds: int = 3600,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch_jwks
        self._ttl = ttl_seconds
        self._time = time_fn
        self._doc: JwksDoc | None = None
        self._fetched_at: float = 0.0

    def _expirado(self) -> bool:
        return self._doc is None or (self._time() - self._fetched_at) >= self._ttl

    def _refrescar(self) -> None:
        self._doc = self._fetch()
        self._fetched_at = self._time()

    def get_jwk(self, kid: str) -> dict | None:
        """Devuelve la JWK del ``kid`` pedido (refresca si expiro o si falta el kid).

        Un ``kid`` ausente fuerza UN refresco (rotacion de claves); si tras el
        refresco sigue ausente, devuelve ``None`` (token con kid invalido)."""
        if self._expirado():
            self._refrescar()
        jwk = self._buscar(kid)
        if jwk is None:
            # Posible rotacion: refresca una vez mas y reintenta.
            self._refrescar()
            jwk = self._buscar(kid)
        return jwk

    def _buscar(self, kid: str) -> dict | None:
        if not self._doc:
            return None
        for key in self._doc.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None
