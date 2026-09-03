"""Tests de auth/RBAC sobre los endpoints de proctoring activeexam (endurecimiento por rol).

Los endpoints de proctoring activeexam son COMPARTIDOS alumno/proctor. Este modulo
verifica el contrato de autorizacion tras el endurecimiento:

  - Solo autenticado (cualquier token valido): crear sesion, eventos, chat,
    pausas (solicitar / poll / reanudar), finalizar sesion.
  - Proctor + admin_sistema: GET /sessions, GET /sessions/{id},
    GET /pausas/pendientes, PATCH /pausas/{id}.

DELETE /sessions/{id} (C-76 tarea 20) es admin-only y SOLO acepta sesiones
modo='test' (diagnostico, SIN examen real). Las sesiones modo='examen' quedan
PERMANENTEMENTE protegidas — la evidencia academica no se borra, se preserva
con cadena de custodia (regla dura #6/#7, tarea 16) — sin excepciones, ni
siquiera para admin_sistema.

Sin Bearer -> 401. Rol insuficiente -> 403. Postgres real (sin mocks de DB).

Correr con:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_rbac_guards.py -v
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.proctoring.conftest import auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"

# UUID inexistente para los casos donde solo nos interesa el codigo de auth
# (401/403 se evaluan ANTES que el 404 del recurso).
_FAKE_ID = "00000000-0000-0000-0000-000000000000"

_ESTUDIANTE = auth_headers(["estudiante"])
# c-76 eliminó el rol proctor y el coordinador pasó a supervisar, pero c-79 lo
# ACOTÓ por pertenencia: alcanza las sesiones de SUS materias, no todas. Sobre una
# sesión de diagnóstico, que no cuelga de ninguna comisión, recibe 403. El único
# alcance institucional hoy es admin_sistema.
_PROCTOR = auth_headers(["coordinador"])
_ADMIN = auth_headers(["admin_sistema"])


async def _crear_sesion(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        f"{_BASE}/sessions", json={"modo": "test"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ===========================================================================
# (a) 401 sin token — endpoints proctor-only y admin-only
# ===========================================================================


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_BASE}/sessions"),
        ("GET", f"{_BASE}/sessions/{_FAKE_ID}"),
        ("GET", f"{_BASE}/pausas/pendientes"),
        ("PATCH", f"{_BASE}/pausas/{_FAKE_ID}"),
    ],
)
async def test_sin_token_401(client_noauth: AsyncClient, method: str, path: str) -> None:
    """Sin Bearer -> 401 en los endpoints restringidos (proctor-only / admin-only)."""
    if method == "GET":
        resp = await client_noauth.get(path)
    elif method == "PATCH":
        resp = await client_noauth.patch(
            path, json={"accion": "aprobar", "tutor_actor": "x"}
        )
    else:
        resp = await client_noauth.request(method, path)
    assert resp.status_code == 401, resp.text


# ===========================================================================
# (b) 403 estudiante en endpoints proctor-only / admin-only
# ===========================================================================


async def test_estudiante_listar_sesiones_403(client_noauth: AsyncClient) -> None:
    """GET /sessions con rol estudiante -> 403 (es vista del proctor)."""
    resp = await client_noauth.get(f"{_BASE}/sessions", headers=_ESTUDIANTE)
    assert resp.status_code == 403, resp.text


async def test_estudiante_detalle_sesion_403(client_noauth: AsyncClient) -> None:
    """GET /sessions/{id} con rol estudiante -> 403 (detalle del proctor)."""
    resp = await client_noauth.get(f"{_BASE}/sessions/{_FAKE_ID}", headers=_ESTUDIANTE)
    assert resp.status_code == 403, resp.text


async def test_estudiante_pausas_pendientes_403(client_noauth: AsyncClient) -> None:
    """GET /pausas/pendientes con rol estudiante -> 403 (poll del proctor)."""
    resp = await client_noauth.get(f"{_BASE}/pausas/pendientes", headers=_ESTUDIANTE)
    assert resp.status_code == 403, resp.text


async def test_estudiante_resolver_pausa_403(client_noauth: AsyncClient) -> None:
    """PATCH /pausas/{id} con rol estudiante -> 403 (aprobar/rechazar es del proctor)."""
    resp = await client_noauth.patch(
        f"{_BASE}/pausas/{_FAKE_ID}",
        json={"accion": "aprobar", "tutor_actor": "x"},
        headers=_ESTUDIANTE,
    )
    assert resp.status_code == 403, resp.text


# ===========================================================================
# (c) Proctor OK en los endpoints proctor-only
# ===========================================================================


async def test_proctor_listar_sesiones_200(client_noauth: AsyncClient) -> None:
    """GET /sessions con rol proctor -> 200."""
    resp = await client_noauth.get(f"{_BASE}/sessions", headers=_PROCTOR)
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


async def test_supervisor_institucional_detalle_sesion_200(
    client_noauth: AsyncClient,
) -> None:
    """GET /sessions/{id} con alcance institucional -> 200 sobre una sesion existente."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.get(f"{_BASE}/sessions/{sid}", headers=_ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == sid


