"""Validacion LOCAL de JWT contra el JWKS cacheado (infraestructura, C-06 D2 / C-55).

Flujo original (C-06, RS256 Keycloak):
1. Decodifica el header del JWT (sin verificar) para leer ``kid`` y ``alg``.
2. Resuelve la clave publica via ``JwksCache.get_jwk(kid)`` (sin round-trip si
   esta cacheada).
3. Verifica firma + expiracion + ``aud`` con la lib (RS256).
4. Delega la POLITICA de claims al dominio (``TokenPolicy.principal_desde_claims``).

Flujo multi-issuer (C-55, HS256 propio + RS256 Keycloak):
1. Decodifica el header Y el payload (ambos sin verificar) para leer ``alg``,
   ``kid`` e ``iss``.
2. Despacha al ``verify_fn`` correcto:
   - alg=HS256 + iss=JWT_OWN_ISSUER  → ``verify_fn_hs256`` (secreto simetrico)
   - alg=RS256 + iss=KEYCLOAK_ISSUER → ``verify_fn_rs256`` (JWKS cacheado)
   - cualquier otra combinacion → ``UnauthenticatedError`` (401)
3. La politica de claims (ahora con ``issuers_aceptados: frozenset``) valida issuer
   y audiencia; el resto del mapeo es identico.

La verificacion criptografica se inyecta como callable (``verify_fn``) para no
acoplar el flujo a una lib concreta y para poder testear sin red. Si se inyecta
un solo ``verify_fn`` (modo C-06 legacy), el validador funciona como antes — el
campo ``verify_fn_hs256`` queda en None y el despacho va directo a ``verify_fn``.

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


def _decode_unverified_payload(token: str) -> dict:
    """Lee el payload del JWT SIN verificar la firma (para leer ``iss`` antes de verificar)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:  # noqa: PLR2004
            raise ValueError("JWT no tiene 3 segmentos.")
        return json.loads(_b64url_decode(parts[1]))
    except Exception as exc:  # noqa: BLE001
        raise UnauthenticatedError("Payload de JWT malformado.") from exc


class JwtValidator:
    """Valida un JWT localmente y devuelve el ``AuthenticatedPrincipal`` de dominio.

    Soporta dos modos:
    - Legacy (C-06): un solo ``verify_fn`` (RS256). Se construye con
      ``verify_fn=fn_rs256`` y ``verify_fn_hs256=None``.
    - Multi-issuer (C-55): dos ``verify_fn`` (HS256 propio + RS256 Keycloak).
      El despacho es por ``alg`` del header + ``iss`` del payload.
    """

    def __init__(
        self,
        *,
        jwks_cache: JwksCache,
        policy: TokenPolicy,
        verify_fn: VerifyFn,
        verify_fn_hs256: VerifyFn | None = None,
        own_issuer: str | None = None,
        keycloak_issuer: str | None = None,
    ) -> None:
        self._jwks = jwks_cache
        self._policy = policy
        self._verify_rs256 = verify_fn  # fn RS256 (Keycloak o legacy)
        self._verify_hs256 = verify_fn_hs256  # fn HS256 (provider propio, C-55)
        self._own_issuer = own_issuer
        self._keycloak_issuer = keycloak_issuer

    def validar(self, token: str) -> AuthenticatedPrincipal:
        """Valida firma/exp/aud/iss y devuelve el principal de dominio.

        En modo multi-issuer (C-55): lee ``alg`` del header e ``iss`` del payload
        sin verificar, despacha al verify_fn correcto, rechaza combinaciones no
        reconocidas con ``UnauthenticatedError``.

        En modo legacy (C-06, verify_fn_hs256=None): comportamiento anterior.

        Lanza ``UnauthenticatedError`` (-> 401) ante cualquier invalides.
        """
        if not token:
            raise UnauthenticatedError("Token vacio.")
        header = decode_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg", "")

        # Modo multi-issuer (C-55): despachar por alg+iss.
        if self._verify_hs256 is not None:
            payload_sin_verificar = _decode_unverified_payload(token)
            iss = payload_sin_verificar.get("iss", "")

            if alg == "HS256" and iss == self._own_issuer:
                # Token propio: verificar con secreto simetrico (sin JWKS).
                claims = self._verify_hs256(
                    token, None, self._policy.audience, self._own_issuer or ""
                )
            elif alg == "RS256" and iss == self._keycloak_issuer:
                # Token Keycloak: verificar con JWKS cacheado (comportamiento C-06).
                jwk = self._jwks.get_jwk(kid) if kid else None
                claims = self._verify_rs256(
                    token, jwk, self._policy.audience, self._keycloak_issuer or ""
                )
            else:
                # Combinacion alg+iss no reconocida: rechazar sin revelar config.
                raise UnauthenticatedError(
                    "Combinacion de alg/iss del token no reconocida."
                )
        else:
            # Modo legacy (C-06): un solo verify_fn, behavior anterior.
            jwk = self._jwks.get_jwk(kid) if kid else None
            claims = self._verify_rs256(token, jwk, self._policy.audience, self._policy.issuer)

        # La politica de claims (issuer/audiencia/MFA/mapeo) es dominio puro.
        return self._policy.principal_desde_claims(claims)
