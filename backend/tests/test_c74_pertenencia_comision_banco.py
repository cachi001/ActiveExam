"""C-74 post-cierre: aislamiento por comisión entre docentes de la MISMA materia.

Tres bugs reales encontrados en vivo (E2E, no en tests — cero cobertura previa):

1. `_exigir_pertenencia_materia` (banco de preguntas) rechazaba con falso
   negativo a un docente real que dicta una comisión distinta de la que
   `docente_de_materia()` (``.limit(1)`` sin filtrar por quién pregunta)
   devolvía primero.

2. `crear-desde-banco` solo validaba pertenencia a la MATERIA — un docente que
   dicta la Comisión 2 podía crear un examen apuntando a la Comisión 1 de OTRO
   docente, con solo compartir materia/banco.

3. `POST /{examen_id}/comision` (asociar examen ya importado a una comisión)
   no tenía NINGÚN chequeo de pertenencia — cualquier docente con
   `gestionar_academico` podía asociar cualquier examen a cualquier comisión.

DB real (DATABASE_URL). Sin mocks de DB. Sigue el mismo patrón que
``test_c73_pertenencia_docente.py``.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaProfesorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "materia_profesor",
    "opcion_banco",
    "pregunta_banco",
    "categoria_pregunta",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    # c-78: pertenencia del rol PROFESOR. Los tests de este archivo la usan
    # porque crear examenes y operar el banco dejaron de ser del TUTOR (E-03).
    MateriaProfesorModel.__table__,
    MateriaModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    CategoriaPreguntaModel.__table__,
    PreguntaBancoModel.__table__,
    OpcionBancoModel.__table__,
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_docente(factory, legajo: str) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=legajo,
            email=f"{legajo.lower()}@uni.edu",
            nombre="Docente",
            apellido=legajo,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_materia_con_dos_comisiones(factory, docente_c1: str, docente_c2: str | None):
    """Una materia con 2 comisiones: C1 (docente_c1) y C2 (docente_c2).

    Crea C1 primero a propósito — es el caso que gatillaba el bug 1
    (``.limit(1)`` devolvía el docente de la primera comisión creada)."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        c1 = ComisionModel(
            materia_id=materia.id, codigo=f"C1-{sufijo}", nombre="Comisión 1",
            # `docente_id` se eliminó del modelo en c-79: quién dicta una
            # comisión es una relación N:M (`comision_tutor`), que se agrega
            # abajo. El kwarg viejo había quedado y rompía el constructor.
            codigo_matriculacion=f"K1-{sufijo}",
        )
        s.add(c1)
        await s.flush()
        if docente_c1:
            s.add(ComisionTutorModel(comision_id=c1.id, tutor_id=docente_c1))
        c2 = ComisionModel(
            materia_id=materia.id, codigo=f"C2-{sufijo}", nombre="Comisión 2",
            codigo_matriculacion=f"K2-{sufijo}",
        )
        s.add(c2)
        await s.flush()
        if docente_c2:
            s.add(ComisionTutorModel(comision_id=c2.id, tutor_id=docente_c2))
        # c-78: ademas de tutor de SU comision, cada docente queda como PROFESOR
        # de la materia. Es lo que le da la capacidad `crear_examenes`/
        # `gestionar_banco` sin cambiar en nada lo que estos tests verifican: la
        # pertenencia sigue siendo "SU materia / SU comision" contra "ajena".
        for docente in (docente_c1, docente_c2):
            if docente:
                s.add(
                    MateriaProfesorModel(materia_id=materia.id, profesor_id=docente)
                )
        materia_id, c1_id, c2_id = materia.id, c1.id, c2.id
        await s.commit()
    return materia_id, c1_id, c2_id


async def _crear_examen_importado(factory, comision_id: str | None = None) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(titulo="Examen importado", comision_id=comision_id)
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


