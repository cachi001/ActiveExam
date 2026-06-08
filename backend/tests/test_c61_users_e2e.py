"""Tests de integración E2E para C-61: CRUD de usuarios, registro y foto de perfil.

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_SLIM=postgresql://user:pass@host:5432/db  (postgres:16-alpine)
  JWT_OWN_SECRET=<string aleatorio seguro>
  EMBEDDING_ENCRYPTION_KEY=<clave Fernet>

CRITICO: usar postgres:16-alpine (igual que Railway), con migración 0009 aplicada.
Tests sin mocks de DB (regla dura de código).
"""

from __future__ import annotations

import asyncio
import os

import pytest

_DB_URL_SLIM = os.environ.get(
    "DATABASE_URL_SLIM",
    "postgresql://app:pass@localhost:55432/proctoring",
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


# ---------------------------------------------------------------------------
# Fixture: slim_client apuntando a postgres:16-alpine
# ---------------------------------------------------------------------------


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
    app_instance = main_slim_module.create_slim_app()

    with TestClient(app_instance) as c:
        yield c

    config_slim_module.get_slim_settings.cache_clear()


# ---------------------------------------------------------------------------
# Helpers de fixture: crear usuarios y tokens
# ---------------------------------------------------------------------------


def _crear_usuario_db(db_url: str, id_institucional: str, email: str, roles: list, password: str):
    """Crea un usuario en la DB de test (idempotente)."""
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_slim import (
        create_slim_engine,
        create_slim_session_factory,
    )
    from sqlalchemy import delete, select

    async def _run():
        url = db_url
        if url.startswith("postgres://"):
            url2 = "postgresql://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url2 = "postgresql+asyncpg://" + url[len("postgresql://"):]
        else:
            url2 = url

        engine = create_slim_engine(url2)
        factory = create_slim_session_factory(engine)
        async with factory() as session:
            # Limpiar si ya existe
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.id_institucional == id_institucional)
            )
            await session.commit()
            usuario = UsuarioModel(
                id_institucional=id_institucional,
                email=email,
                roles=roles,
                password_hash=hashear_password(password),
                auth_provider="local",
                attrs_federados={},
            )
            session.add(usuario)
            await session.commit()
            await session.refresh(usuario)
            uid = str(usuario.id)
        await engine.dispose()
        return uid

    return asyncio.get_event_loop().run_until_complete(_run())


