"""El servidor bloquea a quien todavía no definió sus credenciales.

Antes este gate vivía SOLO en el navegador: `RequireAuth` mostraba la pantalla de
"creá tu contraseña" y no dejaba pasar a ninguna ruta protegida. Pero ningún
endpoint lo verificaba, así que quien supiera usar herramientas de desarrollo podía
operar la API con el token del launch LTI sin haber definido usuario ni contraseña.
Regla dura #6 del proyecto: el cliente es un sensor no confiable, y un control que
solo vive en el cliente no es un control.

Lo que el gate NO puede romper: la persona tiene que poder salir de ese estado. Por
eso `/auth/me` (para que la app sepa en qué estado está) y `/auth/change-password`
(para resolverlo) siguen abiertos, y hay tests que lo fijan.

Sin mocks de DB (regla dura de código).
"""

from __future__ import annotations

import asyncio
import os

import pytest

_DB_URL_ACTIVEEXAM = os.environ.get(
    "DATABASE_URL_ACTIVEEXAM",
    "postgresql://app:pass@localhost:55432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-activeexam")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    "dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0cy1vbmx5LTMyYnl0ZXM=",
)

_ACTIVEEXAM_ENV = {
    "DATABASE_URL": _DB_URL_ACTIVEEXAM,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}

_TEMPORAL = "Temporal2026"
_DEFINITIVA = "Definitiva2026"

#: Endpoint protegido cualquiera, representativo del resto de la API.
_RUTA_PROTEGIDA = "/api/v1/exam-content/materias"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    import importlib

    import app.config_activeexam as config_activeexam_module
    from fastapi.testclient import TestClient

    config_activeexam_module.get_activeexam_settings.cache_clear()
    for k, v in _ACTIVEEXAM_ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_activeexam as main_activeexam_module

    importlib.reload(main_activeexam_module)
    app_instance = main_activeexam_module.create_activeexam_app()
    with TestClient(app_instance) as c:
        yield c
    config_activeexam_module.get_activeexam_settings.cache_clear()


def _url_async(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _correr(coro):
    return asyncio.run(coro)


def _crear_usuario(username: str, email: str, *, pendiente: bool) -> str:
    """Crea un usuario local; ``pendiente`` = todavía no definió sus credenciales."""
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )
    from sqlalchemy import delete, or_

    async def _run():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(
                    or_(UsuarioModel.username == username, UsuarioModel.email == email)
                )
            )
            await session.commit()
            u = UsuarioModel(
                username=username,
                email=email,
                roles=["profesor"],
                password_hash=hashear_password(_TEMPORAL),
                auth_provider="jwt",
                attrs_federados={},
                debe_cambiar_password=pendiente,
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            uid = str(u.id)
        await engine.dispose()
        return uid

    return _correr(_run())


def _borrar(*usernames: str) -> None:
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )
    from sqlalchemy import delete

    async def _run():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.username.in_(usernames))
            )
            await session.commit()
        await engine.dispose()

    _correr(_run())


def _token(client, username: str, password: str = _TEMPORAL) -> str:
    r = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.requires_stack
def test_no_puede_operar_la_api_sin_definir_sus_credenciales(client) -> None:
    """El corazón del arreglo: el token del primer ingreso no habilita la API."""
    _crear_usuario("pend_api", "pend_api@test.local", pendiente=True)
    try:
        tok = _token(client, "pend_api")
        r = client.get(_RUTA_PROTEGIDA, headers=_auth(tok))
        assert r.status_code == 403, r.text
        assert "credenciales" in r.text.lower()
    finally:
        _borrar("pend_api")


@pytest.mark.requires_stack
def test_puede_consultar_su_propio_estado(client) -> None:
    """Sin /auth/me la app no puede ni saber que tiene que mostrar la pantalla."""
    _crear_usuario("pend_me", "pend_me@test.local", pendiente=True)
    try:
        tok = _token(client, "pend_me")
        r = client.get("/api/v1/auth/me", headers=_auth(tok))
        assert r.status_code == 200, r.text
        assert r.json()["debe_cambiar_password"] is True
    finally:
        _borrar("pend_me")


