"""Validación del launch LTI 1.3 (C-75, sección 4 — núcleo de seguridad).

Un launch es de confianza SÓLO si TODO se cumple, o se rechaza sin efectos:
  1. El `(iss, deployment_id)` está en la allowlist `lti_deployment_confiable`
     con `activo=True` (design D2). El `client_id` esperado sale de esa fila —
     NO se confía en el `aud` del token para elegir contra qué validar.
  2. La firma RS256 del `id_token` valida contra el JWKS de Moodle (`jwks_uri`
     de la fila). El material de clave viene de Moodle, no del cliente.
  3. `aud == client_id` registrado, `exp`/`iat` en ventana (los valida PyJWT).
  4. El `nonce` existe, su `state` coincide con el recibido, no está vencido y
     NO fue consumido (anti-replay, design D5). Se marca `consumido_en` de forma
     atómica: un segundo launch con el mismo token/nonce se rechaza.

El cliente es un sensor no confiable (regla de dominio #6): nada de lo que llega
por el navegador se cree hasta pasar 1-4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.lti import (
    LtiDeploymentConfiableModel,
    LtiNonceModel,
)

CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"

# Tolerancia de desincronización de reloj entre el Platform (Moodle) y el Tool al
# validar exp/iat/nbf. OIDC (y por herencia LTI 1.3) recomienda explícitamente
# admitir un pequeño skew: en la práctica los servidores nunca están perfectamente
# sincronizados (acá se vio ~60-90 s de drift entre Moodle y el contenedor). El
# anti-replay real lo da el `nonce` de un solo uso (design D5), no la ventana temporal.
_CLOCK_SKEW_LEEWAY_SEG = 300

JwksFetcher = Callable[[str], dict]


class LaunchInvalidoError(Exception):
    """Launch LTI rechazado. ``codigo`` es un slug estable para la API/logs."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class LaunchValidado:
    """Resultado de un launch válido: los claims verificados + el deployment."""

    claims: dict
    deployment: LtiDeploymentConfiableModel


def _default_jwks_fetcher(jwks_uri: str) -> dict:
    """Trae el JWKS de Moodle por HTTP. Aislado para poder inyectarlo en tests.

    SINCRÓNICO a propósito: nunca se llama derecho desde una corrutina, siempre
    a través de ``JwksPlatformCache``, que lo manda a un hilo. Llamarlo directo
    congela el servidor entero mientras dura la ida y vuelta al campus (c-78,
    medido: 70 alumnos entrando a la vez degradaron todo de 8 ms a 4075 ms).
    """
    import httpx

    return httpx.get(jwks_uri, timeout=10).json()


# Cache compartido por proceso. Se arma perezosamente y por fetcher, para que un
# fetcher inyectado en tests no herede el cache del de producción ni al revés.
#
# Se guarda el fetcher junto al cache a propósito: la clave es su `id()`, y un
# `id()` se reusa cuando el objeto se recolecta. Manteniendo la referencia viva,
# la clave no puede pasar a apuntar a otro fetcher. Son un puñado de fetchers
# distintos por proceso (uno en producción), así que no crece.
_caches_por_fetcher: dict[int, tuple[JwksFetcher, "JwksPlatformCache"]] = {}


def _cache_de(fetcher: JwksFetcher) -> "JwksPlatformCache":
    from app.infrastructure.lti.jwks_platform_cache import JwksPlatformCache

    clave = id(fetcher)
    entrada = _caches_por_fetcher.get(clave)
    if entrada is None:
        entrada = (fetcher, JwksPlatformCache(fetcher))
        _caches_por_fetcher[clave] = entrada
    return entrada[1]


