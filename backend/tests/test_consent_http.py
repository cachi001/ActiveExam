"""Tests HTTP del consentimiento (C-08): texto, acuse (422 sin afirmativa), gate.

Inyecta un JwtValidator HS256 (estudiante autenticado) y override del
ConsentService con puertos en memoria (sin DB). Comparte el patron de
``test_app_factory`` (Settings del entorno). Requiere deps de runtime.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.consent.service import ConsentService
from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.main import create_app
from app.presentation.api.v1.consent.dependencies import get_consent_service
from tests.test_consent_service import (
    FakeQueue,
    InMemoryAuditRepo,
    InMemoryConsentRepo,
)

_SECRET = b"consent-http-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"

_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://app@db:5432/proctoring",
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "k",
    "STORAGE_SECRET_KEY": "s",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "KEYCLOAK_ISSUER": _ISSUER,
    "KEYCLOAK_JWKS_URL": _ISSUER + "/protocol/openid-connect/certs",
    "JWT_AUDIENCE": _AUD,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    app = create_app(Settings())

    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )

    service = ConsentService(InMemoryConsentRepo(), InMemoryAuditRepo(), FakeQueue())

    async def _override():
        yield service

    app.dependency_overrides[get_consent_service] = _override
    return TestClient(app)


def _token(user="alu-1") -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": "s",
            "preferred_username": user,
            "email": f"{user}@uni.edu",
            "exp": 9999999999,
            "realm_access": {"roles": ["estudiante"]},
        },
        _SECRET,
    )


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_get_text_cinco_bloques(client: TestClient) -> None:
    resp = client.get("/api/v1/consent/text", headers=_h(_token()))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["bloques"]) == 5
    assert body["version"]
    assert len(body["hash_texto"]) == 64


def test_consent_sin_token_401(client: TestClient) -> None:
    resp = client.post("/api/v1/consent", json={"exam_id": "e1", "affirmative_action": True})
    assert resp.status_code == 401


def test_consent_sin_accion_afirmativa_422(client: TestClient) -> None:
    # affirmative_action default False -> el backend lo rechaza (D2).
    resp = client.post(
        "/api/v1/consent", json={"exam_id": "e1"}, headers=_h(_token())
    )
    assert resp.status_code == 422


def test_consent_con_accion_afirmativa_201(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/consent",
        json={"exam_id": "e1", "affirmative_action": True},
        headers=_h(_token()),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["hash"]) == 64
    assert body["exam_id"] == "e1"


def test_consent_campo_extra_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/consent",
        json={"exam_id": "e1", "affirmative_action": True, "extra": 1},
        headers=_h(_token()),
    )
    assert resp.status_code == 422  # extra='forbid'


def test_gate_flujo_completo(client: TestClient) -> None:
    h = _h(_token("alu-2"))
    # Sin resolver: gate no permite avanzar.
    g0 = client.get("/api/v1/consent/gate", params={"exam_id": "e1"}, headers=h)
    assert g0.json()["puede_avanzar"] is False
    # Consiente: gate habilita biometria.
    client.post(
        "/api/v1/consent", json={"exam_id": "e1", "affirmative_action": True}, headers=h
    )
    g1 = client.get("/api/v1/consent/gate", params={"exam_id": "e1"}, headers=h)
    body = g1.json()
    assert body["puede_avanzar"] is True
    assert body["biometria_habilitada"] is True
    assert body["resolucion"] == "consentido"


def test_alternativa_escala_sin_abortar(client: TestClient) -> None:
    h = _h(_token("alu-3"))
    resp = client.post(
        "/api/v1/consent/alternative", json={"exam_id": "e1"}, headers=h
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["escalado_a_proctor"] is True
    # El gate ahora avanza por la via alternativa, sin exigir biometria.
    g = client.get("/api/v1/consent/gate", params={"exam_id": "e1"}, headers=h)
    gb = g.json()
    assert gb["puede_avanzar"] is True
    assert gb["biometria_habilitada"] is False
    assert gb["resolucion"] == "via_alternativa"
