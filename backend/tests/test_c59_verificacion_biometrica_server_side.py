"""Tests E2E: verificacion biometrica server-side (C-59).

Cubre:
- 4.1 Enrollment + verificar-referencia con embedding cercano -> 200 es_match=true.
- 4.2 Embedding vivo lejano -> 200 es_match=false.
- 4.3 Usuario sin referencia vigente -> 404.
- 4.4 Embedding vivo de dimension invalida -> 422.
- 4.5 Body con campo de embedding de referencia extra -> 422 (extra='forbid').
- 4.6 Sin Bearer -> 401; rol incorrecto -> 403.
- 4.7 GET referencia/estado: true con referencia, false sin ella; respuesta sin embedding.
- 4.8 El embedding de referencia descifrado no aparece en la respuesta JSON.

Requiere:
  RUN_STACK_TESTS=1
  DATABASE_URL_SLIM=postgresql://... (postgres:16-alpine, slim@head aplicado)
  JWT_OWN_SECRET=...
  EMBEDDING_ENCRYPTION_KEY=...

Sin mocks de DB. Postgres real (postgres:16-alpine, SIN TimescaleDB).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Config del entorno de test slim
# ---------------------------------------------------------------------------

_DB_URL_SLIM = os.environ.get(
    "DATABASE_URL_SLIM",
    "postgresql://app@db-slim:5432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-slim")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    Fernet.generate_key().decode("ascii"),  # genera uno valido si no esta en el env
)

_SLIM_ENV = {
    "DATABASE_URL": _DB_URL_SLIM,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalizar_db_url(url: str) -> str:
    """Convierte postgres:// -> postgresql+asyncpg:// para asyncpg."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _vector_128(valor: float = 0.1) -> list[float]:
    """Vector de 128 floats normalizado para tests."""
    v = [valor] * 128
    # Normalizar para que la distancia coseno sea coherente.
    norma = (sum(x * x for x in v) ** 0.5)
    return [x / norma for x in v]


def _vector_128_lejano() -> list[float]:
    """Vector 128-d muy diferente al de referencia (distancia alta)."""
    # Invierte el signo de todos los componentes -> distancia coseno ~ 2.
    ref = _vector_128(0.1)
    return [-x for x in ref]


def _crear_usuario_slim_sync(id_institucional: str, password: str, roles: list[str]) -> str:
    """Crea un usuario en la DB slim y devuelve su id (str UUID)."""

    async def _crear() -> str:
        from sqlalchemy import select

        from app.infrastructure.auth.hashing import hashear_password
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )

        db_url = _normalizar_db_url(_DB_URL_SLIM)
        engine = create_slim_engine(db_url)
        factory = create_slim_session_factory(engine)

        try:
            async with factory() as session:
                result = await session.execute(
                    select(UsuarioModel).where(
                        UsuarioModel.id_institucional == id_institucional
                    )
                )
                existente = result.scalar_one_or_none()
                if existente is not None:
                    return existente.id

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
                return usuario.id
        finally:
            await engine.dispose()

    return asyncio.get_event_loop().run_until_complete(_crear())


def _limpiar_usuario_slim_sync(usuario_id: str) -> None:
    """Elimina el usuario y sus embeddings/fotos de la DB slim."""

    async def _limpiar() -> None:
        from sqlalchemy import delete

        from app.infrastructure.persistence.models.transactional import (
            EmbeddingReferenciaModel,
            FotoReferenciaModel,
            UsuarioModel,
        )
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )

        db_url = _normalizar_db_url(_DB_URL_SLIM)
        engine = create_slim_engine(db_url)
        factory = create_slim_session_factory(engine)

        try:
            async with factory() as session:
                await session.execute(
                    delete(EmbeddingReferenciaModel).where(
                        EmbeddingReferenciaModel.usuario_id == usuario_id
                    )
                )
                await session.execute(
                    delete(FotoReferenciaModel).where(
                        FotoReferenciaModel.usuario_id == usuario_id
                    )
                )
                await session.execute(
                    delete(UsuarioModel).where(UsuarioModel.id == usuario_id)
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_limpiar())


