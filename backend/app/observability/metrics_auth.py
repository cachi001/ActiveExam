"""Credencial de scrape para `/metrics`, compartida por los dos main.

Hay DOS aplicaciones que exponen `/metrics` — `main_activeexam.py` (la que corre
en produccion) y `main.py` (el stack full) — y el endpoint estaba abierto en las
dos. La politica vive aca, en un solo lugar, para que cerrar una no deje la otra
abierta.
"""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request

ENV_TOKEN = "METRICS_TOKEN"


def exigir_credencial_de_scrape(request: Request) -> None:
    """Corta el request si no trae la credencial de scrape.

    El cuerpo de `/metrics` no es inocuo: el label `path` del histograma publica
    el catalogo completo de rutas de la API, los contadores publican el volumen
    de trafico y las metricas de proceso publican memoria y CPU. Abierto, es
    reconocimiento gratis (asi estaba en Render hasta la medicion del 25/8/2026).

    Politica, en dos escalones:
      - `METRICS_TOKEN` vacio o ausente -> 404, el endpoint queda DESHABILITADO.
        Fail closed a proposito: olvidarse la variable en un entorno nuevo no
        puede volver a dejarlo publico. El 404 ademas no delata que exista.
      - `METRICS_TOKEN` presente -> exige `Authorization: Bearer <token>`. Es el
        esquema que Prometheus habla nativo (`authorization` / `bearer_token` en
        el scrape_config), asi que no hace falta un sidecar ni un proxy.

    La variable se lee EN CADA REQUEST, no al construir la app: rotar el token es
    reiniciar el proceso, no reconstruir la aplicacion.
    """
    esperado = os.getenv(ENV_TOKEN, "").strip()
    if not esperado:
        raise HTTPException(status_code=404)

    cabecera = request.headers.get("authorization", "")
    esquema, _, recibido = cabecera.partition(" ")
    # compare_digest en vez de `==`: el tiempo de comparacion no debe filtrar
    # cuantos caracteres del token acerto quien prueba.
    if esquema.lower() != "bearer" or not secrets.compare_digest(
        recibido.strip(), esperado
    ):
        raise HTTPException(
            status_code=401,
            detail="Credencial de scrape invalida.",
            headers={"WWW-Authenticate": "Bearer"},
        )