async def test_coordinador_sin_pertenencia_detalle_403(client_noauth: AsyncClient) -> None:
    """c-79: el coordinador NO es institucional. Sin pertenencia sobre la sesion,
    403 'sesion_ajena' aunque el rol tenga la capacidad de supervisar."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.get(f"{_BASE}/sessions/{sid}", headers=_PROCTOR)
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["error"] == "sesion_ajena"


async def test_proctor_pausas_pendientes_200(client_noauth: AsyncClient) -> None:
    """GET /pausas/pendientes con rol proctor -> 200."""
    resp = await client_noauth.get(f"{_BASE}/pausas/pendientes", headers=_PROCTOR)
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


async def test_supervisor_institucional_resolver_pausa_200(
    client_noauth: AsyncClient,
) -> None:
    """PATCH /pausas/{id} con alcance institucional -> 200 (aprueba la pausa pedida)."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp_p = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "bano"}, headers=_ESTUDIANTE
    )
    assert resp_p.status_code == 201, resp_p.text
    pid = resp_p.json()["id"]
    resp = await client_noauth.patch(
        f"{_BASE}/pausas/{pid}",
        json={"accion": "aprobar", "tutor_actor": "doc-1"},
        headers=_ADMIN,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "aprobada"


# ===========================================================================
# (d) DELETE /sessions/{id}: admin-only, SOLO modo='test' (C-76 tarea 20)
# ===========================================================================


async def test_delete_sesion_sin_token_401(client_noauth: AsyncClient) -> None:
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.delete(f"{_BASE}/sessions/{sid}")
    assert resp.status_code == 401, resp.text


async def test_delete_sesion_proctor_403_no_es_admin(client_noauth: AsyncClient) -> None:
    """Solo admin_sistema puede borrar — coordinador (ex-proctor) NO, aunque
    tenga `supervisar_vivo`: borrar es un privilegio MAS restrictivo que supervisar."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.delete(f"{_BASE}/sessions/{sid}", headers=_PROCTOR)
    assert resp.status_code == 403, resp.text


async def test_delete_sesion_modo_examen_nunca_se_borra_ni_para_admin(
    client_noauth: AsyncClient,
) -> None:
    """Regla dura #6/#7: la evidencia academica real (modo='examen') queda
    PERMANENTEMENTE protegida — admin_sistema recibe 409, nunca 204."""
    resp_crear = await client_noauth.post(
        f"{_BASE}/sessions", json={"modo": "examen"}, headers=_ESTUDIANTE
    )
    assert resp_crear.status_code == 201, resp_crear.text
    sid = resp_crear.json()["id"]

    resp = await client_noauth.delete(f"{_BASE}/sessions/{sid}", headers=_ADMIN)
    assert resp.status_code == 409, resp.text
    assert resp.status_code != 204


async def test_delete_sesion_modo_test_admin_204(client_noauth: AsyncClient) -> None:
    """Sesion de diagnostico (modo='test', SIN examen real vinculado): admin
    SI puede eliminarla."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.delete(f"{_BASE}/sessions/{sid}", headers=_ADMIN)
    assert resp.status_code == 204, resp.text

    resp_get = await client_noauth.get(f"{_BASE}/sessions/{sid}", headers=_ADMIN)
    assert resp_get.status_code == 404


# ===========================================================================
# (e) Admin SI puede ver la vista del proctor
# ===========================================================================


async def test_admin_listar_sesiones_200(client_noauth: AsyncClient) -> None:
    """admin_sistema tambien puede ver la vista del proctor (GET /sessions)."""
    resp = await client_noauth.get(f"{_BASE}/sessions", headers=_ADMIN)
    assert resp.status_code == 200, resp.text


# ===========================================================================
# (f) El alumno (estudiante autenticado) SIGUE pudiendo operar su flujo
# ===========================================================================


async def test_estudiante_crear_sesion_201(client_noauth: AsyncClient) -> None:
    """El alumno crea su sesion (solo autenticado)."""
    resp = await client_noauth.post(
        f"{_BASE}/sessions", json={"modo": "test"}, headers=_ESTUDIANTE
    )
    assert resp.status_code == 201, resp.text


async def test_estudiante_ingestar_evento_201(client_noauth: AsyncClient) -> None:
    """El alumno manda eventos de deteccion (solo autenticado)."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "bajo",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "face_count_cliente": 1,
        },
        headers=_ESTUDIANTE,
    )
    assert resp.status_code == 201, resp.text


async def test_estudiante_chat_post_y_get(client_noauth: AsyncClient) -> None:
    """El alumno responde y lee el chat (solo autenticado, autor por schema).

    D4: el alumno NO inicia el hilo, así que el tutor escribe primero. Este test
    asumía que podía abrirlo él y por eso rompía contra la regla del producto."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp_tutor = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "¿todo bien?"},
        headers=_ADMIN,
    )
    assert resp_tutor.status_code == 201, resp_tutor.text
    resp_post = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "hola profe"},
        headers=_ESTUDIANTE,
    )
    assert resp_post.status_code == 201, resp_post.text
    resp_get = await client_noauth.get(
        f"{_BASE}/sessions/{sid}/chat", headers=_ESTUDIANTE
    )
    assert resp_get.status_code == 200, resp_get.text
    assert len(resp_get.json()) == 2


