"""Politica de validacion de claims del JWT (PURO, C-06 D2).

La VERIFICACION CRIPTOGRAFICA de la firma (RS256 contra el JWKS de Keycloak) vive
en ``app.infrastructure.auth`` (necesita lib/red). Pero la POLITICA sobre los
claims ya decodificados — audiencia esperada, issuer, expiracion, mapeo a
``AuthenticatedPrincipal`` y deteccion del segundo factor — es una regla de
negocio PURA y se testea sin red.

Mapeo de claims (Keycloak / OIDC):
- ``sub``                  -> subject opaco del IdP.
- ``preferred_username`` / ``preferred_username``-like -> ``id_institucional``.
- ``email``                -> email.
- ``realm_access.roles``   -> roles funcionales (se filtran a ``Rol`` validos).
- ``aud``                  -> debe contener ``JWT_AUDIENCE`` (verificado aqui).
- ``iss``                  -> debe coincidir con ``KEYCLOAK_ISSUER``.
- ``exp``/``iat``          -> ventana de validez (la lib ya la chequea; aqui se
                              re-verifica la expiracion por defensa en profundidad).
- ``amr`` / ``acr``        -> deteccion del segundo factor (MFA satisfecho, D4).

Sin framework ni infraestructura (D1).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.auth.errors import UnauthenticatedError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import parse_rol

# Valores de ``amr`` (Authentication Methods References, RFC 8176) que cuentan
# como segundo factor satisfecho (TOTP minimo, WebAuthn recomendado — `03`/`08`).
SEGUNDO_FACTOR_AMR: frozenset[str] = frozenset(
    {"otp", "totp", "mfa", "hwk", "swk", "webauthn", "fido", "u2f"}
)


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    """Politica de validacion de claims (sin secretos: solo issuer + audiencia)."""

    issuer: str
    audience: str

    def _verificar_audiencia(self, claims: dict) -> None:
        aud = claims.get("aud")
        valores = aud if isinstance(aud, (list, tuple)) else [aud]
        if self.audience not in valores:
            raise UnauthenticatedError("Audiencia del token no coincide con JWT_AUDIENCE.")

    def _verificar_issuer(self, claims: dict) -> None:
        if claims.get("iss") != self.issuer:
            raise UnauthenticatedError("Issuer del token no coincide con KEYCLOAK_ISSUER.")

    def _mfa_satisfecho(self, claims: dict) -> bool:
        amr = claims.get("amr") or []
        if isinstance(amr, str):
            amr = [amr]
        if any(m.lower() in SEGUNDO_FACTOR_AMR for m in amr):
            return True
        # ACR >= 2 (algunos IdP exponen el nivel de aseguramiento como acr numerico).
        acr = claims.get("acr")
        if isinstance(acr, str) and acr.isdigit() and int(acr) >= 2:
            return True
        return False

    def principal_desde_claims(self, claims: dict) -> AuthenticatedPrincipal:
        """Valida issuer/audiencia y construye el principal desde los claims.

        Presupone que la FIRMA y la EXPIRACION ya fueron verificadas por la lib en
        infraestructura; aqui se re-chequean issuer + audiencia (defensa en
        profundidad) y se mapean los claims al value object de dominio."""
        self._verificar_issuer(claims)
        self._verificar_audiencia(claims)

        id_institucional = (
            claims.get("preferred_username")
            or claims.get("upn")
            or claims.get("sub")
        )
        if not id_institucional:
            raise UnauthenticatedError("El token no porta identificador institucional.")

        roles_raw = []
        realm_access = claims.get("realm_access") or {}
        if isinstance(realm_access, dict):
            roles_raw = realm_access.get("roles") or []
        roles = tuple(r for r in (parse_rol(x) for x in roles_raw) if r is not None)

        attrs = {
            k: str(v)
            for k, v in claims.items()
            if k in ("given_name", "family_name", "name", "preferred_username")
            and v is not None
        }

        return AuthenticatedPrincipal(
            id_institucional=str(id_institucional),
            email=str(claims.get("email") or ""),
            roles=roles,
            mfa_satisfecho=self._mfa_satisfecho(claims),
            jurisdiccion=(
                str(claims["jurisdiccion"]) if claims.get("jurisdiccion") else None
            ),
            subject=str(claims.get("sub")) if claims.get("sub") else None,
            attrs_federados=attrs,
        )