def _eliminar_usuario_db(db_url: str, id_institucional: str):
    """Elimina un usuario de la DB de test."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_slim import (
        create_slim_engine,
        create_slim_session_factory,
    )
    from sqlalchemy import delete

    async def _run():
        url = db_url
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]

        engine = create_slim_engine(url)
        factory = create_slim_session_factory(engine)
        async with factory() as session:
            await session.execute(
                delete(UsuarioModel).where(UsuarioModel.id_institucional == id_institucional)
            )
            await session.commit()
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_run())


def _login(client, username: str, password: str) -> str | None:
    """Realiza login y retorna el access_token o None si falla."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if resp.status_code != 200:
        return None
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 2.6: Tests CRUD de usuarios
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestUserCRUD:
    """Tests E2E del CRUD de usuarios (C-61, tareas 2.1–2.5)."""

    _ADMIN_ID = "c61-test-admin"
    _ADMIN_EMAIL = "c61-admin@demo.test"
    _ADMIN_PASS = "AdminPass123"

    _OTRO_ID = "c61-test-otro"
    _OTRO_EMAIL = "c61-otro@demo.test"
    _OTRO_PASS = "OtroPass123"

    def setup_method(self):
        """Crear usuarios de test antes de cada test."""
        _crear_usuario_db(
            _DB_URL_SLIM, self._ADMIN_ID, self._ADMIN_EMAIL, ["admin_sistema"], self._ADMIN_PASS
        )
        _crear_usuario_db(
            _DB_URL_SLIM, self._OTRO_ID, self._OTRO_EMAIL, ["estudiante"], self._OTRO_PASS
        )

    def teardown_method(self):
        """Limpiar usuarios de test."""
        _eliminar_usuario_db(_DB_URL_SLIM, self._ADMIN_ID)
        _eliminar_usuario_db(_DB_URL_SLIM, self._OTRO_ID)
        _eliminar_usuario_db(_DB_URL_SLIM, "c61-nuevo-user")

    def test_listar_usuarios_200(self, slim_client):
        """Admin lista usuarios → 200 con array y sin password_hash."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token, "Login de admin falló"

        resp = slim_client.get(
            "/api/v1/users/?limit=50&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        # Verificar que password_hash no está en la respuesta.
        for u in data["items"]:
            assert "password_hash" not in u

    def test_listar_usuarios_403_rol_insuficiente(self, slim_client):
        """Estudiante lista usuarios → 403."""
        token = _login(slim_client, self._OTRO_ID, self._OTRO_PASS)
        assert token

        resp = slim_client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_listar_usuarios_401_sin_token(self, slim_client):
        """Sin token → 401."""
        resp = slim_client.get("/api/v1/users/")
        assert resp.status_code == 401

    def test_listar_excluye_baja(self, slim_client):
        """Usuario dado de baja no aparece en el listado."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        # Buscar el id del otro usuario.
        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        usuario_otro = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._OTRO_ID),
            None,
        )
        assert usuario_otro is not None, "El usuario 'otro' debería estar en el listado"

        # Dar de baja al otro.
        resp_delete = slim_client.delete(
            f"/api/v1/users/{usuario_otro['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_delete.status_code == 204

        # Verificar que ya no aparece en el listado.
        listado2 = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        ids = [u["id_institucional"] for u in listado2.json()["items"]]
        assert self._OTRO_ID not in ids

    def test_editar_usuario_200(self, slim_client):
        """Admin edita roles del otro usuario → 200."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        # Obtener id del otro usuario.
        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        usuario_otro = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._OTRO_ID),
            None,
        )
        assert usuario_otro is not None

        resp = slim_client.put(
            f"/api/v1/users/{usuario_otro['id']}",
            json={"roles": ["proctor"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "proctor" in resp.json()["roles"]

    def test_editar_usuario_422_campo_extra(self, slim_client):
        """Campo extra (password_hash) en body → 422 por extra='forbid'."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        usuario_otro = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._OTRO_ID),
            None,
        )
        assert usuario_otro is not None

        resp = slim_client.put(
            f"/api/v1/users/{usuario_otro['id']}",
            json={"password_hash": "hacked"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_editar_usuario_404_no_existe(self, slim_client):
        """PUT sobre usuario inexistente → 404."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        resp = slim_client.put(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            json={"roles": ["estudiante"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_anti_lockout_admin_no_puede_quitarse_rol(self, slim_client):
        """Admin no puede quitarse el rol admin_sistema → 409."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        # Obtener el id del admin.
        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        admin_user = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._ADMIN_ID),
            None,
        )
        assert admin_user is not None

        resp = slim_client.put(
            f"/api/v1/users/{admin_user['id']}",
            json={"roles": ["estudiante"]},  # quitar admin_sistema de si mismo
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_baja_204(self, slim_client):
        """Admin da de baja a otro usuario → 204."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        usuario_otro = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._OTRO_ID),
            None,
        )
        assert usuario_otro is not None

        resp = slim_client.delete(
            f"/api/v1/users/{usuario_otro['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    def test_baja_usuario_no_puede_loguear(self, slim_client):
        """Usuario dado de baja no puede loguear → 401 con mensaje genérico."""
        token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert token

        listado = slim_client.get(
            "/api/v1/users/?limit=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        usuario_otro = next(
            (u for u in listado.json()["items"] if u["id_institucional"] == self._OTRO_ID),
            None,
        )
        assert usuario_otro is not None

        # Dar de baja.
        slim_client.delete(
            f"/api/v1/users/{usuario_otro['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Intentar loguear.
        resp = slim_client.post(
            "/api/v1/auth/login",
            json={"username": self._OTRO_ID, "password": self._OTRO_PASS},
        )
        assert resp.status_code == 401

    def test_baja_403_rol_insuficiente(self, slim_client):
        """Estudiante intenta dar de baja a otro → 403."""
        token = _login(slim_client, self._OTRO_ID, self._OTRO_PASS)
        assert token

        resp = slim_client.delete(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3.5: Tests de registro público
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestRegistro:
    """Tests E2E de POST /api/v1/auth/register (C-61, tarea 3.1-3.4)."""

    _REG_ID = "c61-reg-test-user"
    _REG_EMAIL = "c61-reg@demo.test"

    def teardown_method(self):
        _eliminar_usuario_db(_DB_URL_SLIM, self._REG_ID)

    def test_registro_exitoso_201(self, slim_client):
        """Registro con datos válidos → 201 con rol estudiante forzado."""
        resp = slim_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Juan",
                "apellido": "Perez",
                "id_institucional": self._REG_ID,
                "email": self._REG_EMAIL,
                "password": "Password123",
                "password_confirmacion": "Password123",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["roles"] == ["estudiante"]
        assert data["id_institucional"] == self._REG_ID

    def test_registro_rechaza_campo_roles(self, slim_client):
        """Enviar 'roles' en el body → 422 por extra='forbid'."""
        resp = slim_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Hack",
                "apellido": "Attempt",
                "id_institucional": "hacker-001",
                "email": "hacker@demo.test",
                "password": "Password123",
                "password_confirmacion": "Password123",
                "roles": ["admin_sistema"],
            },
        )
        assert resp.status_code == 422

    def test_registro_password_no_coincide(self, slim_client):
        """Passwords diferentes → 422."""
        resp = slim_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Test",
                "apellido": "User",
                "id_institucional": "reg-mismatch",
                "email": "mismatch@demo.test",
                "password": "Password123",
                "password_confirmacion": "OtroPassword",
            },
        )
        assert resp.status_code == 422

    def test_registro_password_debil(self, slim_client):
        """Password menor a 8 caracteres → 422."""
        resp = slim_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Test",
                "apellido": "User",
                "id_institucional": "reg-weak",
                "email": "weak@demo.test",
                "password": "abc",
                "password_confirmacion": "abc",
            },
        )
        assert resp.status_code == 422

    def test_registro_duplicado_409(self, slim_client):
        """Email o id_institucional duplicado → 409."""
        payload = {
            "nombre": "Dup",
            "apellido": "User",
            "id_institucional": self._REG_ID,
            "email": self._REG_EMAIL,
            "password": "Password123",
            "password_confirmacion": "Password123",
        }
        # Primer registro
        r1 = slim_client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 201

        # Segundo registro con mismo email/id_institucional
        r2 = slim_client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code == 409

    def test_registro_password_hasheado(self, slim_client):
        """El password nunca se persiste en claro en la DB."""
        resp = slim_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Hash",
                "apellido": "Test",
                "id_institucional": self._REG_ID,
                "email": self._REG_EMAIL,
                "password": "Password123",
                "password_confirmacion": "Password123",
            },
        )
        assert resp.status_code == 201

        # Verificar que el password en claro no se devuelve en la respuesta.
        data = resp.json()
        assert "password" not in data
        assert "password_hash" not in data
        assert "password_confirmacion" not in data

        # Verificar que se puede loguear (el hash es válido).
        login_resp = slim_client.post(
            "/api/v1/auth/login",
            json={"username": self._REG_ID, "password": "Password123"},
        )
        assert login_resp.status_code == 200


# ---------------------------------------------------------------------------
# 4.5: Tests de foto de perfil
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestFotoPerfil:
    """Tests E2E de GET /api/v1/enrollment/foto-perfil (C-61, tarea 4.1-4.3)."""

    _ALUMNO_ID = "c61-foto-alumno"
    _ALUMNO_EMAIL = "c61-foto@demo.test"
    _ALUMNO_PASS = "AlumnoPass123"

    _ADMIN_ID = "c61-foto-admin"
    _ADMIN_EMAIL = "c61-foto-admin@demo.test"
    _ADMIN_PASS = "AdminPass123"

    _SIN_FOTO_ID = "c61-sin-foto"
    _SIN_FOTO_EMAIL = "c61-sinfoto@demo.test"
    _SIN_FOTO_PASS = "SinFotoPass123"

    _alumno_uid: str = ""

    def setup_method(self):
        self._alumno_uid = _crear_usuario_db(
            _DB_URL_SLIM, self._ALUMNO_ID, self._ALUMNO_EMAIL, ["estudiante"], self._ALUMNO_PASS
        )
        _crear_usuario_db(
            _DB_URL_SLIM, self._ADMIN_ID, self._ADMIN_EMAIL, ["admin_sistema"], self._ADMIN_PASS
        )
        _crear_usuario_db(
            _DB_URL_SLIM, self._SIN_FOTO_ID, self._SIN_FOTO_EMAIL, ["estudiante"], self._SIN_FOTO_PASS
        )

    def teardown_method(self):
        _eliminar_usuario_db(_DB_URL_SLIM, self._ALUMNO_ID)
        _eliminar_usuario_db(_DB_URL_SLIM, self._ADMIN_ID)
        _eliminar_usuario_db(_DB_URL_SLIM, self._SIN_FOTO_ID)

    def _subir_foto(self, client, token: str) -> None:
        """Sube una foto mínima de 1x1 pixel JPEG para el alumno."""
        import base64
        # JPEG mínimo válido (1x1 pixel)
        jpeg_bytes = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD3, 0xFF, 0xD9,
        ])
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        resp = client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": data_url},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, f"Subida de foto falló: {resp.json()}"

    def test_foto_propia_200(self, slim_client):
        """Alumno obtiene su propia foto → 200 con base64."""
        token = _login(slim_client, self._ALUMNO_ID, self._ALUMNO_PASS)
        assert token

        # Subir foto primero.
        self._subir_foto(slim_client, token)

        resp = slim_client.get(
            "/api/v1/enrollment/foto-perfil",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "imagen_base64" in data
        assert data["imagen_base64"].startswith("data:image/")

    def test_foto_propia_404_sin_foto(self, slim_client):
        """Alumno sin foto → 404."""
        token = _login(slim_client, self._SIN_FOTO_ID, self._SIN_FOTO_PASS)
        assert token

        resp = slim_client.get(
            "/api/v1/enrollment/foto-perfil",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_foto_propia_401_sin_token(self, slim_client):
        """Sin token → 401."""
        resp = slim_client.get("/api/v1/enrollment/foto-perfil")
        assert resp.status_code == 401

    def test_foto_ajena_200_admin(self, slim_client):
        """Admin obtiene la foto de otro usuario → 200."""
        # Subir foto como alumno.
        alumno_token = _login(slim_client, self._ALUMNO_ID, self._ALUMNO_PASS)
        assert alumno_token
        self._subir_foto(slim_client, alumno_token)

        # Admin obtiene la foto por usuario_id.
        admin_token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert admin_token

        resp = slim_client.get(
            f"/api/v1/enrollment/foto-perfil/{self._alumno_uid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "imagen_base64" in data

    def test_foto_ajena_403_estudiante(self, slim_client):
        """Estudiante intenta ver la foto de otro → 403."""
        token = _login(slim_client, self._ALUMNO_ID, self._ALUMNO_PASS)
        assert token

        resp = slim_client.get(
            f"/api/v1/enrollment/foto-perfil/{self._alumno_uid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_foto_ajena_404_sin_foto(self, slim_client):
        """Admin pide foto de usuario sin foto → 404."""
        admin_token = _login(slim_client, self._ADMIN_ID, self._ADMIN_PASS)
        assert admin_token

        # Obtener el id del usuario sin foto.
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )
        from sqlalchemy import select

        async def _get_uid():
            url = _DB_URL_SLIM
            if url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            engine = create_slim_engine(url)
            factory = create_slim_session_factory(engine)
            async with factory() as session:
                res = await session.execute(
                    select(UsuarioModel).where(
                        UsuarioModel.id_institucional == self._SIN_FOTO_ID
                    )
                )
                u = res.scalar_one_or_none()
                uid = str(u.id) if u else None
            await engine.dispose()
            return uid

        sin_foto_uid = asyncio.get_event_loop().run_until_complete(_get_uid())
        assert sin_foto_uid

        resp = slim_client.get(
            f"/api/v1/enrollment/foto-perfil/{sin_foto_uid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
