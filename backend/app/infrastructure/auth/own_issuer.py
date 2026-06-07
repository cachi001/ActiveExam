"""Emisor de JWT propio (HS256) para el provider local (C-55).

Firma un access token con el secreto ``JWT_OWN_SECRET`` (HS256). El shape de
los claims es IDENTICO al de Keycloak (sub, preferred_username, email,
realm_access.roles, iss, aud, exp, iat) para que ``TokenPolicy.principal_desde_claims()``
funcione sin cambios — garantia de retrocompatibilidad (D3).

``mfa_satisfecho`` NO se incluye en el token propio (no hay MFA en este change);
``amr`` queda ausente, por lo que el mapeo en TokenPolicy retorna
``mfa_satisfecho=False`` para todos los roles. El frontend muestra un warning
visible pero NO bloquea (deuda tecnica documentada: MFA propio = change futuro).

DEUDA TECNICA (MFA propio):
  Los roles proctor y admin_sistema exigen MFA (RN-AU / ROLES_CON_MFA).
  En este change el provider JWT propio emite ``mfa_satisfecho=False`` para
  esos roles. El acceso NO se bloquea (MVP); el frontend advierte con un banner.
  La implementacion de TOTP propio queda documentada como change futuro.
"""

from __future__ import annotations

import time

import jwt  # PyJWT

from app.domain.auth.roles import parse_rol
from app.infrastructure.persistence.models.transactional import UsuarioModel


def emitir_jwt_propio(
    usuario: UsuarioModel,
    *,
    secret: str,
    issuer: str,
    audience: str,
    ttl_seconds: int = 900,
) -> str:
    """Firma un JWT HS256 con claims compatibles con TokenPolicy.

    Args:
        usuario: instancia ORM del usuario autenticado.
        secret: secreto HS256 (``JWT_OWN_SECRET``, sensible).
        issuer: claim ``iss`` (``JWT_OWN_ISSUER``, ej. "activeexam-auth").
        audience: claim ``aud`` (``JWT_AUDIENCE``).
        ttl_seconds: vida del token en segundos (default 15 min).

    Returns:
        JWT firmado como string.
    """
    ahora = int(time.time())
    roles_validos = [r.value for r in (parse_rol(rol) for rol in (usuario.roles or [])) if r is not None]

    claims: dict = {
        "sub": str(usuario.id),
        "preferred_username": usuario.id_institucional,
        "email": usuario.email,
        "realm_access": {"roles": roles_validos},
        "iss": issuer,
        "aud": audience,
        "iat": ahora,
        "exp": ahora + ttl_seconds,
        # amr ausente: sin MFA propio en este change (deuda tecnica documentada).
        # TokenPolicy lo leerá como mfa_satisfecho=False — warning en frontend.
    }

    return jwt.encode(claims, secret, algorithm="HS256")
