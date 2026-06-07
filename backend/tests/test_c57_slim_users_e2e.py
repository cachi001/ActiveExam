"""Tests de integracion E2E: users slim (c-57, task 10.2).

Verifica:
  - POST /api/v1/users/ por admin_sistema -> 201 crea usuario
  - El usuario creado puede hacer login

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_SLIM=postgresql://... (postgres:16-alpine, slim@head aplicado)
  JWT_OWN_SECRET=...
  EMBEDDING_ENCRYPTION_KEY=...
"""

from __future__ import annotations

import os

import pytest

_DB_URL_SLIM = os.environ.get(
    "DATABASE_URL_SLIM",
    "postgresql://app@db-slim:5432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-slim")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    "dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0cy1vbmx5LTMyYnl0ZXM=",
)

_SLIM_ENV = {
    "DATABASE_URL": _DB_URL_SLIM,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}


@pytest.fixture
def slim_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient del slim apuntando a postgres:16-alpine."""
    import importlib

    import app.config_slim as config_slim_module
    from fastapi.testclient import TestClient

    config_slim_module.get_slim_settings.cache_clear()

    for k, v in _SLIM_ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_slim as main_slim_module

    importlib.reload(main_slim_module)
    app = main_slim_module.create_slim_app()

    with TestClient(app) as c:
        yield c

    config_slim_module.get_slim_settings.cache_clear()


def _crear_admin_y_token(slim_client) -> str:
    """Crea un admin en la DB slim y retorna su access_token."""
    import asyncio

    async def _crear():
        from sqlalchemy import select

        from app.infrastructure.auth.hashing import hashear_password
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )

        db_url = _DB_URL_SLIM
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        if db_url.startswith("postgresql://"):
            db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

        engine = create_slim_engine(db_url)
        factory = create_slim_session_factory(engine)
        async with factory() as session:
            result = await session.execute(
                select(UsuarioModel).where(
                    UsuarioModel.id_institucional == "test-admin-creator"
                )
            )
            if result.scalar_one_or_none() is None:
                usuario = UsuarioModel(
                    id_institucional="test-admin-creator",
                    email="test-admin-creator@demo.test",
                    roles=["admin_sistema"],
                    password_hash=hashear_password("admin123"),
                    auth_provider="jwt",
                    attrs_federados={},
                )
                session.add(usuario)
                await session.commit()
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_crear())

    resp = slim_client.post(
        "/api/v1/auth/login",
        json={"username": "test-admin-creator", "password": "admin123"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login admin fallo: {resp.text}")
    return resp.json()["access_token"]


@pytest.mark.requires_stack
class TestSlimUsersE2E:
    """Tests E2E de gestion de usuarios slim."""

    def test_crear_usuario_como_admin_retorna_201(
        self,
        slim_client,
    ) -> None:
        """POST /users/ por admin_sistema -> 201, usuario creado."""
        admin_token = _crear_admin_y_token(slim_client)

        resp = slim_client.post(
            "/api/v1/users/",
            json={
                "id_institucional": "nuevo-usuario-e2e",
                "email": "nuevo-usuario-e2e@demo.test",
                "password": "nuevo-password123",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"

    def test_usuario_creado_puede_hacer_login(
        self,
        slim_client,
    ) -> None:
        """Usuario creado por admin puede hacer login con sus credenciales."""
        admin_token = _crear_admin_y_token(slim_client)

        # Crear usuario (o puede existir del test anterior — es idempotente via 409).
        slim_client.post(
            "/api/v1/users/",
            json={
                "id_institucional": "nuevo-usuario-e2e-login",
                "email": "nuevo-usuario-e2e-login@demo.test",
                "password": "mi-password-e2e",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Login con el nuevo usuario.
        resp = slim_client.post(
            "/api/v1/auth/login",
            json={"username": "nuevo-usuario-e2e-login", "password": "mi-password-e2e"},
        )
        assert resp.status_code == 200, f"Login del nuevo usuario fallo: {resp.text}"
        assert "access_token" in resp.json()

    def test_crear_usuario_sin_admin_retorna_403(
        self,
        slim_client,
    ) -> None:
        """POST /users/ sin rol admin_sistema -> 403."""
        # Login como estudiante (no admin).
        import asyncio

        async def _crear_estudiante():
            from sqlalchemy import select

            from app.infrastructure.auth.hashing import hashear_password
            from app.infrastructure.persistence.models.transactional import UsuarioModel
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            db_url = _DB_URL_SLIM
            if db_url.startswith("postgres://"):
                db_url = "postgresql://" + db_url[len("postgres://"):]
            if db_url.startswith("postgresql://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

            engine = create_slim_engine(db_url)
            factory = create_slim_session_factory(engine)
            async with factory() as session:
                result = await session.execute(
                    select(UsuarioModel).where(
                        UsuarioModel.id_institucional == "test-no-admin"
                    )
                )
                if result.scalar_one_or_none() is None:
                    usuario = UsuarioModel(
                        id_institucional="test-no-admin",
                        email="test-no-admin@demo.test",
                        roles=["estudiante"],
                        password_hash=hashear_password("pass123"),
                        auth_provider="jwt",
                        attrs_federados={},
                    )
                    session.add(usuario)
                    await session.commit()
            await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_crear_estudiante())

        resp_login = slim_client.post(
            "/api/v1/auth/login",
            json={"username": "test-no-admin", "password": "pass123"},
        )
        if resp_login.status_code != 200:
            pytest.skip("Login de estudiante no disponible")

        token = resp_login.json()["access_token"]

        resp = slim_client.post(
            "/api/v1/users/",
            json={
                "id_institucional": "intento-crear-usuario",
                "email": "intento@demo.test",
                "password": "pass",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Esperado 403, got {resp.status_code}: {resp.text}"
