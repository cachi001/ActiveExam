"""Validacion LOCAL de JWT contra el JWKS cacheado (infraestructura, C-06 D2).

Flujo:
1. Decodifica el header del JWT (sin verificar) para leer ``kid`` y ``alg``.
2. Resuelve la clave publica via ``JwksCache.get_jwk(kid)`` (sin round-trip si
   esta cacheada).
3. Verifica firma + expiracion + ``aud`` con la lib (RS256 por defecto).
4. Delega la POLITICA de claims (issuer/audiencia/MFA/mapeo) al dominio
   (``TokenPolicy.principal_desde_claims``), que es puro.

La verificacion criptografica se inyecta como callable (``verify_fn``) para no
acoplar el flujo a una lib concreta y para poder testear con una firma simetrica
(HS256) sin red ni PyJWT. En produccion el callable usa PyJWT+JWKS (RS256). Si
PyJWT no esta instalado, el import de la fabrica RS256 falla EXPLICITO al
construirla (no en import-time), de modo que el resto del modulo (y los tests con
``verify_fn`` inyectado) funciona sin la dependencia.

Esta pieza vive en infraestructura; el dominio nunca la importa.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache

# Una funcion de verificacion: (token, jwk, audience, issuer) -> claims dict.
# Levanta UnauthenticatedError si la firma/exp/aud son invalidos.
VerifyFn = Callable[[str, dict | None, str, str], dict]


def _b64url_decode(segment: str) -> bytes:
    """Decodifica un segmento base64url (con padding tolerante)."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_unverified_header(token: str) -> dict:
    """Lee el header del JWT SIN verificar la firma (solo para resolver ``kid``)."""
    try:
        header_b64 = token.split(".", 1)[0]
        return json.loads(_b64url_decode(header_b64))
    except Exception as exc:  # noqa: BLE001 - cualquier malformacion -> 401
        raise UnauthenticatedError("Header de JWT malformado.") from exc


class JwtValidator:
    """Valida un JWT localmente y devuelve el ``AuthenticatedPrincipal`` de dominio."""

    def __init__(
        self,
        *,
        jwks_cache: JwksCache,
        policy: TokenPolicy,
        verify_fn: VerifyFn,
    ) -> None:
        self._jwks = jwks_cache
        self._policy = policy
        self._verify = verify_fn

    def validar(self, token: str) -> AuthenticatedPrincipal:
        """Valida firma/exp/aud/iss y devuelve el principal de dominio (D2).

        Lanza ``UnauthenticatedError`` (-> 401) ante firma invalida, expiracion,
        audiencia/issuer incorrectos o token malformado."""
        if not token:
            raise UnauthenticatedError("Token vacio.")
        header = decode_unverified_header(token)
        kid = header.get("kid")
        jwk = self._jwks.get_jwk(kid) if kid else None
        # La verificacion criptografica (firma + exp + aud) la hace ``verify_fn``.
        claims = self._verify(token, jwk, self._policy.audience, self._policy.issuer)
        # La politica de claims (issuer/audiencia/MFA/mapeo) es dominio puro.
        return self._policy.principal_desde_claims(claims)
