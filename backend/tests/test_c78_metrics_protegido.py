"""`/metrics` no puede quedar publico en produccion (c-78 task 16.3).

Hallazgo de la medicion de capacidad del 25/8/2026: el endpoint estaba abierto
en la instancia de Render. `generate_latest()` publica el catalogo completo de
rutas de la API (label `path` del histograma), los volumenes de trafico y la
memoria/CPU del proceso — reconocimiento gratis para cualquiera que pase.

Contrato que fijan estos tests:
  - Sin `METRICS_TOKEN` configurado, el endpoint esta DESHABILITADO (404). Fail
    closed: olvidarse la variable no deja el endpoint abierto, que es exactamente
    como se llego al hallazgo.
  - Con `METRICS_TOKEN`, exige `Authorization: Bearer <token>` (formato que
    Prometheus habla nativamente via `bearer_token` en el scrape_config).
  - El middleware de metricas sigue contando requests en los tres casos: proteger
    la lectura no debe apagar la instrumentacion.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.metrics_activeexam import instrument_activeexam_metrics

TOKEN = "token-de-scrape-de-prueba"


def _app() -> FastAPI:
    app = FastAPI()
    instrument_activeexam_metrics(app)
    return app


def test_sin_token_configurado_el_endpoint_no_existe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    resp = TestClient(_app()).get("/metrics")
    assert resp.status_code == 404


def test_con_token_configurado_y_bearer_correcto_expone_las_metricas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    resp = TestClient(_app()).get(
        "/metrics", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert resp.status_code == 200
    assert "# HELP" in resp.text or "# TYPE" in resp.text


def test_con_token_configurado_y_sin_credencial_rechaza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    resp = TestClient(_app()).get("/metrics")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"
    assert "http_requests_total" not in resp.text


def test_con_token_configurado_y_credencial_equivocada_rechaza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    client = TestClient(_app())
    for header in (
        "Bearer token-equivocado",
        TOKEN,  # sin el esquema Bearer
        "Basic dXNlcjpwYXNz",
        "Bearer ",
    ):
        resp = client.get("/metrics", headers={"Authorization": header})
        assert resp.status_code == 401, header


def test_el_token_se_lee_en_cada_request_no_al_importar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La app se construye una vez y vive horas; rotar el token no puede exigir
    reconstruirla, y un test que setea la variable despues de importar el modulo
    tampoco puede ver el valor viejo."""
    client = TestClient(_app())
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    assert client.get("/metrics").status_code == 404

    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    assert (
        client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).status_code
        == 200
    )


def test_la_instrumentacion_sigue_contando_aunque_el_scrape_este_cerrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("METRICS_TOKEN", TOKEN)
    app = _app()

    @app.get("/ping")
    async def _ping() -> dict[str, str]:
        return {"ok": "1"}

    client = TestClient(app)
    client.get("/ping")
    cuerpo = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"}).text
    assert 'path="/ping"' in cuerpo
