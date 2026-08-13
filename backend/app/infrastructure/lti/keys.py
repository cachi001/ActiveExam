"""Par de claves RS256 de ActiveExam-como-Tool LTI (C-75, design D3).

LTI 1.3 exige que el Tool exponga un JWKS público (RS256) para el registro
dinámico y para que Moodle pueda verificar mensajes firmados por el Tool. El JWT
de sesión (`emitir_jwt_propio`) es HS256 simétrico y NO sirve para eso.

- ``generar_par_rs256`` es PURA: genera una clave RSA 2048 y devuelve
  ``(pem_privada, jwk_publica, kid)``. La privada en PEM (PKCS8, sin cifrar acá —
  el cifrado at-rest lo aplica el llamador con ``SecretCipher``); la pública como
  JWK listo para servir en ``GET /lti/jwks``.
- ``asegurar_tool_key_activa`` es idempotente: si ya hay una fila activa la
  devuelve; si no, genera el par, cifra la privada y lo persiste.
"""

from __future__ import annotations

import json
import secrets

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.lti import LtiToolKeyModel


def generar_par_rs256() -> tuple[str, dict, str]:
    """Genera una clave RSA 2048 y la devuelve como (PEM privada, JWK pública, kid).

    El JWK público incluye ``kid``/``use=sig``/``alg=RS256`` además de los campos
    RSA (``kty``/``n``/``e``) — el shape que Moodle espera en un JWK Set.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privada = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    kid = secrets.token_hex(16)
    jwk_publica = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk_publica.update({"kid": kid, "use": "sig", "alg": "RS256"})

    return pem_privada, jwk_publica, kid


async def asegurar_tool_key_activa(
    session: AsyncSession, cipher: SecretCipher
) -> LtiToolKeyModel:
    """Devuelve la clave activa del Tool; la genera y persiste (cifrada) si no hay.

    Idempotente: pensada para llamarse al arranque o de forma perezosa antes de
    servir el JWKS. La privada se guarda cifrada con ``SecretCipher`` (misma clave
    EMBEDDING_ENCRYPTION_KEY que ``moodle_credencial``).
    """
    activa = (
        await session.execute(
            select(LtiToolKeyModel).where(LtiToolKeyModel.activo.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if activa is not None:
        return activa

    pem_privada, jwk_publica, kid = generar_par_rs256()
    fila = LtiToolKeyModel(
        kid=kid,
        clave_privada_cifrada=cipher.encrypt(pem_privada),
        clave_publica_jwk=jwk_publica,
        activo=True,
    )
    session.add(fila)
    await session.flush()
    return fila
