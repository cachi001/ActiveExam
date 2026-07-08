"""C-69: inscripción de alumnos a comisiones + listado con elegibilidad.

Endpoints (admin-only, mismo guard que el resto de exam-content):
- POST   /api/v1/exam-content/comisiones/{comision_id}/inscripciones  → 201
- DELETE /api/v1/exam-content/comisiones/{comision_id}/inscripciones/{usuario_id} → 204
- GET    /api/v1/exam-content/comisiones/{comision_id}/alumnos         → 200

Reglas verificadas:
- Inscribir un alumno → 201 {id, usuario_id, comision_id}.
- Inscribir dos veces el mismo (usuario, comisión) → 409 'duplicado'.
- Comisión inexistente → 404 'comision_no_encontrada'.
- Usuario inexistente → 404 'usuario_no_encontrado'.
- Eliminar inscripción existente → 204; eliminar inexistente → 404.
- GET alumnos: alumno recién inscripto SIN consentimiento ni biometría →
  puede_rendir=False con razon que menciona ambos.
- GET alumnos: alumno con consentimiento 'otorgado' + embedding de referencia
  vigente → puede_rendir=True, razon=None.

Sin mocks de DB (regla dura): requieren DATABASE_URL real (pytest.skip si falta).
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
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401 -- registra tablas
    ComisionModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401 -- registra tabla
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401 -- registra tablas
    ConsentimientoPerfilModel,
    EmbeddingReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.biometric_reference import (
    EmbeddingReferenciaRepository,
)
from app.infrastructure.persistence.repositories.consent_perfil import (
    ConsentimientoPerfilSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

# Orden de DROP (CASCADE cubre las FKs). Las tablas hijas primero por prolijidad.
_TABLES = (
    "inscripcion",
    "embedding_referencia",
    "consentimiento_perfil",
    "comision",
    "materia",
    "usuario",
)

_UUID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Fixtures sin DB (tests de auth 403)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_noauth():
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=None), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures con DB real
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        # create_all ordena por dependencias (usuario/materia antes que comision/
        # inscripcion; usuario antes que consent/embedding).
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                UsuarioModel.__table__,
                MateriaModel.__table__,
                ComisionModel.__table__,
                InscripcionModel.__table__,
                ConsentimientoPerfilModel.__table__,
                EmbeddingReferenciaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def client_admin(factory):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"], mfa=False),
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers de datos (inserción directa — sin mocks)
# ---------------------------------------------------------------------------


async def _crear_usuario(
    factory,
    *,
    id_institucional: str,
    nombre: str | None = "Ana",
    apellido: str | None = "García",
    email: str = "alumno@uni.edu",
) -> str:
    """Inserta un usuario estudiante y devuelve su id."""
    async with factory() as s:
        usuario = UsuarioModel(
            id=str(uuid.uuid4()),
            id_institucional=id_institucional,
            email=email,
            roles=["estudiante"],
            nombre=nombre,
            apellido=apellido,
        )
        s.add(usuario)
        await s.commit()
        return usuario.id


async def _crear_comision(factory, *, codigo_materia: str, codigo_comision: str) -> str:
    """Inserta materia + comisión y devuelve el id de la comisión."""
    async with factory() as s:
        materia = MateriaModel(
            id=str(uuid.uuid4()), codigo=codigo_materia, nombre="Materia"
        )
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            id=str(uuid.uuid4()),
            materia_id=materia.id,
            codigo=codigo_comision,
            nombre="Comisión",
            # C-70 hizo codigo_matriculacion NOT NULL + UNIQUE; el sufijo aleatorio
            # evita colisiones entre tests que reusan los mismos códigos.
            codigo_matriculacion=f"{codigo_materia}-{codigo_comision}-{uuid.uuid4().hex[:6]}",
        )
        s.add(comision)
        await s.commit()
        return comision.id


# ---------------------------------------------------------------------------
# Inscribir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inscribir_alumno_201(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-1", codigo_comision="C-1"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-1")

    resp = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"]
    assert data["usuario_id"] == usuario_id
    assert data["comision_id"] == comision_id


@pytest.mark.asyncio
async def test_inscribir_duplicado_409(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-2", codigo_comision="C-2"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-2")

    primera = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert primera.status_code == 201, primera.text

    repetida = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert repetida.status_code == 409, repetida.text
    assert repetida.json()["detail"]["error"] == "duplicado"


@pytest.mark.asyncio
async def test_inscribir_comision_inexistente_404(client_admin, factory):
    usuario_id = await _crear_usuario(factory, id_institucional="A-3")
    resp = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{_UUID_INEXISTENTE}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "comision_no_encontrada"


@pytest.mark.asyncio
async def test_inscribir_usuario_inexistente_404(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-4", codigo_comision="C-4"
    )
    resp = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": _UUID_INEXISTENTE},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "usuario_no_encontrado"


@pytest.mark.asyncio
async def test_inscribir_extra_forbid_422(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-5", codigo_comision="C-5"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-5")
    resp = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id, "desconocido": 1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Eliminar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eliminar_inscripcion_204(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-6", codigo_comision="C-6"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-6")
    alta = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert alta.status_code == 201, alta.text

    resp = await client_admin.delete(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones/{usuario_id}"
    )
    assert resp.status_code == 204, resp.text

    # Ya no aparece en el listado de la comisión.
    alumnos = await client_admin.get(
        f"/api/v1/exam-content/comisiones/{comision_id}/alumnos"
    )
    assert alumnos.status_code == 200
    assert all(a["usuario_id"] != usuario_id for a in alumnos.json())


@pytest.mark.asyncio
async def test_eliminar_inscripcion_inexistente_404(client_admin, factory):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-7", codigo_comision="C-7"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-7")
    resp = await client_admin.delete(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones/{usuario_id}"
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "inscripcion_no_encontrada"


# ---------------------------------------------------------------------------
# GET alumnos + elegibilidad
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alumnos_comision_inexistente_404(client_admin):
    resp = await client_admin.get(
        f"/api/v1/exam-content/comisiones/{_UUID_INEXISTENTE}/alumnos"
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"]["error"] == "comision_no_encontrada"


@pytest.mark.asyncio
async def test_alumno_sin_consentimiento_ni_biometria_no_puede_rendir(
    client_admin, factory
):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-8", codigo_comision="C-8"
    )
    usuario_id = await _crear_usuario(
        factory,
        id_institucional="A-8",
        nombre="Beto",
        apellido="López",
        email="beto@uni.edu",
    )
    alta = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert alta.status_code == 201, alta.text

    resp = await client_admin.get(
        f"/api/v1/exam-content/comisiones/{comision_id}/alumnos"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    alumno = data[0]
    assert alumno["usuario_id"] == usuario_id
    assert alumno["id_institucional"] == "A-8"
    assert alumno["nombre"] == "Beto"
    assert alumno["apellido"] == "López"
    assert alumno["email"] == "beto@uni.edu"
    assert alumno["consentimiento_vigente"] is False
    assert alumno["biometria_vigente"] is False
    assert alumno["puede_rendir"] is False
    # La razón menciona AMBOS faltantes.
    assert "consentimiento" in alumno["razon"].lower()
    assert "biometr" in alumno["razon"].lower()


@pytest.mark.asyncio
async def test_alumno_con_consentimiento_y_biometria_puede_rendir(
    client_admin, factory
):
    comision_id = await _crear_comision(
        factory, codigo_materia="MAT-9", codigo_comision="C-9"
    )
    usuario_id = await _crear_usuario(factory, id_institucional="A-9")
    alta = await client_admin.post(
        f"/api/v1/exam-content/comisiones/{comision_id}/inscripciones",
        json={"usuario_id": usuario_id},
    )
    assert alta.status_code == 201, alta.text

    # Sembrar consentimiento 'otorgado' + embedding de referencia vigente
    # reusando los repos de producción (sin mocks).
    async with factory() as s:
        await ConsentimientoPerfilSqlRepository(s).registrar(
            usuario_id=usuario_id,
            version_texto="v1",
            hash_texto="h" * 64,
            estado="otorgado",
        )
        await EmbeddingReferenciaRepository(s).crear(
            usuario_id=usuario_id,
            embedding_cifrado="fernet-token-opaco",
        )
        await s.commit()

    resp = await client_admin.get(
        f"/api/v1/exam-content/comisiones/{comision_id}/alumnos"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    alumno = data[0]
    assert alumno["consentimiento_vigente"] is True
    assert alumno["biometria_vigente"] is True
    assert alumno["puede_rendir"] is True
    assert alumno["razon"] is None


# ---------------------------------------------------------------------------
# Auth (sin DB): estudiante no puede operar inscripciones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inscribir_estudiante_403(client_noauth):
    resp = await client_noauth.post(
        f"/api/v1/exam-content/comisiones/{_UUID_INEXISTENTE}/inscripciones",
        json={"usuario_id": _UUID_INEXISTENTE},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_listar_alumnos_estudiante_403(client_noauth):
    resp = await client_noauth.get(
        f"/api/v1/exam-content/comisiones/{_UUID_INEXISTENTE}/alumnos",
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403
