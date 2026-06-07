"""Tests HTTP de la API de configuracion de examen (C-07): RBAC + CRUD + 422.

Verifica:
- admin con MFA -> 2xx; rol no-admin -> 403; admin sin MFA -> 403 (exam-config-access-control).
- crear examen (201), validacion de parametros (422), set/list habilitados,
  asignar proctores, presign de referencia.

Inyecta un JwtValidator HS256 (sin PyJWT/Keycloak) y override de la dependencia del
servicio con repositorios en memoria (sin DB). Comparte el patron de
``test_app_factory`` (Settings del entorno). Requiere las deps de runtime.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.exam_config.service import ExamConfigService
from app.config import Settings
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.main import create_app
from app.presentation.api.v1.exams.dependencies import get_exam_service
from tests.test_exam_config_service import InMemoryAssignmentRepo, InMemoryExamRepo

_SECRET = b"exam-http-secret"
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

    # Servicio con repos en memoria (sin DB), compartido entre requests del test.
    exams, asgs = InMemoryExamRepo(), InMemoryAssignmentRepo()
    service = ExamConfigService(exams, asgs)

    async def _override():
        yield service

    app.dependency_overrides[get_exam_service] = _override
    return TestClient(app)


def _token(roles, mfa=True) -> str:
    claims = {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "s",
        "preferred_username": "admin1",
        "email": "admin1@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }
    if mfa:
        claims["amr"] = ["otp"]
    return encode_hs256(claims, _SECRET)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_VALID_EXAM = {
    "nombre": "Algebra Final",
    "inicio": "2026-06-01T09:00:00Z",
    "fin": "2026-06-01T11:00:00Z",
    "umbral_score": 0.7,
    "detectores": ["face_detection", "face_mesh"],
    "umbrales_detector": {"face_detection": 0.5},
    "politica_retencion": "estandar",
    "exige_biometria": True,
}


# --- RBAC --------------------------------------------------------------------


def test_no_admin_recibe_403(client: TestClient) -> None:
    resp = client.post("/api/v1/exams", json=_VALID_EXAM, headers=_h(_token(["estudiante"])))
    assert resp.status_code == 403


def test_admin_sin_mfa_recibe_403(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/exams", json=_VALID_EXAM, headers=_h(_token(["admin_examenes"], mfa=False))
    )
    assert resp.status_code == 403


def test_admin_con_mfa_crea_201(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/exams", json=_VALID_EXAM, headers=_h(_token(["admin_examenes"]))
    )
    assert resp.status_code == 201
    assert resp.json()["id"] is not None


def test_sin_token_401(client: TestClient) -> None:
    resp = client.post("/api/v1/exams", json=_VALID_EXAM)
    assert resp.status_code == 401


# --- Validacion (422) --------------------------------------------------------


def test_ventana_incoherente_422(client: TestClient) -> None:
    bad = {**_VALID_EXAM, "fin": "2026-06-01T08:00:00Z"}
    resp = client.post("/api/v1/exams", json=bad, headers=_h(_token(["admin_examenes"])))
    assert resp.status_code == 422
    assert "ventana" in resp.json()["detail"]["errores"]


def test_detector_desconocido_422(client: TestClient) -> None:
    bad = {**_VALID_EXAM, "detectores": ["telepatia"]}
    resp = client.post("/api/v1/exams", json=bad, headers=_h(_token(["admin_examenes"])))
    assert resp.status_code == 422


def test_campo_extra_422(client: TestClient) -> None:
    bad = {**_VALID_EXAM, "campo_raro": 1}
    resp = client.post("/api/v1/exams", json=bad, headers=_h(_token(["admin_examenes"])))
    assert resp.status_code == 422  # extra='forbid'


# --- Habilitados / proctores / referencia ------------------------------------


def test_set_y_list_habilitados(client: TestClient) -> None:
    h = _h(_token(["admin_examenes"]))
    created = client.post("/api/v1/exams", json=_VALID_EXAM, headers=h).json()
    eid = created["id"]
    put = client.put(
        f"/api/v1/exams/{eid}/students", json={"estudiantes": ["a", "b"]}, headers=h
    )
    assert put.status_code == 200
    assert set(put.json()["estudiantes"]) == {"a", "b"}
    get = client.get(f"/api/v1/exams/{eid}/students", headers=h)
    assert set(get.json()["estudiantes"]) == {"a", "b"}


def test_asignar_proctores(client: TestClient) -> None:
    h = _h(_token(["admin_examenes"]))
    eid = client.post("/api/v1/exams", json=_VALID_EXAM, headers=h).json()["id"]
    resp = client.put(
        f"/api/v1/exams/{eid}/proctors", json={"proctores": ["p1", "p2"]}, headers=h
    )
    assert resp.status_code == 200
    assert set(resp.json()["proctores"]) == {"p1", "p2"}


def test_referencia_presign(client: TestClient) -> None:
    h = _h(_token(["admin_examenes"]))
    eid = client.post("/api/v1/exams", json=_VALID_EXAM, headers=h).json()["id"]
    resp = client.post(
        f"/api/v1/exams/{eid}/reference-photo",
        json={"estudiante_id": "alu-1", "precomputada": False, "hash_binario": "h"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["upload_url"] is not None  # presign devuelto
    assert body["precomputada"] is False


def test_referencia_precomputada(client: TestClient) -> None:
    h = _h(_token(["admin_examenes"]))
    eid = client.post("/api/v1/exams", json=_VALID_EXAM, headers=h).json()["id"]
    resp = client.post(
        f"/api/v1/exams/{eid}/reference-photo",
        json={"estudiante_id": "alu-2", "precomputada": True},
        headers=h,
    )
    assert resp.status_code == 200
    assert resp.json()["upload_url"] is None  # no exige carga