@pytest.mark.requires_stack
def test_puede_definir_su_contrasena_y_queda_habilitado(client) -> None:
    """La salida del estado tiene que funcionar, y dejar la sesión usable.

    Si el token nuevo no llegara con la marca limpia, la persona quedaría
    encerrada: sin poder operar y sin nada más que cambiar.
    """
    _crear_usuario("pend_sale", "pend_sale@test.local", pendiente=True)
    try:
        tok = _token(client, "pend_sale")

        r = client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_actual": _TEMPORAL, "contrasena_nueva": _DEFINITIVA},
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text

        token_nuevo = r.json().get("access_token")
        assert token_nuevo, "tiene que devolver un token con la marca ya limpia"

        ok = client.get(_RUTA_PROTEGIDA, headers=_auth(token_nuevo))
        assert ok.status_code == 200, ok.text
    finally:
        _borrar("pend_sale")


@pytest.mark.requires_stack
def test_quien_ya_definio_sus_credenciales_no_se_ve_afectado(client) -> None:
    """El gate no puede molestar a los usuarios normales, que son casi todos."""
    _crear_usuario("normal_api", "normal_api@test.local", pendiente=False)
    try:
        tok = _token(client, "normal_api")
        r = client.get(_RUTA_PROTEGIDA, headers=_auth(tok))
        assert r.status_code == 200, r.text
    finally:
        _borrar("normal_api")


@pytest.mark.requires_stack
def test_el_alumno_que_entra_por_el_campus_tampoco_puede_operar(client) -> None:
    """El caso que motivó el arreglo, con el camino propio de LTI.

    La cuenta nace desde el campus con un username sintético (``lti:1:7``) y sin
    contraseña, así que su primer set NO pide contraseña anterior. Igual no puede
    tocar la API hasta elegir usuario y contraseña, y al hacerlo queda habilitado.
    """
    from app.infrastructure.auth.own_issuer import emitir_jwt_propio
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )
    from sqlalchemy import delete, select

    async def _crear_lti():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.username == "lti:1:999")
            )
            await session.commit()
            u = UsuarioModel(
                username="lti:1:999",
                email="alumno_lti@test.local",
                roles=["estudiante"],
                password_hash=None,
                auth_provider="lti",
                attrs_federados={},
                debe_cambiar_password=True,
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            # issuer/audience: los defaults de ActiveExamSettings, que es lo que
            # valida la app levantada por el fixture.
            tok = emitir_jwt_propio(
                u,
                secret=_JWT_SECRET,
                issuer="activeexam-auth",
                audience="activeexam",
            )
        await engine.dispose()
        return tok

    async def _limpiar():
        engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            ids = (
                await session.execute(
                    select(UsuarioModel.id).where(
                        UsuarioModel.email == "alumno_lti@test.local"
                    )
                )
            ).scalars().all()
            if ids:
                await session.execute(
                    delete(UsuarioModel).where(UsuarioModel.id.in_(ids))
                )
                await session.commit()
        await engine.dispose()

    tok = _correr(_crear_lti())
    try:
        bloqueado = client.get(_RUTA_PROTEGIDA, headers=_auth(tok))
        assert bloqueado.status_code == 403, bloqueado.text

        # Primer set LTI: sin contraseña anterior, pero el username es obligatorio.
        r = client.put(
            "/api/v1/auth/change-password",
            json={"contrasena_nueva": _DEFINITIVA, "nuevo_username": "alumno.real"},
            headers=_auth(tok),
        )
        assert r.status_code == 200, r.text
        token_nuevo = r.json()["access_token"]

        ok = client.get(_RUTA_PROTEGIDA, headers=_auth(token_nuevo))
        assert ok.status_code == 200, ok.text
    finally:
        _correr(_limpiar())


@pytest.mark.requires_stack
def test_el_login_de_quien_esta_pendiente_sigue_funcionando(client) -> None:
    """Bloquear el login lo dejaría afuera del sistema, no adentro del gate."""
    _crear_usuario("pend_login", "pend_login@test.local", pendiente=True)
    try:
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "pend_login", "password": _TEMPORAL},
        )
        assert r.status_code == 200, r.text
        assert r.json()["access_token"]
    finally:
        _borrar("pend_login")