async def test_estudiante_no_puede_iniciar_el_chat(client_noauth: AsyncClient) -> None:
    """D4: sin un mensaje previo del tutor, el alumno no abre el hilo."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "hola?"},
        headers=_ESTUDIANTE,
    )
    assert resp.status_code == 403, resp.text


async def test_estudiante_pausa_solicitar_poll_y_reanudar(
    client_noauth: AsyncClient,
) -> None:
    """El alumno solicita pausa, la pollea, y la reanuda (finalizar) tras aprobacion."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)

    # Solicita
    resp_sol = await client_noauth.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "bano"}, headers=_ESTUDIANTE
    )
    assert resp_sol.status_code == 201, resp_sol.text
    pid = resp_sol.json()["id"]

    # Pollea las pausas de su sesion
    resp_poll = await client_noauth.get(
        f"{_BASE}/sessions/{sid}/pausas", headers=_ESTUDIANTE
    )
    assert resp_poll.status_code == 200, resp_poll.text

    # El supervisor aprueba (necesario para que el alumno pueda finalizar)
    resp_apr = await client_noauth.patch(
        f"{_BASE}/pausas/{pid}",
        json={"accion": "aprobar", "tutor_actor": "doc-1"},
        headers=_ADMIN,
    )
    assert resp_apr.status_code == 200, resp_apr.text

    # El alumno reanuda (finalizar pausa)
    resp_fin = await client_noauth.patch(
        f"{_BASE}/pausas/{pid}/finalizar", headers=_ESTUDIANTE
    )
    assert resp_fin.status_code == 200, resp_fin.text
    assert resp_fin.json()["estado"] == "finalizada"


async def test_estudiante_finalizar_sesion_200(client_noauth: AsyncClient) -> None:
    """El alumno finaliza su sesion (solo autenticado)."""
    sid = await _crear_sesion(client_noauth, _ESTUDIANTE)
    resp = await client_noauth.patch(
        f"{_BASE}/sessions/{sid}/finalizar", headers=_ESTUDIANTE
    )
    assert resp.status_code == 200, resp.text
