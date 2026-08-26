"""Cache del JWKS de cada Platform LTI, y fuera del bucle de eventos.

Por qué existe
-------------
Medido el 26/8/2026 con ``tools/carga/avalancha-lti.py``, 70 alumnos entrando a
la vez por el link de Moodle: el JWKS se bajaba **70 veces** (una por launch),
cada alumno tardaba **8 s** en entrar, y el servidor se degradó de 8 ms a
**4075 ms** para todo lo demás — incluidos los que ya estaban rindiendo.

La causa es la misma que la de bcrypt: ``httpx.get`` es sincrónico y se llamaba
derecho dentro de una corrutina. Mientras bajaba el JWKS del campus, el bucle de
eventos quedaba congelado.

Dos arreglos, no uno
--------------------
- **Cache por ``jwks_uri``** con TTL: el JWKS de un campus cambia cuando rota sus
  claves, o sea casi nunca. Bajarlo por launch no tenía ningún sentido.
- **Bajada en un hilo** (``asyncio.to_thread``): el cache no alcanza. El primer
  alumno del día siempre encuentra el cache frío, y con la bajada dentro de la
  corrutina ese primer launch congela a todos igual.

Y single-flight: 70 alumnos llegando juntos con el cache frío no son 70 bajadas.
Sin eso, la primera avalancha del día pega N veces contra el campus a la vez —
justo cuando el campus también está saturado.

Es distinto de ``infrastructure/auth/jwks_cache.py``, que cachea el JWKS ÚNICO de
Keycloak de forma sincrónica. Acá hay N Platforms, cada uno con su URI, y se
resuelve dentro de un handler async.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass

JwksDoc = dict


@dataclass
class _Entrada:
    doc: JwksDoc
    bajado_en: float
    # Cuándo se refrescó por última vez por un `kid` que faltaba. Sin esto, un
    # token con un kid inventado dispararía una bajada por intento: un
    # amplificador de tráfico contra el campus, gratis para quien lo mande.
    refresco_por_kid_en: float = 0.0


def _tiene_kid(doc: JwksDoc, kid: str) -> bool:
    return any(k.get("kid") == kid for k in doc.get("keys", []))


class JwksPlatformCache:
    """Cache TTL por ``jwks_uri``, con la bajada fuera del bucle de eventos."""

    def __init__(
        self,
        fetcher: Callable[[str], JwksDoc],
        *,
        ttl_seg: int = 3600,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._ttl = ttl_seg
        self._time = time_fn
        self._entradas: dict[str, _Entrada] = {}
        # Un lock por URI: dos campus distintos no tienen por qué esperarse.
        self._locks: dict[str, asyncio.Lock] = {}

    async def obtener(self, jwks_uri: str, *, requiere_kid: str | None = None) -> JwksDoc:
        """El JWKS del campus. ``requiere_kid`` fuerza un refresco si falta ese kid.

        Ese refresco cubre el riesgo que introduce el cache: si el campus rota
        sus claves, el JWKS viejo dejaría fallar TODOS los launches hasta que
        venza el TTL.
        """
        vigente = self._vigente(jwks_uri, requiere_kid=requiere_kid)
        if vigente is not None:
            return vigente

        lock = self._locks.setdefault(jwks_uri, asyncio.Lock())
        async with lock:
            # Otro que esperaba el mismo lock ya pudo haberlo bajado.
            vigente = self._vigente(jwks_uri, requiere_kid=requiere_kid)
            if vigente is not None:
                return vigente

            ahora = self._time()
            anterior = self._entradas.get(jwks_uri)
            doc = await self._bajar(jwks_uri)
            # Si la bajada falla, la excepción sube y NO se guarda nada: un campus
            # caído no puede dejar el cache envenenado para cuando vuelva.
            self._entradas[jwks_uri] = _Entrada(
                doc=doc,
                bajado_en=ahora,
                refresco_por_kid_en=(
                    ahora
                    if requiere_kid is not None and anterior is not None
                    else (anterior.refresco_por_kid_en if anterior else 0.0)
                ),
            )
            return doc

    def _vigente(
        self, jwks_uri: str, *, requiere_kid: str | None = None
    ) -> JwksDoc | None:
        entrada = self._entradas.get(jwks_uri)
        if entrada is None:
            return None
        if (self._time() - entrada.bajado_en) >= self._ttl:
            return None
        if requiere_kid is not None and not _tiene_kid(entrada.doc, requiere_kid):
            # Falta el kid: vale UN refresco. Si ya se refrescó hace poco por
            # esta misma razón, el kid sencillamente no existe — se devuelve lo
            # cacheado y que la validación de la firma lo rechace.
            if entrada.refresco_por_kid_en >= entrada.bajado_en:
                return entrada.doc
            return None
        return entrada.doc

    async def _bajar(self, jwks_uri: str) -> JwksDoc:
        if inspect.iscoroutinefunction(self._fetcher):
            return await self._fetcher(jwks_uri)
        # El fetcher de producción es `httpx.get`, sincrónico. A un hilo: es la
        # línea que evita que una ida y vuelta al campus congele el servidor.
        return await asyncio.to_thread(self._fetcher, jwks_uri)

    def invalidar(self, jwks_uri: str) -> None:
        """Olvida el JWKS de un campus (rotación de claves detectada)."""
        self._entradas.pop(jwks_uri, None)
