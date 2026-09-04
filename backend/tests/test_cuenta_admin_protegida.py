"""La cuenta admin raíz no puede ser tomada por otro administrador.

`admin_sistema` era un rol plano: cualquier admin podía, sobre CUALQUIER otro
admin, quitarle el rol, cambiarle el usuario y el correo, resetearle la contraseña
o darlo de baja. Con dos administradores en producción, eso significa que cada uno
puede desalojar al otro, y quien es dueño del sistema no tiene ninguna posición
distinta a la de un ayudante al que le dieron el rol un rato.

La cuenta raíz (la del seed) queda blindada contra los cuatro caminos que
equivalen a tomarla. Lo que NO se bloquea, a propósito: corregirle el nombre o
desbloquearla, que no son tomas de cuenta; y ella misma sigue pudiendo cambiar
todo lo suyo.
"""

from __future__ import annotations

import asyncio
import os

import pytest

_DB_URL = os.environ.get(
    "DATABASE_URL_ACTIVEEXAM",
    "postgresql://app:pass@localhost:55432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-activeexam")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    "dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0cy1vbmx5LTMyYnl0ZXM=",
)

_ENV = {
    "DATABASE_URL": _DB_URL,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}

_PROTEGIDA = "admin"
_PROTEGIDA_EMAIL = "admin@activeexam.local"
_PROTEGIDA_PASS = "ProtegidaPass123"

_OTRO = "admin-segundo-test"
_OTRO_EMAIL = "admin-segundo@demo.test"
_OTRO_PASS = "SegundoPass123"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    import importlib

    import app.config_activeexam as config_activeexam_module
    from fastapi.testclient import TestClient

    config_activeexam_module.get_activeexam_settings.cache_clear()
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_activeexam as main_activeexam_module

    importlib.reload(main_activeexam_module)
    app_instance = main_activeexam_module.create_activeexam_app()

    with TestClient(app_instance) as c:
        yield c

    config_activeexam_module.get_activeexam_settings.cache_clear()


def _url_async(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def _crear(username: str, email: str, roles: list[str], password: str) -> str:
    from sqlalchemy import delete, or_

    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    async def _run() -> str:
        engine = create_activeexam_engine(_url_async(_DB_URL))
        factory = create_activeexam_session_factory(engine)
        try:
            async with factory() as session:
                await session.execute(
                    delete(UsuarioModel).where(
                        or_(
                            UsuarioModel.username == username,
                            UsuarioModel.email == email,
                        )
                    )
                )
                await session.commit()
                usuario = UsuarioModel(
                    username=username,
                    email=email,
                    roles=roles,
                    password_hash=hashear_password(password),
                    auth_provider="local",
                    attrs_federados={},
                )
                session.add(usuario)
                await session.commit()
                await session.refresh(usuario)
                return str(usuario.id)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def _borrar(usernames: list[str]) -> None:
    """Deja la base como estaba: sin esto, los usuarios que crea este módulo
    desbalancean los conteos del módulo que corra después (lo destapó
    ``test_users_filtros_reactivar::test_estado_todos_incluye_ambos``)."""
    from sqlalchemy import delete

    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    async def _run() -> None:
        engine = create_activeexam_engine(_url_async(_DB_URL))
        factory = create_activeexam_session_factory(engine)
        try:
            async with factory() as session:
                await session.execute(
                    delete(UsuarioModel).where(UsuarioModel.username.in_(usernames))
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())


def _login(client, username: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.requires_stack
class TestCuentaAdminProtegida:
    _CREADOS = [
        _PROTEGIDA,
        _OTRO,
        "admin-tercero-test",
        "baja-inmediata-test",
    ]

    def setup_method(self) -> None:
        self.id_protegida = _crear(
            _PROTEGIDA, _PROTEGIDA_EMAIL, ["admin_sistema"], _PROTEGIDA_PASS
        )
        self.id_otro = _crear(_OTRO, _OTRO_EMAIL, ["admin_sistema"], _OTRO_PASS)

    def teardown_method(self) -> None:
        _borrar(self._CREADOS)

    def _auth_otro(self, client) -> dict[str, str]:
        return {"Authorization": f"Bearer {_login(client, _OTRO, _OTRO_PASS)}"}

    def test_otro_admin_no_puede_quitarle_el_rol(self, client) -> None:
        resp = client.put(
            f"/api/v1/users/{self.id_protegida}",
            json={"roles": ["estudiante"]},
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 409, resp.text

    def test_otro_admin_no_puede_cambiarle_la_credencial_de_ingreso(
        self, client
    ) -> None:
        """Cambiarle el usuario o el correo es quedarse con su forma de entrar."""
        resp = client.put(
            f"/api/v1/users/{self.id_protegida}",
            json={"email": "secuestrada@demo.test"},
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 409, resp.text

        resp = client.put(
            f"/api/v1/users/{self.id_protegida}",
            json={"username": "admin-secuestrada"},
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 409, resp.text

    def test_otro_admin_no_puede_darla_de_baja(self, client) -> None:
        resp = client.delete(
            f"/api/v1/users/{self.id_protegida}", headers=self._auth_otro(client)
        )
        assert resp.status_code == 409, resp.text

    def test_otro_admin_no_puede_resetearle_la_contrasena(self, client) -> None:
        resp = client.post(
            f"/api/v1/users/{self.id_protegida}/resetear-password",
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 409, resp.text

    def test_otro_admin_si_puede_corregirle_el_nombre(self, client) -> None:
        """La protección es contra la toma de la cuenta, no un candado total."""
        resp = client.put(
            f"/api/v1/users/{self.id_protegida}",
            json={"nombre": "Emiliano"},
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["nombre"] == "Emiliano"

    def test_la_cuenta_protegida_sigue_administrando_su_propio_correo(
        self, client
    ) -> None:
        token = _login(client, _PROTEGIDA, _PROTEGIDA_PASS)
        resp = client.put(
            f"/api/v1/users/{self.id_protegida}",
            json={"email": "admin-nuevo@activeexam.local"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text

    def test_dar_de_baja_saca_a_la_persona_en_el_acto(self, client) -> None:
        """Antes seguía operando hasta 15 minutos con el token que ya tenía."""
        victima = _crear("baja-inmediata-test", "baja-inmediata@demo.test", ["tutor"], "VictimaPass123")
        token_victima = _login(client, "baja-inmediata-test", "VictimaPass123")
        cabecera = {"Authorization": f"Bearer {token_victima}"}

        assert client.get("/api/v1/auth/me", headers=cabecera).status_code == 200

        baja = client.delete(f"/api/v1/users/{victima}", headers=self._auth_otro(client))
        assert baja.status_code == 204, baja.text

        # Mismo token, sin esperar a que venza.
        assert client.get("/api/v1/auth/me", headers=cabecera).status_code == 401

    def test_las_demas_cuentas_admin_se_siguen_pudiendo_editar(self, client) -> None:
        """El blindaje es de UNA cuenta, no de todo el rol."""
        otra = _crear("admin-tercero-test", "admin-tercero@demo.test", ["admin_sistema"], "TerceroPass123")
        resp = client.put(
            f"/api/v1/users/{otra}",
            json={"roles": ["estudiante"]},
            headers=self._auth_otro(client),
        )
        assert resp.status_code == 200, resp.text