def _client(app, roles: list[str], subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


# ---------------------------------------------------------------------------
# Bug 1: docente de una comisión NO-primera de la materia no debe ser rechazado
# al operar el banco de preguntas (categorías) de su propia materia.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_de_la_segunda_comision_puede_crear_categoria_en_su_materia(app, factory):
    """RED→GREEN: antes, docente_de_materia() devolvía el docente de C1 (creada
    primero) y comparaba contra el principal — el docente de C2 era rechazado."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1-{uuid.uuid4().hex[:4]}")
    docente_c2 = await _crear_docente(factory, f"DOC-C2-{uuid.uuid4().hex[:4]}")
    materia_id, _c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2
    )

    # c-78: el banco es del PROFESOR (E-03). El actor conserva su rol tutor —
    # lo que se verifica sigue siendo la pertenencia sobre SU materia.
    async with _client(app, ["tutor", "profesor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/categorias",
            json={"materia_id": materia_id, "nombre": "Unidad 1"},
        )

    assert resp.status_code == 201, (
        "El docente de la Comisión 2 fue rechazado al operar el banco de SU "
        f"propia materia. Respuesta: {resp.status_code} {resp.text}"
    )


# ---------------------------------------------------------------------------
# Bug 2: crear-desde-banco debe validar el comision_id puntual, no solo la materia.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_un_tutor_no_puede_crear_examenes_para_ninguna_comision(app, factory):
    """El TUTOR no arma exámenes, ni para su comisión ni para la de al lado.

    Este test comprobaba otra cosa: que un docente de C2 no pudiera apuntar a C1
    de la MISMA materia (403 `comision_ajena`). Esa premisa quedó obsoleta con el
    rol PROFESOR: quien administra una materia administra TODAS sus comisiones,
    así que apuntar a otra comisión de su propia materia es legítimo y ya no
    devuelve `comision_ajena`.

    Lo que sí sigue siendo cierto, y es lo que se fija acá, es que el rol tutor no
    tiene la capacidad `crear_examenes` (c-78: "el tutor NO crea exámenes"). La
    guarda `comision_ajena` sigue viva y cubierta por el test del docente que se
    mete en una materia AJENA."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1B-{uuid.uuid4().hex[:4]}")
    docente_c2 = await _crear_docente(factory, f"DOC-C2B-{uuid.uuid4().hex[:4]}")
    materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2
    )

    # Acá el token lleva SOLO "tutor" a propósito: el tutor no tiene
    # `crear_examenes` (c-78: "el tutor NO crea exámenes"), así que el 403 llega
    # por capacidad. Agregarle "profesor" cambiaría la premisa del test — un
    # profesor administra TODA su materia, así que apuntar a otra comisión de la
    # misma materia es algo que legítimamente puede hacer. El caso de un profesor
    # metiéndose en una materia AJENA lo cubre `test_docente_ajeno_...`.
    async with _client(app, ["tutor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/crear-desde-banco",
            json={
                "titulo": "Examen colado",
                "materia_id": materia_id,
                "comision_id": c1_id,
                "sorteo": [{"categoria_id": None, "cantidad": 1}],
            },
        )

    assert resp.status_code == 403, (
        f"Un tutor pudo crear un examen. Respuesta: {resp.status_code} {resp.text}"
    )
    assert "crear_examenes" in resp.text


@pytest.mark.asyncio
async def test_docente_si_puede_crear_examen_para_su_propia_comision(app, factory):
    """Triangulación: el mismo docente SÍ puede crear un examen para su propia
    comisión (falla más adelante por falta de preguntas en el banco — 422/500 son
    aceptables acá, lo que NO debe pasar es un 403 de pertenencia)."""
    docente_c2 = await _crear_docente(factory, f"DOC-C2C-{uuid.uuid4().hex[:4]}")
    materia_id, _c1_id, c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1=None, docente_c2=docente_c2
    )

    # `crear_examenes` es capacidad del PROFESOR, no del tutor (c-78: "el tutor
    # NO crea exámenes"). El fixture ya deja a cada docente como profesor de la
    # materia; faltaba que el token lo dijera. Lo que este test verifica es la
    # PERTENENCIA, no la capacidad — sin el rol, el 403 llegaba antes y tapaba
    # justo lo que se quiere probar.
    async with _client(app, ["tutor", "profesor"], subject=docente_c2) as c:
        resp = await c.post(
            "/api/v1/exam-content/crear-desde-banco",
            json={
                "titulo": "Examen propio",
                "materia_id": materia_id,
                "comision_id": c2_id,
                "sorteo": [{"categoria_id": None, "cantidad": 1}],
            },
        )

    assert resp.status_code != 403, resp.text


# ---------------------------------------------------------------------------
# Bug 3: asociar examen importado a comisión exige pertenencia sobre la comisión.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docente_no_puede_asociar_examen_a_comision_ajena(app, factory):
    """RED→GREEN: antes este endpoint no tenía NINGÚN chequeo de pertenencia."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1D-{uuid.uuid4().hex[:4]}")
    intruso = await _crear_docente(factory, f"DOC-X-{uuid.uuid4().hex[:4]}")
    _materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2=None
    )
    examen_id = await _crear_examen_importado(factory)

    async with _client(app, ["tutor"], subject=intruso) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/comision",
            json={"comision_id": c1_id},
        )

    assert resp.status_code == 403, (
        "Cualquier docente pudo asociar un examen importado a una comisión "
        f"ajena. Respuesta: {resp.status_code} {resp.text}"
    )


@pytest.mark.asyncio
async def test_docente_dueno_si_puede_asociar_examen_a_su_comision(app, factory):
    """Triangulación: el docente titular de la comisión sí puede asociarla."""
    docente_c1 = await _crear_docente(factory, f"DOC-C1E-{uuid.uuid4().hex[:4]}")
    _materia_id, c1_id, _c2_id = await _crear_materia_con_dos_comisiones(
        factory, docente_c1, docente_c2=None
    )
    examen_id = await _crear_examen_importado(factory)

    async with _client(app, ["tutor", "profesor"], subject=docente_c1) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{examen_id}/comision",
            json={"comision_id": c1_id},
        )

    assert resp.status_code == 200, resp.text
