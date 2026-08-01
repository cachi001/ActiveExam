"""`_auditar_credencial` escribe `modulo=MOODLE` + `entidad=USUARIO` explícitos,
separado de la config institucional del campus (`modulo=CONFIGURACION`) — C-73 §13.

Ejercita el endpoint real (`PUT`/`DELETE /config/moodle/mi-credencial`) contra
DB real y lee el `audit_log` directo para verificar la clasificación. Con
`token` (no `password`) para no depender de HTTP real a Moodle.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.credencial_docente_service import CredencialDocenteService
from app.application.moodle.credencial_service import MoodleCredencialResolver
from app.application.moodle.intentos_fallidos_tracker import IntentosFallidosTracker
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.config.router import router as config_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_KEY = "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
_BASE = "https://campus.test"


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
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.state.credencial_docente = CredencialDocenteService(
        session_factory=factory, cipher=SecretCipher(key=_KEY)
    )
    application.state.moodle_credenciales = MoodleCredencialResolver(
        session_factory=factory,
        cipher=SecretCipher(key=_KEY),
        env_base_url=_BASE,
        env_token="institucional",  # noqa: S106
    )
    application.state.moodle_intentos_fallidos = IntentosFallidosTracker(umbral=5)
    application.include_router(config_router, prefix="/api/v1/config")
    return application


@pytest_asyncio.fixture
async def service_shortname(factory):
    """El canje contraseña→token exige `service=` — sin esto Moodle nunca se
    llega a consultar. Fila institucional (id=1), se borra al terminar."""
    async with factory() as s:
        await s.execute(
            text(
                "INSERT INTO moodle_credencial (id, base_url, component, service_shortname) "
                "VALUES (1, :base_url, 'mod_assign', 'api_moodle_test') "
                "ON CONFLICT (id) DO UPDATE SET service_shortname = 'api_moodle_test'"
            ),
            {"base_url": _BASE},
        )
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("DELETE FROM moodle_credencial WHERE id = 1"))
        await s.commit()


@pytest_asyncio.fixture
async def docente_id(factory):
    legajo = f"D-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(id_institucional=legajo, email=f"{legajo.lower()}@uni.edu")
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    yield uid
    async with factory() as s:
        await s.execute(text("DELETE FROM usuario WHERE id = :i"), {"i": uid})
        await s.commit()


def _client(app, subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["docente"], subject=subject),
    )


async def _filas_de_auditoria(factory, usuario_id: str) -> list[tuple[str, str | None, str | None]]:
    async with factory() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT accion, modulo, entidad FROM audit_log "
                    "WHERE entidad_id = :uid ORDER BY timestamp"
                ),
                {"uid": usuario_id},
            )
        ).all()
    return [tuple(r) for r in rows]


@pytest.mark.asyncio
async def test_conectar_audita_modulo_moodle_entidad_usuario(app, factory, docente_id):
    async with _client(app, subject=docente_id) as c:
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )
    assert resp.status_code == 200, resp.text

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == [("moodle_credencial.conectar", "MOODLE", "USUARIO")]


@pytest.mark.asyncio
async def test_recargar_credencial_ya_sana_no_genera_fila_nueva(app, factory, docente_id):
    """RENOVAR significa 'hacia falta' (C-73 §12/§13): si ya estaba activa y
    sana, volver a cargarla no es un evento de seguridad distinto — no se
    audita de nuevo, solo se extiende el plazo en silencio."""
    async with _client(app, subject=docente_id) as c:
        await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-renovado-5678"},
        )
    assert resp.status_code == 200, resp.text

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == [("moodle_credencial.conectar", "MOODLE", "USUARIO")]


@pytest.mark.asyncio
async def test_renovar_si_estaba_vencida(app, factory, docente_id):
    async with _client(app, subject=docente_id) as c:
        await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )
        async with factory() as s:
            await s.execute(
                text(
                    "UPDATE moodle_credencial_docente SET actualizado_en = "
                    "now() - interval '31 days' WHERE usuario_id = :uid"
                ),
                {"uid": docente_id},
            )
            await s.commit()
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-renovado-5678"},
        )
    assert resp.status_code == 200, resp.text

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == [
        ("moodle_credencial.conectar", "MOODLE", "USUARIO"),
        ("moodle_credencial.renovar", "MOODLE", "USUARIO"),
    ]


@pytest.mark.asyncio
async def test_renovar_si_estaba_caida(app, factory, docente_id):
    async with _client(app, subject=docente_id) as c:
        await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )
        async with factory() as s:
            await s.execute(
                text(
                    "UPDATE moodle_credencial_docente SET estado = 'caida' "
                    "WHERE usuario_id = :uid"
                ),
                {"uid": docente_id},
            )
            await s.commit()
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-renovado-5678"},
        )
    assert resp.status_code == 200, resp.text

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == [
        ("moodle_credencial.conectar", "MOODLE", "USUARIO"),
        ("moodle_credencial.renovar", "MOODLE", "USUARIO"),
    ]


@pytest.mark.asyncio
async def test_desconectar_audita_modulo_moodle(app, factory, docente_id):
    async with _client(app, subject=docente_id) as c:
        await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )
        resp = await c.delete("/api/v1/config/moodle/mi-credencial")
    assert resp.status_code == 200, resp.text

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas[-1] == ("moodle_credencial.desconectar", "MOODLE", "USUARIO")


@pytest.mark.asyncio
async def test_ninguna_fila_de_credencial_personal_cae_en_modulo_configuracion(
    app, factory, docente_id
):
    """La separación que motivó el fix: filtrar Auditoría por CONFIGURACION no
    debe traer nada de la credencial PERSONAL del docente."""
    async with _client(app, subject=docente_id) as c:
        await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "token": "t0ken-emitido-1234"},
        )

    filas = await _filas_de_auditoria(factory, docente_id)
    assert all(modulo == "MOODLE" for _, modulo, _ in filas)
    assert not any(modulo == "CONFIGURACION" for _, modulo, _ in filas)


def _mock_invalidlogin():
    respx.post(f"{_BASE}/login/token.php").mock(
        return_value=httpx.Response(
            200, json={"error": "Acceso inválido", "errorcode": "invalidlogin"}
        )
    )


@pytest.mark.asyncio
@respx.mock
async def test_intento_fallido_individual_no_audita_nada(
    app, factory, docente_id, service_shortname
):
    """Un solo typo no es un evento de auditoría — recién a partir del umbral."""
    _mock_invalidlogin()
    async with _client(app, subject=docente_id) as c:
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "password": "mala-clave-1"},
        )
    assert resp.status_code == 422

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == []


@pytest.mark.asyncio
@respx.mock
async def test_al_quinto_intento_fallido_seguido_audita_una_vez(
    app, factory, docente_id, service_shortname
):
    _mock_invalidlogin()
    async with _client(app, subject=docente_id) as c:
        for _ in range(5):
            resp = await c.put(
                "/api/v1/config/moodle/mi-credencial",
                json={"moodle_username": "jperez", "password": "mala-clave-1"},
            )
            assert resp.status_code == 422

    filas = await _filas_de_auditoria(factory, docente_id)
    assert filas == [("moodle_credencial.intentos_fallidos", "MOODLE", "USUARIO")]


@pytest.mark.asyncio
@respx.mock
async def test_un_intento_correcto_reinicia_el_contador_de_fallidos(
    app, factory, docente_id, service_shortname
):
    """Conectar bien borra el contador: 4 fallos + 1 éxito + 4 fallos más NO
    llega al umbral (serían 8 seguidos sin el reset)."""
    _mock_invalidlogin()
    async with _client(app, subject=docente_id) as c:
        for _ in range(4):
            await c.put(
                "/api/v1/config/moodle/mi-credencial",
                json={"moodle_username": "jperez", "password": "mala-clave-1"},
            )
        respx.post(f"{_BASE}/login/token.php").mock(
            return_value=httpx.Response(200, json={"token": "token-bueno-1234"})
        )
        ok = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "password": "clave-correcta"},
        )
        assert ok.status_code == 200
        _mock_invalidlogin()
        for _ in range(4):
            await c.put(
                "/api/v1/config/moodle/mi-credencial",
                json={"moodle_username": "jperez", "password": "mala-clave-1"},
            )

    filas = await _filas_de_auditoria(factory, docente_id)
    assert ("moodle_credencial.intentos_fallidos", "MOODLE", "USUARIO") not in filas