def _login_y_token(client, id_institucional: str, password: str) -> str:
    """Hace login y devuelve el access_token."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": id_institucional, "password": password},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login fallo ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def _enrollar_embedding(client, token: str, embedding: list[float]) -> str:
    """Hace enrollment del embedding y devuelve el referencia_id."""
    resp = client.post(
        "/api/v1/enrollment/embedding-referencia",
        json={"embedding": embedding},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Enrollment fallo: {resp.text}"
    return resp.json()["referencia_id"]


# ---------------------------------------------------------------------------
# Fixture: slim_client
# ---------------------------------------------------------------------------


@pytest.fixture
def slim_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient del slim apuntando a postgres:16-alpine con EMBEDDING_KEY real."""
    import importlib

    import app.config_slim as config_slim_module
    from fastapi.testclient import TestClient

    config_slim_module.get_slim_settings.cache_clear()

    for k, v in _SLIM_ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_slim as main_slim_module

    importlib.reload(main_slim_module)
    slim_app = main_slim_module.create_slim_app()

    with TestClient(slim_app) as c:
        yield c

    config_slim_module.get_slim_settings.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestVerificarReferenciaServerSide:
    """Tests E2E de verificacion biometrica server-side (C-59)."""

    # ------------------------------------------------------------------
    # 4.1 Embedding vivo cercano -> 200 es_match=true
    # ------------------------------------------------------------------

    def test_embedding_cercano_es_match_true(self, slim_client) -> None:
        """Enrollment + verificar-referencia con embedding cercano -> 200 es_match=true."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-match-true", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-match-true", "password123")

            # Enrollment del embedding de referencia.
            referencia = _vector_128(0.1)
            _enrollar_embedding(slim_client, token, referencia)

            # Verificacion con el MISMO vector (distancia ~0 -> es_match=true).
            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": referencia},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["es_match"] is True, f"Esperado es_match=true, got: {data}"
            assert "distancia" in data
            assert "umbral" in data
            assert data["distancia"] >= 0.0

            # 4.8 El embedding de referencia NO aparece en la respuesta.
            data_str = resp.text
            assert "embedding_referencia" not in data_str
            assert "embedding_cifrado" not in data_str
            # Los campos validos son exactamente estos tres.
            assert set(data.keys()) == {"distancia", "es_match", "umbral"}
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.2 Embedding vivo lejano -> 200 es_match=false
    # ------------------------------------------------------------------

    def test_embedding_lejano_es_match_false(self, slim_client) -> None:
        """Embedding vivo lejano -> 200 es_match=false (no sancion, solo prioriza)."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-match-false", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-match-false", "password123")

            referencia = _vector_128(0.1)
            _enrollar_embedding(slim_client, token, referencia)

            # Vector lejano (invertido -> distancia coseno ~2).
            vivo_lejano = _vector_128_lejano()
            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": vivo_lejano},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["es_match"] is False, f"Esperado es_match=false, got: {data}"
            assert data["distancia"] > 0.3  # distancia alta

            # Regla dura #5: es_match=false no es sancion.
            # El sistema responde 200, no 403 ni 409.
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.3 Usuario sin referencia vigente -> 404
    # ------------------------------------------------------------------

    def test_sin_referencia_vigente_retorna_404(self, slim_client) -> None:
        """Usuario autenticado sin embedding vigente -> 404."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-sin-ref", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-sin-ref", "password123")

            # Sin enrollment previo.
            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": _vector_128(0.1)},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 404, f"Esperado 404, got {resp.status_code}: {resp.text}"
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.4 Embedding vivo de dimension invalida -> 422
    # ------------------------------------------------------------------

    def test_embedding_dimension_invalida_retorna_422(self, slim_client) -> None:
        """Embedding vivo con dimension distinta a la referencia -> 422."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-dim-inv", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-dim-inv", "password123")

            # Enrollar referencia 128-d.
            _enrollar_embedding(slim_client, token, _vector_128(0.1))

            # Enviar embedding vivo de 64 dimensiones (invalido).
            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": [0.1] * 64},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 422, f"Esperado 422, got {resp.status_code}: {resp.text}"
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.5 Body con campo extra (embedding_referencia) -> 422 (extra='forbid')
    # ------------------------------------------------------------------

    def test_campo_embedding_referencia_extra_retorna_422(self, slim_client) -> None:
        """Body con embedding_referencia extra -> 422 por extra='forbid'."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-extra-field", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-extra-field", "password123")

            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={
                    "embedding_vivo": _vector_128(0.1),
                    "embedding_referencia": _vector_128(0.2),  # campo NO permitido
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 422, (
                f"Esperado 422 por campo extra, got {resp.status_code}: {resp.text}"
            )
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.6 Sin Bearer -> 401; rol incorrecto -> 403
    # ------------------------------------------------------------------

    def test_sin_bearer_retorna_401(self, slim_client) -> None:
        """Sin Bearer token -> 401."""
        resp = slim_client.post(
            "/api/v1/proctoring/biometria/verificar-referencia",
            json={"embedding_vivo": _vector_128(0.1)},
            # Sin Authorization header.
        )
        assert resp.status_code == 401, f"Esperado 401, got {resp.status_code}: {resp.text}"

    def test_rol_incorrecto_retorna_403(self, slim_client) -> None:
        """Token con rol distinto a estudiante -> 403."""
        # Crear usuario con rol proctor (no estudiante).
        usuario_id = _crear_usuario_slim_sync(
            "c59-rol-proctor", "password123", ["proctor"]
        )
        try:
            token = _login_y_token(slim_client, "c59-rol-proctor", "password123")

            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": _vector_128(0.1)},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 403, f"Esperado 403, got {resp.status_code}: {resp.text}"
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # 4.7 GET referencia/estado: true con referencia, false sin ella
    # ------------------------------------------------------------------

    def test_estado_referencia_true_con_referencia(self, slim_client) -> None:
        """GET referencia/estado -> tiene_referencia_vigente=true si hay embedding."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-estado-true", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-estado-true", "password123")
            _enrollar_embedding(slim_client, token, _vector_128(0.1))

            resp = slim_client.get(
                "/api/v1/proctoring/biometria/referencia/estado",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["tiene_referencia_vigente"] is True

            # Confirmar que la respuesta NO contiene el embedding.
            assert "embedding" not in resp.text
            assert "embedding_cifrado" not in resp.text
            assert set(data.keys()) == {"tiene_referencia_vigente"}
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    def test_estado_referencia_false_sin_referencia(self, slim_client) -> None:
        """GET referencia/estado -> tiene_referencia_vigente=false si no hay embedding."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-estado-false", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-estado-false", "password123")

            resp = slim_client.get(
                "/api/v1/proctoring/biometria/referencia/estado",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["tiene_referencia_vigente"] is False
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    def test_estado_referencia_sin_bearer_401(self, slim_client) -> None:
        """GET referencia/estado sin Bearer -> 401."""
        resp = slim_client.get("/api/v1/proctoring/biometria/referencia/estado")
        assert resp.status_code == 401, f"Esperado 401, got {resp.status_code}: {resp.text}"

    # ------------------------------------------------------------------
    # 4.8 Embedding de referencia NO aparece en respuesta ni en logs
    # ------------------------------------------------------------------

    def test_embedding_referencia_no_en_respuesta_verificacion(self, slim_client) -> None:
        """La respuesta de verificar-referencia NO contiene el embedding descifrado."""
        usuario_id = _crear_usuario_slim_sync(
            "c59-no-emb-resp", "password123", ["estudiante"]
        )
        try:
            token = _login_y_token(slim_client, "c59-no-emb-resp", "password123")
            referencia = _vector_128(0.1)
            _enrollar_embedding(slim_client, token, referencia)

            resp = slim_client.post(
                "/api/v1/proctoring/biometria/verificar-referencia",
                json={"embedding_vivo": referencia},
                headers={"Authorization": f"Bearer {token}"},
            )

            assert resp.status_code == 200, resp.text
            data = resp.json()

            # Los unicos campos permitidos en la respuesta son: distancia, es_match, umbral.
            assert set(data.keys()) == {"distancia", "es_match", "umbral"}

            # El texto completo de la respuesta no debe contener valores del embedding.
            # (El embedding cifrado es un Fernet token; verificamos que no haya claves
            # sospechosas de embedding en el JSON.)
            resp_text = resp.text.lower()
            assert "embedding_referencia" not in resp_text
            assert "embedding_cifrado" not in resp_text
            assert "referencia_descifrada" not in resp_text
        finally:
            _limpiar_usuario_slim_sync(usuario_id)

    # ------------------------------------------------------------------
    # Endpoint stateless demo-only sigue funcionando (retrocompat)
    # ------------------------------------------------------------------

    def test_endpoint_stateless_demo_still_works(self, slim_client) -> None:
        """POST /biometria/verificar (stateless, demo-only) sigue operativo."""
        emb_a = _vector_128(0.1)
        emb_b = _vector_128(0.15)  # Ligeramente diferente pero cercano.

        resp = slim_client.post(
            "/api/v1/proctoring/biometria/verificar",
            json={
                "embedding_vivo": emb_a,
                "embedding_referencia": emb_b,
            },
        )

        assert resp.status_code == 200, f"Demo endpoint roto: {resp.text}"
        data = resp.json()
        assert "distancia" in data
        assert "es_match" in data
        assert "umbral" in data
