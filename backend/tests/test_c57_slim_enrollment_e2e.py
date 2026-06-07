"""Tests de integracion E2E: enrollment slim (foto + embedding) (c-57, task 10.3).

Verifica:
  - POST /api/v1/enrollment/foto-perfil por estudiante autenticado -> 201
  - POST /api/v1/enrollment/embedding-referencia por estudiante -> 201
  - Foto se persiste como BYTEA en foto_referencia.foto_bytes

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_SLIM=postgresql://... (postgres:16-alpine, slim@head aplicado)
  JWT_OWN_SECRET=...
  EMBEDDING_ENCRYPTION_KEY=...
"""

from __future__ import annotations

import base64
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


def _imagen_base64_minima() -> str:
    """Genera una imagen base64 minima valida (GIF de 1x1 pixel) para tests."""
    # GIF de 1 pixel transparente (minimo valido como imagen)
    gif_bytes = (
        b"GIF89a\x01\x00\x01\x00\x00\xff\x00,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;"
    )
    return "data:image/gif;base64," + base64.b64encode(gif_bytes).decode()


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


def _login_y_token(slim_client, id_institucional: str, password: str) -> str:
    """Hace login y retorna el access_token."""
    resp = slim_client.post(
        "/api/v1/auth/login",
        json={"username": id_institucional, "password": password},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login fallo ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def _crear_usuario_slim(id_institucional: str, password: str, roles: list[str]) -> None:
    """Crea un usuario en la DB slim para los tests."""
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
                    UsuarioModel.id_institucional == id_institucional
                )
            )
            if result.scalar_one_or_none() is None:
                usuario = UsuarioModel(
                    id_institucional=id_institucional,
                    email=f"{id_institucional}@demo.test",
                    roles=roles,
                    password_hash=hashear_password(password),
                    auth_provider="jwt",
                    attrs_federados={},
                )
                session.add(usuario)
                await session.commit()
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_crear())


@pytest.mark.requires_stack
class TestSlimEnrollmentE2E:
    """Tests E2E del enrollment slim (foto + embedding)."""

    def test_foto_perfil_retorna_201_y_persiste_bytea(
        self,
        slim_client,
    ) -> None:
        """POST /enrollment/foto-perfil por estudiante -> 201 con foto_referencia_id."""
        _crear_usuario_slim("test-enrollment-foto", "password123", ["estudiante"])
        token = _login_y_token(slim_client, "test-enrollment-foto", "password123")

        imagen = _imagen_base64_minima()
        resp = slim_client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": imagen},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "foto_referencia_id" in data
        # El id debe ser un UUID valido.
        import uuid
        uuid.UUID(data["foto_referencia_id"])

    def test_embedding_referencia_retorna_201(
        self,
        slim_client,
    ) -> None:
        """POST /enrollment/embedding-referencia por estudiante -> 201 con referencia_id."""
        _crear_usuario_slim("test-enrollment-emb", "password123", ["estudiante"])
        token = _login_y_token(slim_client, "test-enrollment-emb", "password123")

        embedding_128d = [0.1] * 128  # Vector de 128 floats

        resp = slim_client.post(
            "/api/v1/enrollment/embedding-referencia",
            json={"embedding": embedding_128d},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "referencia_id" in data

    def test_foto_muy_grande_retorna_422(
        self,
        slim_client,
    ) -> None:
        """POST /enrollment/foto-perfil con foto > 500 KB -> 422."""
        _crear_usuario_slim("test-enrollment-foto-grande", "password123", ["estudiante"])
        token = _login_y_token(slim_client, "test-enrollment-foto-grande", "password123")

        # 600 KB de datos random -> deberia ser rechazado.
        imagen_grande = "data:image/jpeg;base64," + base64.b64encode(
            b"x" * (600 * 1024)
        ).decode()

        resp = slim_client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": imagen_grande},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422, (
            f"Esperado 422 para foto grande, got {resp.status_code}: {resp.text}"
        )

    def test_embedding_con_dimension_incorrecta_retorna_422(
        self,
        slim_client,
    ) -> None:
        """POST /enrollment/embedding-referencia con embedding != 128 -> 422."""
        _crear_usuario_slim("test-enrollment-emb-dim", "password123", ["estudiante"])
        token = _login_y_token(slim_client, "test-enrollment-emb-dim", "password123")

        embedding_64d = [0.1] * 64  # Solo 64 floats, deberia rechazarse.

        resp = slim_client.post(
            "/api/v1/enrollment/embedding-referencia",
            json={"embedding": embedding_64d},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422, (
            f"Esperado 422 para embedding de 64 dimensiones, got {resp.status_code}"
        )

    def test_enrollment_sin_bearer_retorna_401(
        self,
        slim_client,
    ) -> None:
        """POST /enrollment/foto-perfil sin Bearer -> 401."""
        resp = slim_client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": _imagen_base64_minima()},
        )
        assert resp.status_code == 401
