"""Con qué credencial se devuelve cada nota (C-73 §10.4, §10.5, §10.6).

Reglas que se clavan acá:

- La nota la devuelve el DOCENTE a cargo de la comisión del examen. Su token pisa
  al institucional, y en `source` queda que fue una credencial personal.
- Si la comisión no tiene docente, o el docente no conectó su cuenta, la nota NO se
  manda: se retiene con motivo `sin_credencial_docente`. Mandarla con la cuenta
  institucional la dejaría en la libreta sin responsable —el problema que este cambio
  vino a resolver— y encima en silencio.
- Si el token del docente fue revocado (`invalidtoken`), se marca su credencial como
  CAÍDA (para poder avisarle) y la nota queda pendiente. Tampoco se reintenta con la
  institucional: firmaría con otra identidad sin que nadie se entere.

Se prueba contra el cliente real con transporte simulado (`respx`); NO se mockea DB.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.application.moodle.writeback_service import _es_token_invalido
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient

_BASE = "https://campus.test"
_TOKEN_INSTITUCIONAL = "token-institucional-aaaa"  # noqa: S105
_TOKEN_DOCENTE = "token-del-docente-bbbb"  # noqa: S105


def _client() -> MoodleRestClient:
    async def _provider() -> MoodleClientConfig:
        return MoodleClientConfig(
            base_url=_BASE, ws_token=_TOKEN_INSTITUCIONAL, component="mod_assign"
        )

    return MoodleRestClient(config_provider=_provider)


def _mock_grade_items(router):
    """La lectura de escala responde grademax 100 (caso típico de Moodle)."""
    router.post(f"{_BASE}/webservice/rest/server.php").mock(
        side_effect=_responder
    )


_capturas: list[dict] = []


def _responder(request: httpx.Request) -> httpx.Response:
    from urllib.parse import parse_qs

    datos = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
    _capturas.append(datos)
    if datos.get("wsfunction") == "gradereport_user_get_grade_items":
        return httpx.Response(
            200,
            json={
                "usergrades": [
                    {"gradeitems": [{"cmid": 55, "grademax": 100.0}]}
                ]
            },
        )
    # Un update exitoso de Moodle responde `null`.
    return httpx.Response(200, json=None, text='null')


@pytest.fixture(autouse=True)
def _limpiar():
    _capturas.clear()
    yield
    _capturas.clear()


@pytest.mark.asyncio
@respx.mock
async def test_el_token_del_docente_pisa_al_institucional():
    _mock_grade_items(respx)
    await _client().write_grade(
        moodle_userid=7,
        nota=8.0,
        courseid=9,
        cmid=55,
        nota_maxima=10.0,
        ws_token=_TOKEN_DOCENTE,
        source="activeexam:docente",
    )
    escritura = [c for c in _capturas if c["wsfunction"] == "core_grades_update_grades"][0]
    assert escritura["wstoken"] == _TOKEN_DOCENTE
    assert escritura["source"] == "activeexam:docente"


@pytest.mark.asyncio
@respx.mock
async def test_el_cliente_sin_token_explicito_usa_el_institucional():
    """Contrato del CLIENTE (lo usa la anulación por fraude, que decide un revisor).

    Que el cliente sepa escribir con la institucional no significa que el write-back
    de una nota lo haga: ese camino exige credencial del docente (ver §10.4)."""
    _mock_grade_items(respx)
    await _client().write_grade(
        moodle_userid=7, nota=8.0, courseid=9, cmid=55, nota_maxima=10.0
    )
    escritura = [c for c in _capturas if c["wsfunction"] == "core_grades_update_grades"][0]
    assert escritura["wstoken"] == _TOKEN_INSTITUCIONAL
    assert escritura["source"] == "activeexam"


@pytest.mark.asyncio
@respx.mock
async def test_la_escala_se_lee_con_la_misma_credencial_que_escribe():
    """Leer la escala con un token y escribir con otro puede leer un ítem que el
    docente ni siquiera ve."""
    _mock_grade_items(respx)
    await _client().write_grade(
        moodle_userid=7,
        nota=8.0,
        courseid=9,
        cmid=55,
        nota_maxima=10.0,
        ws_token=_TOKEN_DOCENTE,
    )
    lectura = [
        c for c in _capturas if c["wsfunction"] == "gradereport_user_get_grade_items"
    ][0]
    assert lectura["wstoken"] == _TOKEN_DOCENTE


@pytest.mark.asyncio
@respx.mock
async def test_la_nota_se_escala_al_grademax_real():
    """8/10 en un ítem sobre 100 debe llegar como 80, no como 8."""
    _mock_grade_items(respx)
    await _client().write_grade(
        moodle_userid=7, nota=8.0, courseid=9, cmid=55, nota_maxima=10.0
    )
    escritura = [c for c in _capturas if c["wsfunction"] == "core_grades_update_grades"][0]
    assert float(escritura["grades[0][grade]"]) == pytest.approx(80.0)


def test_reconoce_el_token_invalido_de_moodle():
    """Distinguirlo importa: se arregla recargando la credencial, no el destino."""
    assert _es_token_invalido(Exception("Moodle: invalidtoken"))
    assert _es_token_invalido(Exception("Ficha (token) no válida"))
    assert not _es_token_invalido(Exception("destino no configurado"))
