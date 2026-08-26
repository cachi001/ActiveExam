"""c-78 — El JWKS del Platform LTI: cacheado y fuera del bucle de eventos.

Medido el 26/8/2026 con `tools/carga/avalancha-lti.py`, 70 alumnos entrando a la
vez por el link de Moodle:

  - el JWKS se pedía **70 veces**, una por launch: sin cache
  - cada alumno tardaba **8 s** en entrar (mediana), 10,9 s la avalancha entera
  - y el canario, que mide cómo responde el servidor para TODO lo demás, saltó
    de 8 ms a **4075 ms**

La causa es la misma que la de bcrypt: `httpx.get` es SINCRÓNICO y se llamaba
derecho dentro de una corrutina, así que mientras bajaba el JWKS de Moodle el
bucle de eventos quedaba congelado para todos — incluidos los alumnos que ya
estaban rindiendo.

Este módulo cubre las dos mitades del arreglo:
  1. **Cache por `jwks_uri`** con TTL: N launches del mismo Platform bajan el
     JWKS UNA vez.
  2. **Fuera del bucle**: la bajada corre en un hilo, así que N launches
     concurrentes no se serializan.

Sin red y sin DB: el fetcher se inyecta.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.infrastructure.lti.jwks_platform_cache import JwksPlatformCache

JWKS_A = {"keys": [{"kid": "kid-a", "kty": "RSA", "n": "aaa", "e": "AQAB"}]}
JWKS_B = {"keys": [{"kid": "kid-b", "kty": "RSA", "n": "bbb", "e": "AQAB"}]}


class FetcherEspia:
    """Fetcher sincrónico que cuenta llamadas y puede tardar, como la red real."""

    def __init__(self, doc: dict = JWKS_A, demora_seg: float = 0.0):
        self.doc = doc
        self.demora_seg = demora_seg
        self.llamadas: list[str] = []

    def __call__(self, jwks_uri: str) -> dict:
        self.llamadas.append(jwks_uri)
        if self.demora_seg:
            time.sleep(self.demora_seg)
        return self.doc


@pytest.mark.asyncio
async def test_el_mismo_platform_baja_el_jwks_una_sola_vez():
    espia = FetcherEspia()
    cache = JwksPlatformCache(espia)

    for _ in range(70):
        assert await cache.obtener("https://campus.edu/jwks") == JWKS_A

    assert len(espia.llamadas) == 1, (
        f"70 launches bajaron el JWKS {len(espia.llamadas)} veces: no hay cache"
    )


@pytest.mark.asyncio
async def test_dos_platforms_distintos_no_comparten_cache():
    """Cada campus tiene su propio JWKS: mezclarlos daría `kid_desconocido`."""

    def fetcher(jwks_uri: str) -> dict:
        return JWKS_A if jwks_uri.endswith("/a") else JWKS_B

    cache = JwksPlatformCache(fetcher)

    assert await cache.obtener("https://uno.edu/a") == JWKS_A
    assert await cache.obtener("https://dos.edu/b") == JWKS_B
    assert await cache.obtener("https://uno.edu/a") == JWKS_A


@pytest.mark.asyncio
async def test_vencido_el_ttl_se_vuelve_a_bajar():
    """El campus rota sus claves: el cache no puede ser para siempre."""
    espia = FetcherEspia()
    reloj = {"t": 1000.0}
    cache = JwksPlatformCache(espia, ttl_seg=600, time_fn=lambda: reloj["t"])

    await cache.obtener("https://campus.edu/jwks")
    reloj["t"] += 599
    await cache.obtener("https://campus.edu/jwks")
    assert len(espia.llamadas) == 1, "refrescó antes de vencer el TTL"

    reloj["t"] += 2
    await cache.obtener("https://campus.edu/jwks")
    assert len(espia.llamadas) == 2, "no refrescó después de vencer el TTL"


@pytest.mark.asyncio
async def test_la_bajada_no_congela_el_bucle_de_eventos():
    """Lo que se llevó puesto al servidor con 70 alumnos entrando a la vez.

    Se piden 20 JWKS de Platforms DISTINTOS (o sea, 20 misses: el cache no
    ayuda acá a propósito), cada uno con 100 ms de demora. Si la bajada corre
    derecho en la corrutina, se serializan: 20 × 100 ms = 2 s. En un hilo,
    corren en paralelo y termina en una fracción de eso.

    Y mientras tanto, un "canario" cuenta cuántas veces logró correr: si el
    bucle estuviera bloqueado, no correría casi ninguna.
    """
    espia = FetcherEspia(demora_seg=0.1)
    cache = JwksPlatformCache(espia)

    vueltas = 0
    corriendo = True

    async def canario():
        nonlocal vueltas
        while corriendo:
            vueltas += 1
            await asyncio.sleep(0.005)

    tarea_canario = asyncio.create_task(canario())
    t0 = time.perf_counter()
    await asyncio.gather(*[cache.obtener(f"https://campus{i}.edu/jwks") for i in range(20)])
    transcurrido = time.perf_counter() - t0
    corriendo = False
    await tarea_canario

    assert len(espia.llamadas) == 20, "el test no hizo los 20 misses que pretende"
    assert transcurrido < 1.0, (
        f"20 bajadas de 100 ms tardaron {transcurrido:.2f}s: se serializaron, "
        "o sea que la bajada sigue corriendo dentro del bucle de eventos"
    )
    assert vueltas > 5, (
        f"el canario solo corrio {vueltas} veces: el bucle estuvo bloqueado"
    )


@pytest.mark.asyncio
async def test_una_bajada_en_curso_no_se_duplica():
    """70 alumnos llegando juntos con el cache frío no son 70 bajadas.

    Sin esto, la primera avalancha del día (cache vacío) pega 70 veces contra
    el campus a la vez, que es justo el momento en que el campus también está
    saturado.
    """
    espia = FetcherEspia(demora_seg=0.05)
    cache = JwksPlatformCache(espia)

    await asyncio.gather(*[cache.obtener("https://campus.edu/jwks") for _ in range(70)])

    assert len(espia.llamadas) == 1, (
        f"70 pedidos simultaneos con el cache frio dispararon "
        f"{len(espia.llamadas)} bajadas"
    )


@pytest.mark.asyncio
async def test_un_fetcher_async_tambien_sirve():
    """Los tests de LTI inyectan fetchers propios; algunos pueden ser async."""

    async def fetcher(_jwks_uri: str) -> dict:
        return JWKS_B

    cache = JwksPlatformCache(fetcher)
    assert await cache.obtener("https://campus.edu/jwks") == JWKS_B


@pytest.mark.asyncio
async def test_un_kid_desconocido_fuerza_un_refresco():
    """El riesgo que introduce el cache: el campus rota sus claves.

    Con el JWKS viejo pegado hasta que venza el TTL, TODOS los launches
    fallarían con `kid_desconocido` durante una hora. Un kid que no está fuerza
    un refresco antes de darlo por inválido.
    """
    docs = [JWKS_A, JWKS_B]  # el campus rotó: kid-a pasó a ser kid-b
    llamadas: list[str] = []

    def fetcher(jwks_uri: str) -> dict:
        llamadas.append(jwks_uri)
        return docs[min(len(llamadas) - 1, len(docs) - 1)]

    cache = JwksPlatformCache(fetcher)

    assert await cache.obtener("https://campus.edu/jwks", requiere_kid="kid-a") == JWKS_A
    # Ahora se pide un kid que el JWKS cacheado no tiene.
    assert await cache.obtener("https://campus.edu/jwks", requiere_kid="kid-b") == JWKS_B
    assert len(llamadas) == 2


@pytest.mark.asyncio
async def test_un_kid_que_sigue_sin_estar_no_refresca_para_siempre():
    """Un token con un kid inventado no puede dispararle un pedido al campus
    por cada intento: sería un amplificador de tráfico gratis."""
    espia = FetcherEspia()
    cache = JwksPlatformCache(espia)

    await cache.obtener("https://campus.edu/jwks", requiere_kid="kid-a")
    for _ in range(10):
        await cache.obtener("https://campus.edu/jwks", requiere_kid="kid-inventado")

    assert len(espia.llamadas) <= 2, (
        f"un kid inexistente disparo {len(espia.llamadas)} bajadas"
    )


@pytest.mark.asyncio
async def test_si_la_bajada_falla_no_deja_el_cache_envenenado():
    """Un campus caído no puede dejar rota la validación cuando vuelve."""
    fallas = {"quedan": 1}

    def fetcher(_jwks_uri: str) -> dict:
        if fallas["quedan"] > 0:
            fallas["quedan"] -= 1
            raise RuntimeError("campus caido")
        return JWKS_A

    cache = JwksPlatformCache(fetcher)

    with pytest.raises(RuntimeError):
        await cache.obtener("https://campus.edu/jwks")

    assert await cache.obtener("https://campus.edu/jwks") == JWKS_A
