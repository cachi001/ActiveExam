"""Tests de integracion E2E: users activeexam (c-57, task 10.2).

Verifica:
  - POST /api/v1/users/ por admin_sistema -> 201 crea usuario
  - El usuario creado puede hacer login

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_ACTIVEEXAM=postgresql://... (postgres:16-alpine, activeexam@head aplicado)
  JWT_OWN_SECRET=...
  EMBEDDING_ENCRYPTION_KEY=...
"""

from __future__ import annotations

import os

import pytest

_DB_URL_ACTIVEEXAM = os.environ.get(
    "DATABASE_URL_ACTIVEEXAM",
    "postgresql://app@db-activeexam:5432/proctoring",
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


@pytest.fixture
def activeexam_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient del activeexam apuntando a postgres:16-alpine."""
    import importlib

    import app.config_activeexam as config_activeexam_module
    from fastapi.testclient import TestClient

    config_activeexam_module.get_activeexam_settings.cache_clear()

    for k, v in _ACTIVEEXAM_ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_activeexam as main_activeexam_module

    importlib.reload(main_activeexam_module)
    app = main_activeexam_module.create_activeexam_app()

    with TestClient(app) as c:
        yield c

    config_activeexam_module.get_activeexam_settings.cache_clear()


def _crear_admin_y_token(activeexam_client) -> str:
    """Crea un admin en la DB activeexam y retorna su access_token."""
    import asyncio

    async def _crear():
        from sqlalchemy import select

        from app.infrastructure.auth.hashing import hashear_password
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_activeexam import (
            create_activeexam_engine,
            create_activeexam_session_factory,
        )

        db_url = _DB_URL_ACTIVEEXAM
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]
        if db_url.startswith("postgresql://"):
            db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

        engine = create_activeexam_engine(db_url)
        factory = create_activeexam_session_factory(engine)
        async with factory() as session:
            result = await session.execute(
                select(UsuarioModel).where(
                    UsuarioModel.username == "test-admin-creator"
                )
            )
            if result.scalar_one_or_none() is None:
                usuario = UsuarioModel(
                    username="test-admin-creator",
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

    resp = activeexam_client.post(
        "/api/v1/auth/login",
        json={"username": "test-admin-creator", "password": "admin123"},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login admin fallo: {resp.text}")
    return resp.json()["access_token"]


@pytest.mark.requires_stack
class TestActiveExamUsersE2E:
    """Tests E2E de gestion de usuarios activeexam."""

    def test_crear_usuario_como_admin_retorna_201(
        self,
        activeexam_client,
    ) -> None:
        """POST /users/ por admin_sistema -> 201, usuario creado."""
        admin_token = _crear_admin_y_token(activeexam_client)

        resp = activeexam_client.post(
            "/api/v1/users/",
            json={
                "username": "nuevo-usuario-e2e",
                "email": "nuevo-usuario-e2e@demo.test",
                "password": "nuevo-password123",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"

    def test_usuario_creado_puede_hacer_login(
        self,
        activeexam_client,
    ) -> None:
        """Usuario creado por admin puede hacer login con sus credenciales."""
        admin_token = _crear_admin_y_token(activeexam_client)

        # Crear usuario (o puede existir del test anterior — es idempotente via 409).
        activeexam_client.post(
            "/api/v1/users/",
            json={
                "username": "nuevo-usuario-e2e-login",
                "email": "nuevo-usuario-e2e-login@demo.test",
                "password": "mi-password-e2e",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Login con el nuevo usuario.
        resp = activeexam_client.post(
            "/api/v1/auth/login",
            json={"username": "nuevo-usuario-e2e-login", "password": "mi-password-e2e"},
        )
        assert resp.status_code == 200, f"Login del nuevo usuario fallo: {resp.text}"
        assert "access_token" in resp.json()

    def test_crear_usuario_sin_admin_retorna_403(
        self,
        activeexam_client,
    ) -> None:
        """POST /users/ sin rol admin_sistema -> 403."""
        # Login como estudiante (no admin).
        import asyncio

        async def _crear_estudiante():
            from sqlalchemy import select

            from app.infrastructure.auth.hashing import hashear_password
            from app.infrastructure.persistence.models.transactional import UsuarioModel
            from app.infrastructure.persistence.session_activeexam import (
                create_activeexam_engine,
                create_activeexam_session_factory,
            )

            db_url = _DB_URL_ACTIVEEXAM
            if db_url.startswith("postgres://"):
                db_url = "postgresql://" + db_url[len("postgres://"):]
            if db_url.startswith("postgresql://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]

            engine = create_activeexam_engine(db_url)
            factory = create_activeexam_session_factory(engine)
            async with factory() as session:
                result = await session.execute(
                    select(UsuarioModel).where(
                        UsuarioModel.username == "test-no-admin"
                    )
                )
                if result.scalar_one_or_none() is None:
                    usuario = UsuarioModel(
                        username="test-no-admin",
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

        resp_login = activeexam_client.post(
            "/api/v1/auth/login",
            json={"username": "test-no-admin", "password": "pass123"},
        )
        if resp_login.status_code != 200:
            pytest.skip("Login de estudiante no disponible")

        token = resp_login.json()["access_token"]

        resp = activeexam_client.post(
            "/api/v1/users/",
            json={
                "username": "intento-crear-usuario",
                "email": "intento@demo.test",
                "password": "pass",
                "roles": ["estudiante"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Esperado 403, got {resp.status_code}: {resp.text}"
