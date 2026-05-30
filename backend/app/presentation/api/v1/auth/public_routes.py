"""Lista CANONICA de rutas publicas minimas (presentacion, C-06 D6).

`03` §Rutas publicas marca la lista como no especificada en la fuente; este change
la FIJA en su minimo: login institucional (redireccion a Keycloak) y estaticos del
frontend. Todo el resto de la API y los canales de tiempo real exigen JWT.

``POST /api/v1/auth/refresh`` NO es estrictamente publica: opera CON token
(refresh), por eso no figura en la lista publica aunque no exija un access token.

Esta lista es la fuente unica que Nginx (rate limiting + exencion de auth) y los
middlewares consumen; mantenerla aqui evita divergencias.
"""

from __future__ import annotations

# Prefijos de ruta que NO exigen JWT (superficie publica minima, D6).
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/health/live",   # liveness (Nginx saca instancias caidas, DD-10)
    "/api/v1/health/ready",  # readiness (orquestador / Nginx pooling)
    "/auth/login",           # inicio de login institucional (redireccion a Keycloak)
    "/docs",                 # OpenAPI UI (en prod puede cerrarse por entorno)
    "/openapi.json",
    "/static",               # estaticos del frontend
)

# Rutas que operan CON token aunque no exijan un access token (no son publicas).
TOKEN_BACKED_PATHS: tuple[str, ...] = ("/api/v1/auth/refresh",)


def es_ruta_publica(path: str) -> bool:
    """``True`` si la ruta esta en la superficie publica minima (no exige JWT)."""
    return any(path.startswith(p) for p in PUBLIC_PATH_PREFIXES)
