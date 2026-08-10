"""C-75 sección 4: validación del launch LTI (núcleo de seguridad).

DB real (regla dura #4). La firma se ejercita de verdad: se genera un par RSA de
prueba, se publica su JWK (mockeando el `jwks_fetcher`, sin HTTP a Moodle) y se
firma el `id_token`. Así el test prueba la verificación criptográfica real, no un
stub.

Cubre:
  4.1 launch válido (firma+aud+exp+nonce OK) → aceptado, nonce marcado consumido.
  4.2 firma inválida → rechazo (sin efectos).
  4.3 nonce reusado (replay) → rechazo.
  4.4 token expirado → rechazo.
  4.5 aud ≠ client_id registrado → rechazo.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.lti.launch_validation import (
    CLAIM_DEPLOYMENT_ID,
    LaunchInvalidoError,
    validar_launch,
)
from app.infrastructure.persistence.models.lti import (
    LtiDeploymentConfiableModel,
    LtiNonceModel,
)

_ISS = "https://campustest.frm.utn.edu.ar"
_DEPLOYMENT_ID = "7:zztest"
_CLIENT_ID = "CLIENT123"
_KID = "k-test-1"


def _par_rsa():
    """Devuelve (pem_privada, jwk_publica con kid _KID)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = _KID
    return pem, jwk


def _claims(*, nonce, aud=_CLIENT_ID, exp_delta=300, sub="mdl-42"):
    ahora = int(time.time())
    return {
        "iss": _ISS,
        "aud": aud,
        "sub": sub,
        "iat": ahora,
        "exp": ahora + exp_delta,
        "nonce": nonce,
        CLAIM_DEPLOYMENT_ID: _DEPLOYMENT_ID,
        "name": "Alumno Prueba",
        "email": "alumno@demo.test",
    }


def _firmar(pem, claims):
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": _KID})


def _fetcher(jwk):
    return lambda _uri: {"keys": [jwk]}


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — test de integración omitido")
    return url


@pytest_asyncio.fixture
async def engine(db_url):
    eng = create_async_engine(db_url, poolclass=NullPool, future=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def _limpiar(session_factory):
    async with session_factory() as s:
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()
    yield


async def _preparar(session_factory, *, nonce, state):
    async with session_factory() as s:
        s.add(
            LtiDeploymentConfiableModel(
                iss=_ISS,
                deployment_id=_DEPLOYMENT_ID,
                client_id=_CLIENT_ID,
                jwks_uri="https://campustest.frm.utn.edu.ar/mod/lti/certs.php",
            )
        )
        s.add(
            LtiNonceModel(
                nonce=nonce,
                state=state,
                iss=_ISS,
                expira_en=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await s.commit()


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_launch_valido_se_acepta_y_consume_nonce(session_factory, _limpiar):
    pem, jwk = _par_rsa()
    await _preparar(session_factory, nonce="N1", state="S1")
    token = _firmar(pem, _claims(nonce="N1"))

    async with session_factory() as s:
        validado = await validar_launch(
            s, id_token=token, state="S1", jwks_fetcher=_fetcher(jwk)
        )
    assert validado.claims["sub"] == "mdl-42"
    assert validado.deployment.client_id == _CLIENT_ID

    async with session_factory() as s:
        row = (
            await s.execute(select(LtiNonceModel).where(LtiNonceModel.nonce == "N1"))
        ).scalar_one()
    assert row.consumido_en is not None


@pytest.mark.asyncio
async def test_launch_firma_invalida_se_rechaza(session_factory, _limpiar):
    _pem_bueno, jwk = _par_rsa()  # el JWKS publica ESTA pública (kid _KID)
    pem_impostor, _ = _par_rsa()  # pero firmamos con OTRA privada
    await _preparar(session_factory, nonce="N2", state="S2")
    token = _firmar(pem_impostor, _claims(nonce="N2"))

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc:
            await validar_launch(
                s, id_token=token, state="S2", jwks_fetcher=_fetcher(jwk)
            )
    assert exc.value.codigo == "firma_invalida"


@pytest.mark.asyncio
async def test_launch_replay_nonce_reusado_se_rechaza(session_factory, _limpiar):
    pem, jwk = _par_rsa()
    await _preparar(session_factory, nonce="N3", state="S3")
    token = _firmar(pem, _claims(nonce="N3"))

    async with session_factory() as s:
        await validar_launch(s, id_token=token, state="S3", jwks_fetcher=_fetcher(jwk))

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc:
            await validar_launch(
                s, id_token=token, state="S3", jwks_fetcher=_fetcher(jwk)
            )
    assert exc.value.codigo == "nonce_invalido"


@pytest.mark.asyncio
async def test_launch_token_expirado_se_rechaza(session_factory, _limpiar):
    pem, jwk = _par_rsa()
    await _preparar(session_factory, nonce="N4", state="S4")
    token = _firmar(pem, _claims(nonce="N4", exp_delta=-10))  # ya vencido

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc:
            await validar_launch(
                s, id_token=token, state="S4", jwks_fetcher=_fetcher(jwk)
            )
    assert exc.value.codigo == "token_expirado"


@pytest.mark.asyncio
async def test_launch_audiencia_incorrecta_se_rechaza(session_factory, _limpiar):
    pem, jwk = _par_rsa()
    await _preparar(session_factory, nonce="N5", state="S5")
    # aud apunta a otro client_id: la firma es válida pero la audiencia no.
    token = _firmar(pem, _claims(nonce="N5", aud="OTRO_TOOL"))

    async with session_factory() as s:
        with pytest.raises(LaunchInvalidoError) as exc:
            await validar_launch(
                s, id_token=token, state="S5", jwks_fetcher=_fetcher(jwk)
            )
    assert exc.value.codigo == "audiencia_invalida"
