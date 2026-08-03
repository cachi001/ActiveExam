"""C-73 Fase 1: write-back por ``mod_assign_save_grade`` (camino del servicio movil).

POR QUE ESTE CAMINO EXISTE (verificado E2E en campustest, curso 7 / cmid 537):
  ``core_grades_update_grades`` NO esta en el servicio movil de fabrica, asi que exige
  un servicio externo custom con lista blanca — o sea, que alguien toque el campus.
  ``mod_assign_save_grade`` SI esta. Con el token que el propio docente se autoemite
  (``createmobiletoken`` es default de fabrica), la nota queda registrada con SU
  identidad: la columna *Calificador* de la libreta dice su nombre.

  Sonda que lo confirmo: ``mod_assign_save_grade`` con ``assignmentid=0`` devuelve
  ``invalidrecord``, NO ``accessexception``.

El HTTP de Moodle se MOCKEA con respx. NUNCA la DB (regla dura de codigo #4).
El token NUNCA aparece en un assert — se inyecta via config.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.infrastructure.moodle.client import (
    AssignmentGradeConfig,
    MoodleClientConfig,
    MoodleDestinoNoConfiguradoError,
    MoodleEscalaNoSoportadaError,
    MoodleGradeWriteError,
    MoodleRestClient,
)

_URL = "https://moodle.example.com/webservice/rest/server.php"


@pytest.fixture
def client():
    return MoodleRestClient(
        config=MoodleClientConfig(
            base_url="https://moodle.example.com",
            ws_token="token_institucional_nunca_logueado",  # noqa: S106
        )
    )


def _assignments(*, cmid: int, instance_id: int, grade, nombre: str = "TP 1") -> dict:
    """Respuesta de ``mod_assign_get_assignments`` con una tarea."""
    return {
        "courses": [
            {
                "id": 7,
                "assignments": [
                    {"cmid": cmid, "id": instance_id, "grade": grade, "name": nombre}
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# resolver_assignment_config — cmid -> assign.id + escala
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resuelve_cmid_a_instance_id_y_escala_numerica(client):
    """cmid 537 -> assign.id 39, numerica sobre 100 (el caso real de campustest).

    Es el paso que HOY falta: la base guarda ``moodle_cmid`` y
    ``mod_assign_save_grade`` pide el instance id. No son el mismo numero.
    """
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=537, instance_id=39, grade=100))
    )

    config = await client.resolver_assignment_config(courseid=7, cmid=537)

    assert config == AssignmentGradeConfig(
        instance_id=39, tipo="numerica", grade_max=100.0, scale_id=None
    )


@pytest.mark.asyncio
@respx.mock
async def test_grade_negativo_es_escala_cualitativa_no_un_error(client):
    """``grade`` negativo = id de escala cualitativa. NO es un error.

    Regresion del bug de ``get_grademax`` (client.py): trataba ``grademax <= 0`` como
    "no es nota numerica -> error". Pero un negativo es un dato valido: -5 significa
    escala id 5 (p.ej. Aprobado/Desaprobado). Tratarlo como error rompia el
    write-back de cualquier actividad con escala cualitativa.
    """
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=537, instance_id=39, grade=-5))
    )

    config = await client.resolver_assignment_config(courseid=7, cmid=537)

    assert config.tipo == "escala"
    assert config.scale_id == 5
    assert config.grade_max is None


@pytest.mark.asyncio
@respx.mock
async def test_grade_cero_es_actividad_sin_calificacion(client):
    """``grade == 0`` = la actividad no califica. Hay que detectarlo ANTES de escribir."""
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=537, instance_id=39, grade=0))
    )

    config = await client.resolver_assignment_config(courseid=7, cmid=537)

    assert config.tipo == "sin_calificacion"


@pytest.mark.asyncio
@respx.mock
async def test_cmid_que_no_es_tarea_del_curso_devuelve_none(client):
    """Si el cmid no es una TAREA del curso -> None (puede ser un Cuestionario)."""
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=999, instance_id=39, grade=100))
    )

    assert await client.resolver_assignment_config(courseid=7, cmid=537) is None


@pytest.mark.asyncio
@respx.mock
async def test_error_de_moodle_al_resolver_propaga(client):
    """Un error del WS no puede devolver None en silencio: None significa "no es tarea"."""
    respx.post(_URL).mock(
        return_value=Response(
            200,
            json={
                "exception": "webservice_access_exception",
                "errorcode": "accessexception",
                "message": "Access control exception",
            },
        )
    )

    with pytest.raises(MoodleGradeWriteError, match="accessexception"):
        await client.resolver_assignment_config(courseid=7, cmid=537)


# ---------------------------------------------------------------------------
# write_grade_assign — mod_assign_save_grade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_escribe_con_assignmentid_y_parametros_correctos(client):
    """El payload usa el INSTANCE id y los parametros que Moodle espera."""
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(200, json=_assignments(cmid=537, instance_id=39, grade=100)),
            Response(200, text="null"),  # mod_assign_save_grade devuelve null en exito
        ]
    )

    await client.write_grade_assign(
        moodle_userid=8, nota=75.0, courseid=7, cmid=537
    )

    enviado = dict(
        par.split("=", 1) for par in ruta.calls[1].request.content.decode().split("&")
    )
    assert enviado["wsfunction"] == "mod_assign_save_grade"
    # El instance id (39), NO el cmid (537). Confundirlos escribe en otra actividad.
    assert enviado["assignmentid"] == "39"
    assert enviado["userid"] == "8"
    assert enviado["grade"] == "75.0"
    assert enviado["attemptnumber"] == "-1"  # ultimo intento
    assert enviado["applytoall"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_convierte_la_escala_de_origen_a_la_del_item(client):
    """Un 8 sobre 10 se escribe como 80 sobre 100, no como 8.

    Sin esto un alumno aprobado queda casi desaprobado en la libreta oficial.
    El ``grade_max`` sale del propio assignment, no de una copia nuestra.
    """
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(200, json=_assignments(cmid=537, instance_id=39, grade=100)),
            Response(200, text="null"),
        ]
    )

    await client.write_grade_assign(
        moodle_userid=8, nota=8.0, courseid=7, cmid=537, nota_maxima=10.0
    )

    enviado = dict(
        par.split("=", 1) for par in ruta.calls[1].request.content.decode().split("&")
    )
    assert enviado["grade"] == "80.0"


@pytest.mark.asyncio
@respx.mock
async def test_el_token_del_docente_pisa_al_institucional(client):
    """Con ``ws_token`` la nota sale con la identidad del DOCENTE.

    Es el punto del cambio: Moodle pone como *Calificador* al dueno del token.
    """
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(200, json=_assignments(cmid=537, instance_id=39, grade=100)),
            Response(200, text="null"),
        ]
    )

    await client.write_grade_assign(
        moodle_userid=8,
        nota=75.0,
        courseid=7,
        cmid=537,
        ws_token="token_del_docente",  # noqa: S106
    )

    # Las DOS llamadas van con el token del docente: leer la escala con el
    # institucional y escribir con el del docente puede leer un item que ese
    # docente ni siquiera ve.
    for llamada in ruta.calls:
        assert "token_del_docente" in llamada.request.content.decode()


@pytest.mark.asyncio
@respx.mock
async def test_manda_el_feedback_como_html(client):
    """El comentario viaja en el plugin de retroalimentacion, en HTML."""
    ruta = respx.post(_URL).mock(
        side_effect=[
            Response(200, json=_assignments(cmid=537, instance_id=39, grade=100)),
            Response(200, text="null"),
        ]
    )

    await client.write_grade_assign(
        moodle_userid=8,
        nota=75.0,
        courseid=7,
        cmid=537,
        feedback_html="<p>Corregido por ActiveExam</p>",
    )

    cuerpo = ruta.calls[1].request.content.decode()
    assert "plugindata" in cuerpo
    assert "assignfeedbackcomments_editor" in cuerpo


@pytest.mark.asyncio
@respx.mock
async def test_sin_destino_no_escribe(client):
    """Sin courseid/cmid no se escribe: iria a la libreta de otra materia."""
    with pytest.raises(MoodleDestinoNoConfiguradoError):
        await client.write_grade_assign(moodle_userid=8, nota=75.0, courseid=None, cmid=537)


@pytest.mark.asyncio
@respx.mock
async def test_escala_cualitativa_no_se_escribe_a_ciegas(client):
    """Una escala cualitativa NO se puede calificar sin saber el orden de sus items.

    El orden no es inferible: el equipo verifico scale_id=5 con 1=Aprobado y
    2=Desaprobado (INVERTIDO). Asumir lo contrario desaprueba a todos los aprobados,
    asi que se corta con un error explicito.
    """
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=537, instance_id=39, grade=-5))
    )

    with pytest.raises(MoodleEscalaNoSoportadaError):
        await client.write_grade_assign(moodle_userid=8, nota=75.0, courseid=7, cmid=537)


@pytest.mark.asyncio
@respx.mock
async def test_actividad_sin_calificacion_no_se_escribe(client):
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=537, instance_id=39, grade=0))
    )

    with pytest.raises(MoodleGradeWriteError, match="no califica"):
        await client.write_grade_assign(moodle_userid=8, nota=75.0, courseid=7, cmid=537)


@pytest.mark.asyncio
@respx.mock
async def test_cmid_inexistente_es_error_explicito(client):
    respx.post(_URL).mock(
        return_value=Response(200, json=_assignments(cmid=999, instance_id=39, grade=100))
    )

    with pytest.raises(MoodleGradeWriteError, match="no es una tarea"):
        await client.write_grade_assign(moodle_userid=8, nota=75.0, courseid=7, cmid=537)


@pytest.mark.asyncio
@respx.mock
async def test_error_de_moodle_al_escribir_propaga(client):
    """Moodle contesta 200 con ``exception`` incluso cuando fallo."""
    respx.post(_URL).mock(
        side_effect=[
            Response(200, json=_assignments(cmid=537, instance_id=39, grade=100)),
            Response(
                200,
                json={
                    "exception": "moodle_exception",
                    "errorcode": "invalidtoken",
                    "message": "Ficha (token) no valida",
                },
            ),
        ]
    )

    with pytest.raises(MoodleGradeWriteError, match="invalidtoken"):
        await client.write_grade_assign(moodle_userid=8, nota=75.0, courseid=7, cmid=537)


# ---------------------------------------------------------------------------
# hay_nota_cargada — anti-pisado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_detecta_nota_ya_cargada_a_mano(client):
    """Si el docente ya califico a mano, no hay que pisarle la nota."""
    respx.post(_URL).mock(
        return_value=Response(
            200,
            json={
                "assignments": [
                    {
                        "assignmentid": 39,
                        "grades": [{"userid": 8, "grade": "90.00000", "timemodified": 1700000000}],
                    }
                ]
            },
        )
    )

    assert await client.hay_nota_cargada(instance_id=39, moodle_userid=8) is True


@pytest.mark.asyncio
@respx.mock
async def test_sin_notas_cargadas_no_hay_nada_que_pisar(client):
    respx.post(_URL).mock(
        return_value=Response(200, json={"assignments": [{"assignmentid": 39, "grades": []}]})
    )

    assert await client.hay_nota_cargada(instance_id=39, moodle_userid=8) is False


@pytest.mark.asyncio
@respx.mock
async def test_nota_de_otro_alumno_no_cuenta(client):
    """La nota de OTRO alumno no bloquea la de este."""
    respx.post(_URL).mock(
        return_value=Response(
            200,
            json={
                "assignments": [
                    {
                        "assignmentid": 39,
                        "grades": [{"userid": 99, "grade": "90.00000", "timemodified": 1700000000}],
                    }
                ]
            },
        )
    )

    assert await client.hay_nota_cargada(instance_id=39, moodle_userid=8) is False


@pytest.mark.asyncio
@respx.mock
async def test_grade_negativo_no_es_nota_real(client):
    """Moodle usa -1 para "sin calificar". No es una nota puesta por nadie."""
    respx.post(_URL).mock(
        return_value=Response(
            200,
            json={
                "assignments": [
                    {
                        "assignmentid": 39,
                        "grades": [{"userid": 8, "grade": "-1.00000", "timemodified": 1700000000}],
                    }
                ]
            },
        )
    )

    assert await client.hay_nota_cargada(instance_id=39, moodle_userid=8) is False