def _signing_key(jwks: dict, id_token: str):
    """Devuelve la clave pública del JWKS cuyo ``kid`` coincide con el header."""
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except Exception as exc:  # noqa: BLE001
        raise LaunchInvalidoError("token_ilegible") from exc
    if not kid:
        raise LaunchInvalidoError("kid_ausente")
    try:
        jwk_set = jwt.PyJWKSet.from_dict(jwks)
    except Exception as exc:  # noqa: BLE001
        raise LaunchInvalidoError("jwks_invalido") from exc
    for clave in jwk_set.keys:
        if clave.key_id == kid:
            return clave.key
    raise LaunchInvalidoError("kid_desconocido")


async def validar_launch(
    session: AsyncSession,
    *,
    id_token: str,
    state: str,
    jwks_fetcher: JwksFetcher = _default_jwks_fetcher,
) -> LaunchValidado:
    """Valida un launch LTI end-to-end. Lanza ``LaunchInvalidoError`` ante cualquier
    fallo, sin crear ni loguear a nadie. Devuelve los claims verificados si pasa."""
    ahora = datetime.now(timezone.utc)

    # 1. Leer iss/deployment_id SIN verificar (sólo para elegir contra qué validar).
    try:
        crudo = jwt.decode(id_token, options={"verify_signature": False})
    except Exception as exc:  # noqa: BLE001
        raise LaunchInvalidoError("token_ilegible") from exc

    iss = crudo.get("iss")
    deployment_id = crudo.get(CLAIM_DEPLOYMENT_ID)
    if not iss or not deployment_id:
        raise LaunchInvalidoError("claims_incompletos")

    # 2. Allowlist: el client_id esperado sale de la fila, no del token.
    deployment = (
        await session.execute(
            select(LtiDeploymentConfiableModel).where(
                LtiDeploymentConfiableModel.iss == iss,
                LtiDeploymentConfiableModel.deployment_id == deployment_id,
                LtiDeploymentConfiableModel.activo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if deployment is None:
        raise LaunchInvalidoError("deployment_no_confiable")

    # 3-4. Firma contra el JWKS de Moodle + aud/exp vía PyJWT.
    #
    # Vía el cache, SIEMPRE: cachea por `jwks_uri` y manda la bajada a un hilo.
    # Llamar al fetcher acá derecho es lo que congelaba el servidor entero con
    # 70 alumnos entrando a la vez (c-78).
    # El `kid` del token se le pasa al cache para que un campus que rotó sus
    # claves fuerce UN refresco en vez de dejar fallar todos los launches hasta
    # que venza el TTL.
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except Exception as exc:  # noqa: BLE001
        raise LaunchInvalidoError("token_ilegible") from exc

    jwks = await _cache_de(jwks_fetcher).obtener(
        deployment.jwks_uri, requiere_kid=kid
    )
    clave = _signing_key(jwks, id_token)
    try:
        claims = jwt.decode(
            id_token,
            clave,
            algorithms=["RS256"],
            audience=deployment.client_id,
            leeway=_CLOCK_SKEW_LEEWAY_SEG,
            options={"require": ["exp", "iat", "nonce", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise LaunchInvalidoError("token_expirado") from exc
    except jwt.InvalidAudienceError as exc:
        raise LaunchInvalidoError("audiencia_invalida") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise LaunchInvalidoError("claims_incompletos") from exc
    except jwt.InvalidTokenError as exc:  # incluye firma inválida
        raise LaunchInvalidoError("firma_invalida") from exc

    # 5. Nonce: existe, state coincide, vigente y NO consumido (anti-replay).
    nonce_row = (
        await session.execute(
            select(LtiNonceModel).where(LtiNonceModel.nonce == claims["nonce"])
        )
    ).scalar_one_or_none()
    if (
        nonce_row is None
        or nonce_row.state != state
        or nonce_row.consumido_en is not None
        or nonce_row.expira_en < ahora
    ):
        raise LaunchInvalidoError("nonce_invalido")

    # Consumo atómico: cualquier reuso posterior cae en consumido_en != None.
    nonce_row.consumido_en = ahora
    await session.commit()

    return LaunchValidado(claims=claims, deployment=deployment)
