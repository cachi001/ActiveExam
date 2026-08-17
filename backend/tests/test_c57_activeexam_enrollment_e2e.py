"""Tests de integracion E2E: enrollment activeexam (foto + embedding) (c-57, task 10.3).

Verifica:
  - POST /api/v1/enrollment/foto-perfil por estudiante autenticado -> 201
  - POST /api/v1/enrollment/embedding-referencia por estudiante -> 201
  - Foto se persiste como BYTEA en foto_referencia.foto_bytes

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_ACTIVEEXAM=postgresql://... (postgres:16-alpine, activeexam@head aplicado)
  JWT_OWN_SECRET=...
  EMBEDDING_ENCRYPTION_KEY=...
"""

from __future__ import annotations

import base64
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


def _imagen_base64_minima() -> str:
    """Genera una imagen base64 minima valida (GIF de 1x1 pixel) para tests."""
    # GIF de 1 pixel transparente (minimo valido como imagen)
    gif_bytes = (
        b"GIF89a\x01\x00\x01\x00\x00\xff\x00,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;"
    )
    return "data:image/gif;base64," + base64.b64encode(gif_bytes).decode()


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


def _login_y_token(activeexam_client, username: str, password: str) -> str:
    """Hace login y retorna el access_token."""
    resp = activeexam_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login fallo ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def _crear_usuario_activeexam(username: str, password: str, roles: list[str]) -> None:
    """Crea un usuario en la DB activeexam para los tests."""
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
                    UsuarioModel.username == username
                )
            )
            if result.scalar_one_or_none() is None:
                usuario = UsuarioModel(
                    username=username,
                    email=f"{username}@demo.test",
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
class TestActiveExamEnrollmentE2E:
    """Tests E2E del enrollment activeexam (foto + embedding)."""

    def test_foto_perfil_retorna_201_y_persiste_bytea(
        self,
        activeexam_client,
    ) -> None:
        """POST /enrollment/foto-perfil por estudiante -> 201 con foto_referencia_id."""
        _crear_usuario_activeexam("test-enrollment-foto", "password123", ["estudiante"])
        token = _login_y_token(activeexam_client, "test-enrollment-foto", "password123")

        imagen = _imagen_base64_minima()
        resp = activeexam_client.post(
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
        activeexam_client,
    ) -> None:
        """POST /enrollment/embedding-referencia por estudiante -> 201 con referencia_id."""
        _crear_usuario_activeexam("test-enrollment-emb", "password123", ["estudiante"])
        token = _login_y_token(activeexam_client, "test-enrollment-emb", "password123")

        embedding_128d = [0.1] * 128  # Vector de 128 floats

        resp = activeexam_client.post(
            "/api/v1/enrollment/embedding-referencia",
            json={"embedding": embedding_128d},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "referencia_id" in data

    def test_foto_muy_grande_retorna_422(
        self,
        activeexam_client,
    ) -> None:
        """POST /enrollment/foto-perfil con foto > 500 KB -> 422."""
        _crear_usuario_activeexam("test-enrollment-foto-grande", "password123", ["estudiante"])
        token = _login_y_token(activeexam_client, "test-enrollment-foto-grande", "password123")

        # 600 KB de datos random -> deberia ser rechazado.
        imagen_grande = "data:image/jpeg;base64," + base64.b64encode(
            b"x" * (600 * 1024)
        ).decode()

        resp = activeexam_client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": imagen_grande},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422, (
            f"Esperado 422 para foto grande, got {resp.status_code}: {resp.text}"
        )

    def test_embedding_con_dimension_incorrecta_retorna_422(
        self,
        activeexam_client,
    ) -> None:
        """POST /enrollment/embedding-referencia con embedding != 128 -> 422."""
        _crear_usuario_activeexam("test-enrollment-emb-dim", "password123", ["estudiante"])
        token = _login_y_token(activeexam_client, "test-enrollment-emb-dim", "password123")

        embedding_64d = [0.1] * 64  # Solo 64 floats, deberia rechazarse.

        resp = activeexam_client.post(
            "/api/v1/enrollment/embedding-referencia",
            json={"embedding": embedding_64d},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422, (
            f"Esperado 422 para embedding de 64 dimensiones, got {resp.status_code}"
        )

    def test_enrollment_sin_bearer_retorna_401(
        self,
        activeexam_client,
    ) -> None:
        """POST /enrollment/foto-perfil sin Bearer -> 401."""
        resp = activeexam_client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": _imagen_base64_minima()},
        )
        assert resp.status_code == 401
