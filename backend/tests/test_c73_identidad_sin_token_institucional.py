"""C-73 Fase 2: resolver la identidad del alumno SIN token institucional.

POR QUE:
  Hoy el mapeo usa `core_user_get_users_by_field` con la credencial INSTITUCIONAL, asi
  que aunque el docente ya tenga su cuenta conectada, sin token institucional vivo la
  nota no viaja. Y el token institucional de campustest esta MUERTO (`invalidtoken`),
  con lo cual todo el write-back depende de una credencial que hoy no funciona.

  `core_enrol_get_enrolled_users` esta en el servicio movil de fabrica (verificado en
  campustest, paso 4 del script de Fase 0) y el docente ve a los matriculados de SU
  curso. Resolviendo por ahi:
    - ActiveExam deja de necesitar credencial institucional para devolver notas.
    - Un docente no puede resolver identidades en cursos donde no da clase (el limite
      lo pone Moodle, no nuestro codigo).

DATO REAL QUE OBLIGA AL FALLBACK POR EMAIL:
  En el curso 7 de campustest solo 1 de 2 usuarios expone `idnumber` — `Alumno Prueba`
  NO lo tiene. El mapeo por legajo NO alcanza; el fallback por email es obligatorio.

HTTP mockeado con respx. NUNCA la DB.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.application.moodle.identity_mapper import (
    IdentityResolutionError,
    MoodleIdentityMapper,
)
from app.infrastructure.moodle.client import (
    MoodleClientConfig,
    MoodleGradeWriteError,
    MoodleRestClient,
)

_URL = "https://moodle.example.com/webservice/rest/server.php"


@pytest.fixture
def client():
    return MoodleRestClient(
        config=MoodleClientConfig(
            base_url="https://moodle.example.com",
            ws_token="token_institucional",  # noqa: S106
        )
    )


def _matriculados(*usuarios: dict) -> Response:
    """Respuesta de `core_enrol_get_enrolled_users` (una lista de usuarios)."""
    return Response(200, json=list(usuarios))


# ---------------------------------------------------------------------------
# lookup_userid_en_curso — el metodo nuevo del cliente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_resuelve_por_idnumber_entre_los_matriculados(client):
    respx.post(_URL).mock(
        return_value=_matriculados(
            {"id": 17, "idnumber": "PROF-PRUEBA-001", "email": "prof@u.edu"},
            {"id": 8, "idnumber": "EST-001", "email": "alumno@u.edu"},
        )
    )

    userid = await client.lookup_userid_en_curso(
        courseid=7, idnumber="EST-001", email="alumno@u.edu"
    )

    assert userid == 8


@pytest.mark.asyncio
@respx.mock
async def test_cae_a_email_cuando_el_alumno_no_tiene_idnumber(client):
    """El caso REAL de campustest: `Alumno Prueba` no tiene idnumber cargado.

    Si el mapeo dependiera solo del legajo, este alumno no recibiria la nota nunca.
    """
    respx.post(_URL).mock(
        return_value=_matriculados(
            {"id": 17, "idnumber": "PROF-PRUEBA-001", "email": "prof@u.edu"},
            {"id": 8, "idnumber": "", "email": "alumno@u.edu"},
        )
    )

    userid = await client.lookup_userid_en_curso(
        courseid=7, idnumber="EST-001", email="alumno@u.edu"
    )

    assert userid == 8


@pytest.mark.asyncio
@respx.mock
async def test_el_email_se_compara_sin_distinguir_mayusculas(client):
    """Moodle normaliza los emails a minuscula; el legajo de ActiveExam puede no venir asi.

    Comparar sensible a mayusculas dejaba sin nota a un alumno por como se escribio su
    email en el padron.
    """
    respx.post(_URL).mock(
        return_value=_matriculados({"id": 8, "idnumber": "", "email": "alumno@u.edu"})
    )

    userid = await client.lookup_userid_en_curso(
        courseid=7, idnumber="", email="Alumno@U.Edu"
    )

    assert userid == 8


@pytest.mark.asyncio
@respx.mock
async def test_el_idnumber_gana_sobre_el_email(client):
    """El legajo es la clave institucional: si matchea, no se mira el email.

    Importa cuando dos personas comparten un email (cuentas de catedra) pero tienen
    legajos distintos.
    """
    respx.post(_URL).mock(
        return_value=_matriculados(
            {"id": 8, "idnumber": "EST-001", "email": "compartido@u.edu"},
            {"id": 9, "idnumber": "EST-002", "email": "compartido@u.edu"},
        )
    )

    userid = await client.lookup_userid_en_curso(
        courseid=7, idnumber="EST-002", email="compartido@u.edu"
    )

    assert userid == 9


@pytest.mark.asyncio
@respx.mock
async def test_alumno_no_matriculado_devuelve_none(client):
    respx.post(_URL).mock(
        return_value=_matriculados({"id": 17, "idnumber": "OTRO", "email": "otro@u.edu"})
    )

    assert (
        await client.lookup_userid_en_curso(
            courseid=7, idnumber="EST-001", email="alumno@u.edu"
        )
        is None
    )


@pytest.mark.asyncio
@respx.mock
async def test_dos_matriculados_con_el_mismo_idnumber_es_error(client):
    """Ambiguedad = NO se elige uno arbitrario. Escribirle la nota al que no es es peor
    que no escribirla."""
    respx.post(_URL).mock(
        return_value=_matriculados(
            {"id": 8, "idnumber": "EST-001", "email": "a@u.edu"},
            {"id": 9, "idnumber": "EST-001", "email": "b@u.edu"},
        )
    )

    with pytest.raises(MoodleGradeWriteError, match="EST-001"):
        await client.lookup_userid_en_curso(
            courseid=7, idnumber="EST-001", email="a@u.edu"
        )


@pytest.mark.asyncio
@respx.mock
async def test_usa_el_token_del_docente_no_el_institucional(client):
    """Es el punto de la fase: el pedido va con la credencial del DOCENTE."""
    ruta = respx.post(_URL).mock(
        return_value=_matriculados({"id": 8, "idnumber": "EST-001", "email": "a@u.edu"})
    )

    await client.lookup_userid_en_curso(
        courseid=7,
        idnumber="EST-001",
        email="a@u.edu",
        ws_token="token_del_docente",  # noqa: S106
    )

    cuerpo = ruta.calls[0].request.content.decode()
    assert "token_del_docente" in cuerpo
    assert "token_institucional" not in cuerpo
    assert "core_enrol_get_enrolled_users" in cuerpo


@pytest.mark.asyncio
@respx.mock
async def test_error_del_ws_al_listar_matriculados_propaga(client):
    """Un docente sin permiso en el curso recibe `accessexception`: no puede
    confundirse con "el alumno no esta matriculado"."""
    respx.post(_URL).mock(
        return_value=Response(
            200,
            json={
                "exception": "require_login_exception",
                "errorcode": "requireloginerror",
                "message": "Course or activity not accessible",
            },
        )
    )

    with pytest.raises(MoodleGradeWriteError):
        await client.lookup_userid_en_curso(
            courseid=7, idnumber="EST-001", email="a@u.edu"
        )


# ---------------------------------------------------------------------------
# MoodleIdentityMapper — ruteo entre el camino nuevo y el viejo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_el_mapper_prefiere_los_matriculados_cuando_tiene_curso_y_token(client):
    """Con curso + token del docente NO se toca `core_user_get_users_by_field`."""
    ruta = respx.post(_URL).mock(
        return_value=_matriculados({"id": 8, "idnumber": "EST-001", "email": "a@u.edu"})
    )
    mapper = MoodleIdentityMapper(moodle_client=client)

    userid = await mapper.resolve(
        idnumber="EST-001",
        email="a@u.edu",
        courseid=7,
        ws_token="token_del_docente",  # noqa: S106
    )

    assert userid == 8
    cuerpos = [c.request.content.decode() for c in ruta.calls]
    assert all("core_user_get_users_by_field" not in c for c in cuerpos)


@pytest.mark.asyncio
@respx.mock
async def test_sin_curso_sigue_por_el_camino_institucional(client):
    """`anular_nota` y compania no tienen token de docente: el camino viejo queda."""
    ruta = respx.post(_URL).mock(return_value=Response(200, json=[{"id": 42}]))
    mapper = MoodleIdentityMapper(moodle_client=client)

    userid = await mapper.resolve(idnumber="EST-001", email="a@u.edu")

    assert userid == 42
    assert "core_user_get_users_by_field" in ruta.calls[0].request.content.decode()


@pytest.mark.asyncio
@respx.mock
async def test_no_matriculado_es_un_error_accionable_no_un_fallback(client):
    """Si el alumno no esta en el curso, NO se cae al lookup institucional.

    No seria un rescate: `mod_assign_save_grade` sobre un alumno no matriculado falla
    igual. Caer al camino viejo solo cambiaria un error claro ("no esta matriculado en
    el curso") por uno opaco de Moodle, y encima reintroduciria la dependencia del
    token institucional que esta fase vino a sacar.
    """
    respx.post(_URL).mock(
        return_value=_matriculados({"id": 17, "idnumber": "OTRO", "email": "otro@u.edu"})
    )
    mapper = MoodleIdentityMapper(moodle_client=client)

    with pytest.raises(IdentityResolutionError, match="matriculado"):
        await mapper.resolve(
            idnumber="EST-001",
            email="a@u.edu",
            courseid=7,
            ws_token="token_del_docente",  # noqa: S106
        )
