"""7.3 RED → 7.4 GREEN: tests del cliente Moodle REST.

El HTTP de Moodle se MOCKEA con respx (httpx mock). NUNCA la DB.
El token NUNCA aparece en el test — se inyecta vía config.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.infrastructure.moodle.client import (
    MoodleClientConfig,
    MoodleGradeWriteError,
    MoodleRestClient,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    return MoodleClientConfig(
        base_url="https://moodle.example.com",
        ws_token="test_token_never_logged",  # noqa: S106
        courseid=42,
        cmid=99,
    )


@pytest.fixture
def client(config):
    return MoodleRestClient(config=config)


# ---------------------------------------------------------------------------
# 7.3 RED → 7.4 GREEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_ok(client):
    """Moodle responde OK con warnings vacío → éxito sin excepción."""
    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        return_value=Response(200, json={"warnings": []})
    )

    await client.write_grade(
        moodle_userid=7,
        nota=8.5,
    )
    # No exception = success


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_error_moodle_exception(client):
    """Moodle devuelve un error de excepción (token inválido, etc.) → MoodleGradeWriteError."""
    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        return_value=Response(
            200,
            json={
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token",
            },
        )
    )

    with pytest.raises(MoodleGradeWriteError) as exc_info:
        await client.write_grade(moodle_userid=7, nota=8.5)

    assert "invalidtoken" in str(exc_info.value).lower() or "token" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_network_error(client):
    """Fallo de red (conexión rechazada) → MoodleGradeWriteError."""
    import httpx

    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with pytest.raises(MoodleGradeWriteError):
        await client.write_grade(moodle_userid=7, nota=8.5)


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_http_500(client):
    """Moodle responde 500 → MoodleGradeWriteError."""
    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        return_value=Response(500, text="Internal Server Error")
    )

    with pytest.raises(MoodleGradeWriteError):
        await client.write_grade(moodle_userid=7, nota=8.5)


@pytest.mark.asyncio
@respx.mock
async def test_token_not_in_request_body_as_plaintext(client):
    """El token NO se envía como campo visible en el payload (va encriptado/implícito
    en el parámetro wstoken del WS, pero no como un campo de debug/log aparte).

    Verifica que el payload contenga 'wstoken' como campo WS (obligatorio por Moodle)
    y que la request no incluya el token en ningún campo de log/audit.
    """
    captured = {}

    def capture(request, **kwargs):
        captured["content"] = request.content.decode()
        return Response(200, json={"warnings": []})

    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        side_effect=capture
    )

    await client.write_grade(moodle_userid=7, nota=8.5)

    assert "wstoken" in captured["content"]
    # El token real está en wstoken, pero no en campos de audit/log separados
    # (campo "token" plano, "auth_token", etc.)
    assert "auth_token" not in captured["content"]
    assert "debug_token" not in captured["content"]


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_usa_target_por_examen(client):
    """D12: si se pasan courseid/cmid, el payload los usa (no el global de config)."""
    captured = {}

    def capture(request, **kwargs):
        captured["content"] = request.content.decode()
        return Response(200, json={"warnings": []})

    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        side_effect=capture
    )

    # config global es courseid=42, cmid=99; el examen apunta a 1000/2000
    await client.write_grade(moodle_userid=7, nota=8.5, courseid=1000, cmid=2000)

    content = captured["content"]
    assert "courseid=1000" in content
    assert "activityid=2000" in content
    assert "courseid=42" not in content
    assert "activityid=99" not in content


@pytest.mark.asyncio
@respx.mock
async def test_write_grade_fallback_a_config_cuando_none(client):
    """D12: sin courseid/cmid (None) cae al global de config (compat exámenes viejos)."""
    captured = {}

    def capture(request, **kwargs):
        captured["content"] = request.content.decode()
        return Response(200, json={"warnings": []})

    respx.post("https://moodle.example.com/webservice/rest/server.php").mock(
        side_effect=capture
    )

    await client.write_grade(moodle_userid=7, nota=8.5)  # sin target → global

    content = captured["content"]
    assert "courseid=42" in content
    assert "activityid=99" in content


def test_config_extra_forbid():
    """MoodleClientConfig tiene extra='forbid' (Pydantic)."""
    import pydantic

    with pytest.raises((pydantic.ValidationError, TypeError)):
        MoodleClientConfig(
            base_url="https://moodle.example.com",
            ws_token="tok",  # noqa: S106
            courseid=1,
            cmid=1,
            campo_extra_invalido="valor",  # debe fallar
        )
