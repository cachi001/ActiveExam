"""PUT /users/{id} permite corregir el username, y con qué resguardos.

Por qué existe: el endpoint editaba email, nombre, apellido y roles, pero NO el
username, así que un nombre de usuario mal cargado solo se podía corregir con un
UPDATE a mano en la base. Eso pasó en producción el 29/8/2026.

Renombrar toca la identidad con la que se entra al sistema, así que hay tres
resguardos que estos tests fijan:

1. Unicidad: nadie puede quedarse con el username de otro.
2. Cruce con el email: el login matchea por ``email OR username``, así que el
   username nuevo tampoco puede ser el email de otra persona.
3. Las sesiones abiertas de esa cuenta se cortan: el token porta el username
   viejo y quedaría mintiendo hasta vencer.

Sin mocks de DB (regla dura de código): la unicidad es del índice de Postgres.
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

_PASS = "CambioUser123"


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


def _factory():
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    engine = create_activeexam_engine(_url_async(_DB_URL_ACTIVEEXAM))
    return create_activeexam_session_factory(engine), engine


def _correr(coro):
    # asyncio.run() y no get_event_loop(): en Python 3.12 no hay loop implícito en
    # el hilo principal desde un test sincrónico, y get_event_loop() revienta con
    # "There is no current event loop".
    return asyncio.run(coro)


def _crear_usuario(username: str, email: str, roles: list[str]) -> str:
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from sqlalchemy import delete, or_

    async def _run():
        factory, engine = _factory()
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
                roles=roles,
                password_hash=hashear_password(_PASS),
                auth_provider="jwt",
                attrs_federados={},
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            uid = str(u.id)
        await engine.dispose()
        return uid

    return _correr(_run())


def _borrar_usuarios(*usernames: str) -> None:
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from sqlalchemy import delete

    async def _run():
        factory, engine = _factory()
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.username.in_(usernames))
            )
            await session.commit()
        await engine.dispose()

    _correr(_run())


def _contar_refresh(usuario_id: str) -> int:
    from app.infrastructure.persistence.models.transactional import RefreshTokenModel
    from sqlalchemy import func, select

    async def _run():
        factory, engine = _factory()
        async with factory() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(RefreshTokenModel)
                    .where(RefreshTokenModel.usuario_id == usuario_id)
                )
            ).scalar_one()
        await engine.dispose()
        return n

    return _correr(_run())


def _token(client, username: str) -> str:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": _PASS})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def admin_tok(client):
    _crear_usuario("admin_cu", "admin_cu@test.local", ["admin_sistema"])
    yield _token(client, "admin_cu")
    _borrar_usuarios("admin_cu")


@pytest.mark.requires_stack
def test_renombra_y_el_usuario_entra_con_el_nombre_nuevo(client, admin_tok) -> None:
    """El caso que motivó todo: corregir un username mal cargado."""
    uid = _crear_usuario("mal_escrito", "prof_cu@test.local", ["profesor"])
    try:
        r = client.put(
            f"/api/v1/users/{uid}",
            json={"username": "bien_escrito"},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 200, r.text
        assert r.json()["username"] == "bien_escrito"

        # La prueba real no es el JSON: es que la credencial nueva sirve...
        assert _token(client, "bien_escrito")
        # ...y que la vieja ya no.
        vieja = client.post(
            "/api/v1/auth/login",
            json={"username": "mal_escrito", "password": _PASS},
        )
        assert vieja.status_code == 401
    finally:
        _borrar_usuarios("mal_escrito", "bien_escrito")


@pytest.mark.requires_stack
def test_rechaza_un_username_que_ya_tiene_otro(client, admin_tok) -> None:
    """Dos personas con el mismo username es una identidad ambigua al entrar."""
    uid = _crear_usuario("quiere_cambiar", "a_cu@test.local", ["profesor"])
    _crear_usuario("ya_ocupado", "b_cu@test.local", ["profesor"])
    try:
        r = client.put(
            f"/api/v1/users/{uid}",
            json={"username": "ya_ocupado"},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 409, r.text
    finally:
        _borrar_usuarios("quiere_cambiar", "ya_ocupado")


@pytest.mark.requires_stack
def test_rechaza_un_username_igual_al_email_de_otro(client, admin_tok) -> None:
    """El login acepta email O username: el cruce también es una colisión.

    Sin esto, quien se llame ``otro_cu@test.local`` como username se disputa la
    credencial de ingreso con quien tiene ese email.
    """
    uid = _crear_usuario("quiere_cruzar", "c_cu@test.local", ["profesor"])
    _crear_usuario("otro_duenio", "otro_cu@test.local", ["profesor"])
    try:
        r = client.put(
            f"/api/v1/users/{uid}",
            json={"username": "otro_cu@test.local"},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 409, r.text
    finally:
        _borrar_usuarios("quiere_cruzar", "otro_duenio")


@pytest.mark.requires_stack
def test_renombrar_corta_las_sesiones_abiertas(client, admin_tok) -> None:
    """El token porta el username viejo: dejarlo vivo es dejar una identidad falsa."""
    uid = _crear_usuario("con_sesion", "d_cu@test.local", ["profesor"])
    try:
        _token(client, "con_sesion")  # abre sesión: crea el refresh token
        assert _contar_refresh(uid) >= 1, "el login tiene que dejar un refresh token"

        r = client.put(
            f"/api/v1/users/{uid}",
            json={"username": "sin_sesion"},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 200, r.text
        assert _contar_refresh(uid) == 0
    finally:
        _borrar_usuarios("con_sesion", "sin_sesion")


@pytest.mark.requires_stack
def test_editar_solo_el_nombre_no_desloguea(client, admin_tok) -> None:
    """Corregir un apellido no puede echar a nadie de su examen en curso."""
    uid = _crear_usuario("sigue_igual", "e_cu@test.local", ["profesor"])
    try:
        _token(client, "sigue_igual")
        assert _contar_refresh(uid) >= 1

        r = client.put(
            f"/api/v1/users/{uid}",
            json={"nombre": "Nombre", "apellido": "Corregido"},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 200, r.text
        assert _contar_refresh(uid) >= 1, "editar el nombre no debe cortar la sesión"
    finally:
        _borrar_usuarios("sigue_igual")


@pytest.mark.requires_stack
@pytest.mark.parametrize("invalido", ["", "   ", "con espacio", "a"])
def test_rechaza_usernames_que_romperian_el_login(client, admin_tok, invalido) -> None:
    """Vacío, en blanco, con espacios o de un solo carácter no son identidades."""
    uid = _crear_usuario("valido_cu", "f_cu@test.local", ["profesor"])
    try:
        r = client.put(
            f"/api/v1/users/{uid}",
            json={"username": invalido},
            headers=_auth(admin_tok),
        )
        assert r.status_code == 422, f"aceptó {invalido!r}: {r.text}"
    finally:
        _borrar_usuarios("valido_cu")
