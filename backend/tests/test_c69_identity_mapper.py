"""7.5 RED → 7.6 GREEN: tests del mapeo de identidad alumno ↔ usuario Moodle.

HTTP de Moodle MOCKEADO con respx. Sin mock de DB.
D9: resuelve por idnumber (default), fallback por email.
Sin match único → NO envía a usuario arbitrario → IdentityResolutionError.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.application.moodle.identity_mapper import (
    IdentityResolutionError,
    MoodleIdentityMapper,
    resolve_moodle_userid,
)
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient


BASE = "https://moodle.example.com"


@pytest.fixture
def config():
    return MoodleClientConfig(
        base_url=BASE,
        ws_token="tok",  # noqa: S106
        courseid=1,
        cmid=1,
    )


@pytest.fixture
def moodle_client(config):
    return MoodleRestClient(config=config)


@pytest.fixture
def mapper(moodle_client):
    return MoodleIdentityMapper(moodle_client=moodle_client)


# ---------------------------------------------------------------------------
# 7.5 RED → 7.6 GREEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resuelve_por_idnumber(mapper):
    """D9: si el alumno tiene idnumber mapeado en Moodle, lo usa."""
    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        return_value=Response(200, json=[{"id": 42, "idnumber": "legajo123"}])
    )

    userid = await mapper.resolve(idnumber="legajo123", email="alumno@u.edu")

    assert userid == 42


@pytest.mark.asyncio
@respx.mock
async def test_fallback_por_email_cuando_idnumber_no_en_moodle(mapper):
    """D9: si idnumber no resuelve en Moodle (retorna vacío), intenta por email."""
    call_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        call_count[0] += 1
        if "field=idnumber" in content:
            return Response(200, json=[])  # idnumber no encontrado en Moodle
        if "field=email" in content:
            return Response(200, json=[{"id": 77, "email": "alumno@u.edu"}])
        return Response(200, json=[])

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    # El alumno tiene idnumber pero no está registrado en Moodle con ese idnumber
    userid = await mapper.resolve(idnumber="legajo_no_en_moodle", email="alumno@u.edu")

    assert userid == 77
    assert call_count[0] == 2  # llamó idnumber + fallback email


@pytest.mark.asyncio
@respx.mock
async def test_sin_match_lanza_error(mapper):
    """D9: sin match único en idnumber ni email → IdentityResolutionError (no envía)."""
    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        return_value=Response(200, json=[])  # nadie encontrado
    )

    with pytest.raises(IdentityResolutionError):
        await mapper.resolve(idnumber="unknown", email="noone@u.edu")


@pytest.mark.asyncio
@respx.mock
async def test_multiples_matches_lanza_error(mapper):
    """Múltiples usuarios con el mismo idnumber → IdentityResolutionError."""
    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        return_value=Response(
            200,
            json=[{"id": 1, "idnumber": "x"}, {"id": 2, "idnumber": "x"}],
        )
    )

    with pytest.raises(IdentityResolutionError):
        await mapper.resolve(idnumber="x", email="a@b.com")


def test_resolve_moodle_userid_is_async_function():
    """resolve_moodle_userid es la función pública esperada por el servicio."""
    import inspect

    assert inspect.iscoroutinefunction(resolve_moodle_userid)
