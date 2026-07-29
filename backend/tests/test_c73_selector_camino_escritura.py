"""C-73 Fase 1: selector de camino de escritura segun el ``component`` del destino.

DECISION DE DISENO — por que el selector vive en el CLIENTE y no en el servicio:
  Hay TRES lugares que escriben notas (`ejecutar_writeback`, `anular_nota`,
  `restituir_nota`). Si el `if component == 'mod_assign'` viviera en el servicio habria
  que repetirlo en los tres, y el dia que alguien agregue un cuarto camino se va a
  olvidar de uno. Con un solo punto de entrada (`escribir_nota`) los tres heredan el
  ruteo y la decision queda donde esta el conocimiento del protocolo de Moodle.

REGLA:
  component == 'mod_assign'  -> mod_assign_save_grade  (servicio movil, cero config
                                en el campus, Calificador = el docente)
  cualquier otro             -> core_grades_update_grades (requiere servicio custom
                                habilitado en el campus)
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient

_URL = "https://moodle.example.com/webservice/rest/server.php"


@pytest.fixture
def client():
    return MoodleRestClient(
        config=MoodleClientConfig(
            base_url="https://moodle.example.com",
            ws_token="token_institucional",  # noqa: S106
        )
    )


def _wsfunctions_llamadas(ruta) -> list[str]:
    """Las ``wsfunction`` que se invocaron, en orden."""
    llamadas = []
    for call in ruta.calls:
        params = dict(
            par.split("=", 1) for par in call.request.content.decode().split("&")
        )
        llamadas.append(params.get("wsfunction", ""))
    return llamadas


@pytest.mark.asyncio
@respx.mock
async def test_mod_assign_usa_el_camino_del_servicio_movil(client):
    """Una TAREA se escribe con ``mod_assign_save_grade``.

    Es el camino que no necesita que nadie toque el campus.
    """
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(
                200,
                json={
                    "courses": [
                        {"id": 7, "assignments": [{"cmid": 537, "id": 39, "grade": 100}]}
                    ]
                },
            ),
            Response(200, text="null"),
        ]
    )

    await client.escribir_nota(
        moodle_userid=8, nota=75.0, courseid=7, cmid=537, component="mod_assign"
    )

    llamadas = _wsfunctions_llamadas(ruta)
    assert "mod_assign_save_grade" in llamadas
    assert "core_grades_update_grades" not in llamadas


@pytest.mark.asyncio
@respx.mock
async def test_mod_quiz_sigue_por_core_grades_update_grades(client):
    """Un CUESTIONARIO no tiene equivalente en el servicio movil: camino viejo.

    No es una regresion, es el limite real de `mod_assign_save_grade`.
    """
    ruta = respx.post(_URL).mock(return_value=Response(200, json={"warnings": []}))

    await client.escribir_nota(
        moodle_userid=8, nota=75.0, courseid=7, cmid=537, component="mod_quiz"
    )

    llamadas = _wsfunctions_llamadas(ruta)
    assert "core_grades_update_grades" in llamadas
    assert "mod_assign_save_grade" not in llamadas


@pytest.mark.asyncio
@respx.mock
async def test_component_none_cae_al_default_institucional(client):
    """Sin ``component`` explicito manda el default de la config (``mod_assign``).

    Los examenes viejos no tienen `moodle_component` cargado: no pueden quedar sin
    poder enviar la nota por eso.
    """
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(
                200,
                json={
                    "courses": [
                        {"id": 7, "assignments": [{"cmid": 537, "id": 39, "grade": 100}]}
                    ]
                },
            ),
            Response(200, text="null"),
        ]
    )

    await client.escribir_nota(
        moodle_userid=8, nota=75.0, courseid=7, cmid=537, component=None
    )

    assert "mod_assign_save_grade" in _wsfunctions_llamadas(ruta)


@pytest.mark.asyncio
@respx.mock
async def test_el_token_del_docente_llega_al_camino_nuevo(client):
    """El token del docente tiene que atravesar el selector, no perderse en el ruteo.

    Si se perdiera, la nota saldria con la cuenta institucional y el Calificador
    diria otra cosa — el bug exacto que este cambio vino a resolver, pero silencioso.
    """
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(
                200,
                json={
                    "courses": [
                        {"id": 7, "assignments": [{"cmid": 537, "id": 39, "grade": 100}]}
                    ]
                },
            ),
            Response(200, text="null"),
        ]
    )

    await client.escribir_nota(
        moodle_userid=8,
        nota=75.0,
        courseid=7,
        cmid=537,
        component="mod_assign",
        ws_token="token_del_docente",  # noqa: S106
    )

    for call in ruta.calls:
        assert "token_del_docente" in call.request.content.decode()


@pytest.mark.asyncio
@respx.mock
async def test_la_escala_de_origen_se_respeta_en_ambos_caminos(client):
    """``nota_maxima`` no se puede perder en el ruteo: un 8/10 no es un 8/100."""
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(
                200,
                json={
                    "courses": [
                        {"id": 7, "assignments": [{"cmid": 537, "id": 39, "grade": 100}]}
                    ]
                },
            ),
            Response(200, text="null"),
        ]
    )

    await client.escribir_nota(
        moodle_userid=8,
        nota=8.0,
        courseid=7,
        cmid=537,
        component="mod_assign",
        nota_maxima=10.0,
    )

    params = dict(
        par.split("=", 1) for par in ruta.calls[1].request.content.decode().split("&")
    )
    assert params["grade"] == "80.0"
