"""Tests de integración — vínculo proctoring_session ↔ examen_contenido (C-69).

El alumno rinde un examen importado de Moodle XML (examen_contenido). La sesión de
proctoring debe REGISTRAR contra qué contenido rindió, server-side, para que la
revisión humana y el flujo del alumno sepan qué examen se respondió.

VÍNCULO (decisión de la rama activeexam): vive en ``proctoring_session.examen_contenido_id``
(NULLABLE, FK ON DELETE SET NULL a examen_contenido.id, migración activeexam 0027). La
tabla ``examen`` (config de proctoring) NO existe en activeexam; ``examen_contenido`` y
``proctoring_session`` SÍ coexisten — por eso el vínculo va acá.

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de código).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from tests.proctoring.conftest import auth_headers, dar_perfil_completo

_PROCTOR = auth_headers(["coordinador"])  # c-76: rol proctor eliminado -> coordinador supervisa

pytestmark = pytest.mark.asyncio


async def _crear_examen_contenido(db: AsyncSession, titulo: str = "Final de Análisis I") -> str:
    """Inserta un examen_contenido real y devuelve su id (UUID server-side)."""
    examen = ExamenContenidoModel(titulo=titulo)
    db.add(examen)
    await db.commit()
    await db.refresh(examen)
    return examen.id


@pytest.mark.asyncio
async def test_crear_sesion_con_examen_contenido_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /sessions con examen_contenido_id → 201 y la respuesta lo refleja."""
    # Rendir exige perfil completo (consentimiento + biometria + foto): el
    # alumno del test pasa por lo mismo que uno de verdad.
    await dar_perfil_completo(db_session)
    examen_contenido_id = await _crear_examen_contenido(db_session)

    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={
            "modo": "examen",
            "etiqueta": "rendición real",
            "examen_contenido_id": examen_contenido_id,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["examen_contenido_id"] == examen_contenido_id


@pytest.mark.asyncio
async def test_obtener_sesion_devuelve_examen_contenido_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /sessions/{id} devuelve el examen_contenido_id vinculado al crear."""
    examen_contenido_id = await _crear_examen_contenido(db_session, "Parcial de Física")

    create = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_contenido_id},
    )
    session_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_PROCTOR
    )
    assert resp.status_code == 200
    assert resp.json()["examen_contenido_id"] == examen_contenido_id


@pytest.mark.asyncio
async def test_crear_sesion_sin_examen_contenido_id_es_null(
    client: AsyncClient,
) -> None:
    """Sesión sin contenido sigue siendo válida: examen_contenido_id = null (NULLABLE)."""
    create = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "etiqueta": "prueba libre"},
    )
    assert create.status_code == 201
    assert create.json()["examen_contenido_id"] is None

    session_id = create.json()["id"]
    detalle = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_PROCTOR
    )
    assert detalle.status_code == 200
    assert detalle.json()["examen_contenido_id"] is None


@pytest.mark.asyncio
async def test_borrar_contenido_pone_el_vinculo_en_null(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """ON DELETE SET NULL: borrar el examen_contenido desvincula la sesión, no la borra.

    L2.5 / cadena de custodia: la sesión y su evidencia NUNCA se borran por un cambio
    en el catálogo de contenido — solo se pierde la referencia.
    """
    examen_contenido_id = await _crear_examen_contenido(db_session, "Examen efímero")

    create = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_contenido_id},
    )
    session_id = create.json()["id"]

    # Borrar el contenido: el FK ON DELETE SET NULL nulea el vínculo a nivel DB.
    await db_session.execute(
        delete(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_contenido_id)
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{session_id}", headers=_PROCTOR
    )
    assert resp.status_code == 200  # la sesión sobrevive
    assert resp.json()["examen_contenido_id"] is None  # el vínculo se nuleó


@pytest.mark.asyncio
async def test_examen_contenido_id_campo_extra_sigue_rechazado(
    client: AsyncClient,
) -> None:
    """extra='forbid' sigue vigente con el campo nuevo en juego (no afloja el schema)."""
    resp = await client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "test", "examen_contenido_id": None, "otro": "x"},
    )
    assert resp.status_code == 422
