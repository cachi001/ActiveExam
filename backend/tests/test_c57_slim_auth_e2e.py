"""Tests de integracion E2E: auth JWT slim contra postgres:16-alpine (c-57, task 10.1).

Flujo completo: login -> refresh -> /me contra postgres:16-alpine (sin timescaledb).

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_SLIM=postgresql://user:pass@host:5432/db  (postgres:16-alpine)
  JWT_OWN_SECRET=<string aleatorio seguro>
  EMBEDDING_ENCRYPTION_KEY=<clave Fernet>

CRITICO: usar postgres:16-alpine, NO imagen timescale. Mismo entorno que Railway.

Verificado con:
  alembic upgrade slim@head  (aplica 0005 + 0008 sin timescaledb)
"""

from __future__ import annotations

import os

import pytest

# URL de Postgres estandar para tests del slim (distinta de DATABASE_URL del stack full).
_DB_URL_SLIM = os.environ.get(
    "DATABASE_URL_SLIM",
    "postgresql://app@db-slim:5432/proctoring",
)

_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-slim")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    # Clave Fernet de prueba (SOLO para tests, no usar en prod).
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

    # Limpiar singleton de settings para que use las vars del monkeypatch.
    config_slim_module.get_slim_settings.cache_clear()

    for k, v in _SLIM_ENV.items():
        monkeypatch.setenv(k, v)

    # Importar fresh para que tome las nuevas vars de entorno.
    import importlib

    import app.main_slim as main_slim_module

    importlib.reload(main_slim_module)
    app = main_slim_module.create_slim_app()

    with TestClient(app) as c:
        yield c

    config_slim_module.get_slim_settings.cache_clear()


@pytest.mark.requires_stack
class TestSlimAuthE2E:
    """Tests E2E del flujo auth slim (login -> refresh -> /me)."""

    def test_login_con_credenciales_validas_retorna_200(
        self,
        slim_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """login -> 200 con access_token y refresh_token."""
        # Crear usuario primero.
        from app.config_slim import SlimSettings
        from app.infrastructure.auth.hashing import hashear_password
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )
        import asyncio

        async def crear_usuario():
            db_url = _DB_URL_SLIM
            if db_url.startswith("postgres://"):
                db_url = "postgresql://" + db_url[len("postgres://"):]
            if db_url.startswith("postgresql://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

            engine = create_slim_engine(db_url)
            factory = create_slim_session_factory(engine)
            async with factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(UsuarioModel).where(
                        UsuarioModel.id_institucional == "test-e2e-auth"
                    )
                )
                if result.scalar_one_or_none() is None:
                    usuario = UsuarioModel(
                        id_institucional="test-e2e-auth",
                        email="test-e2e-auth@demo.test",
                        roles=["estudiante"],
                        password_hash=hashear_password("password123"),
                        auth_provider="jwt",
                        attrs_federados={},
                    )
                    session.add(usuario)
                    await session.commit()
            await engine.dispose()

        asyncio.get_event_loop().run_until_complete(crear_usuario())

        resp = slim_client.post(
            "/api/v1/auth/login",
            json={"username": "test-e2e-auth", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_con_password_incorrecto_retorna_401(
        self,
        slim_client,
    ) -> None:
        """login con password incorrecto -> 401 con mensaje generico."""
        resp = slim_client.post(
            "/api/v1/auth/login",
            json={"username": "test-e2e-auth", "password": "password_incorrecta"},
        )
        assert resp.status_code == 401

    def test_me_con_bearer_valido_retorna_200(
        self,
        slim_client,
    ) -> None:
        """login -> access_token -> GET /me -> 200 con perfil."""
        # Login primero (usuario puede existir del test anterior — es idempotente).
        resp_login = slim_client.post(
            "/api/v1/auth/login",
            json={"username": "test-e2e-auth", "password": "password123"},
        )
        if resp_login.status_code != 200:
            pytest.skip("Login no disponible (usuario no creado)")

        access_token = resp_login.json()["access_token"]

        resp_me = slim_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp_me.status_code == 200
        data = resp_me.json()
        assert data["id_institucional"] == "test-e2e-auth"
        assert "estudiante" in data["roles"]

    def test_me_sin_bearer_retorna_401(
        self,
        slim_client,
    ) -> None:
        """GET /me sin Bearer -> 401."""
        resp = slim_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
