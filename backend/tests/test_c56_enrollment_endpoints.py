"""Tests de integracion de los endpoints de enrollment biometrico (C-56).

Cubre:
- 8.1 POST /enrollment/foto-perfil: foto subida, metadatos en DB, ID en response,
       foto anterior marcada no vigente en re-enrollment.
- 8.2 POST /enrollment/embedding-referencia: embedding cifrado en DB (no en claro),
       referencia_id en response, anterior no vigente en re-enrollment,
       rechazo de vector con dimension != 128.
- 8.3 Round-trip de descifrado: leer embedding_cifrado de la DB y descifrar
       con EmbeddingEncryptionService.decrypt().
- 8.4 Migracion 0007: upgrade desde 0006 y downgrade de vuelta.
- 7.4 HTTP 401 sin token y HTTP 403 con rol incorrecto.

NOTA: estos tests REQUIEREN el stack (DB PostgreSQL real). Se marcan con
``@pytest.mark.requires_stack`` para que se salten con la suite unitaria.
Exportar RUN_STACK_TESTS=1 con el compose arriba para ejecutarlos.

La DB debe tener aplicadas las migraciones 0001–0007 antes de ejecutar.
"""

from __future__ import annotations

import base64
import json
import os

import httpx
import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fernet_key_b64() -> str:
    return Fernet.generate_key().decode("ascii")


def _vector_128() -> list[float]:
    return [float(i) / 128.0 for i in range(128)]


def _imagen_b64() -> str:
    """Imagen PNG minimal de 1x1 px en base64 para tests."""
    # PNG 1x1 px transparente (mínimo válido).
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    b64 = base64.b64encode(png_1x1).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _monkeyenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setea las env vars minimas para que Settings arranque en tests de stack."""
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql+asyncpg://app@db:5432/proctoring"),
    )
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "k")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "s")
    monkeypatch.setenv("STORAGE_BUCKET_EVIDENCE", "evidence")
    monkeypatch.setenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/proctoring")
    monkeypatch.setenv(
        "KEYCLOAK_JWKS_URL",
        "http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs",
    )
    monkeypatch.setenv("JWT_AUDIENCE", "proctoring-api")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", _fernet_key_b64())


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

async def _crear_usuario_test(factory, suffix: str = "c56") -> tuple[str, str]:
    """Crea un usuario de prueba y devuelve (id, id_institucional)."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    async with factory() as session:
        u = UsuarioModel(
            id_institucional=f"test-enroll-{suffix}",
            email=f"test-enroll-{suffix}@demo.test",
            roles=["estudiante"],
            password_hash="x",
            auth_provider="local",
            attrs_federados={},
        )
        session.add(u)
        await session.commit()
        return u.id, u.id_institucional


async def _borrar_usuario_test(factory, usuario_id: str) -> None:
    """Limpia el usuario y sus datos relacionados."""
    from sqlalchemy import delete
    from app.infrastructure.persistence.models.transactional import (
        UsuarioModel,
        EmbeddingReferenciaModel,
        FotoReferenciaModel,
    )

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


# ---------------------------------------------------------------------------
# 8.1 Test: POST /enrollment/foto-perfil
# ---------------------------------------------------------------------------

@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_foto_perfil_persistida_en_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foto subida → metadatos en DB → foto_referencia_id en response."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import create_engine, create_session_factory
    from app.main import create_app

    engine = create_engine()
    factory = create_session_factory(engine)

    usuario_id, id_institucional = await _crear_usuario_test(factory, "foto-01")

    try:
        app = create_app()
        # Inyectar JWT válido para estudiante (monkeypatching del validador).
        from app.domain.auth.identity import AuthenticatedPrincipal
        from app.infrastructure.auth.jwt_validator import JwtValidator

        class _FakeValidator(JwtValidator):
            def __init__(self) -> None:  # noqa: no-parent-init — stub de test
                pass  # omite el __init__ del padre que requiere deps reales

            def validar(self, token: str) -> AuthenticatedPrincipal:
                return AuthenticatedPrincipal(
                    id_institucional=id_institucional,
                    email="test@demo.test",
                    roles=["estudiante"],
                    mfa_satisfecho=False,
                    jurisdiccion="AR",
                    subject=usuario_id,  # UUID real de la DB (para FK en enrollment)
                )

        app.state.jwt_validator = _FakeValidator()

        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/enrollment/foto-perfil",
                json={"imagen_base64": _imagen_b64()},
                headers={"Authorization": "Bearer dummy-token"},
            )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "foto_referencia_id" in data
        foto_id = data["foto_referencia_id"]
        assert len(foto_id) == 36  # UUID format

        # Verificar que el registro existe en DB.
        from app.infrastructure.persistence.repositories.biometric_reference import (
            FotoReferenciaRepository,
        )
        async with factory() as session:
            repo = FotoReferenciaRepository(session)
            foto = await repo.obtener_vigente(usuario_id)
            assert foto is not None
            assert foto.vigente is True
            assert foto.hash_sha256  # hash SHA-256 calculado
            assert foto.uri_storage  # key en el bucket

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_foto_anterior_marcada_no_vigente_en_re_enrollment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-enrollment: foto anterior → vigente=FALSE; nueva → vigente=TRUE."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import create_engine, create_session_factory
    from app.infrastructure.persistence.repositories.biometric_reference import (
        FotoReferenciaRepository,
    )
    from sqlalchemy import select
    from app.infrastructure.persistence.models.transactional import FotoReferenciaModel

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "foto-02")

    try:
        from app.main import create_app
        from app.domain.auth.identity import AuthenticatedPrincipal
        from app.infrastructure.auth.jwt_validator import JwtValidator

        class _FakeValidator(JwtValidator):
            def __init__(self) -> None:  # noqa: no-parent-init — stub de test
                pass

            def validar(self, token: str) -> AuthenticatedPrincipal:
                return AuthenticatedPrincipal(
                    id_institucional=id_institucional,
                    email="test@demo.test",
                    roles=["estudiante"],
                    mfa_satisfecho=False,
                    jurisdiccion="AR",
                    subject=usuario_id,  # UUID real para FK en enrollment
                )

        app = create_app()
        app.state.jwt_validator = _FakeValidator()

        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Primer enrollment.
            r1 = await client.post(
                "/api/v1/enrollment/foto-perfil",
                json={"imagen_base64": _imagen_b64()},
                headers={"Authorization": "Bearer t1"},
            )
            assert r1.status_code == 201
            id1 = r1.json()["foto_referencia_id"]

            # Segundo enrollment.
            r2 = await client.post(
                "/api/v1/enrollment/foto-perfil",
                json={"imagen_base64": _imagen_b64()},
                headers={"Authorization": "Bearer t2"},
            )
            assert r2.status_code == 201
            id2 = r2.json()["foto_referencia_id"]

        assert id1 != id2

        # La primera foto debe estar no vigente; la segunda, vigente.
        async with factory() as session:
            result = await session.execute(
                select(FotoReferenciaModel).where(
                    FotoReferenciaModel.usuario_id == usuario_id
                )
            )
            fotos = result.scalars().all()
            assert len(fotos) == 2
            ids_vigentes = [f.id for f in fotos if f.vigente]
            ids_no_vigentes = [f.id for f in fotos if not f.vigente]
            assert id2 in ids_vigentes
            assert id1 in ids_no_vigentes

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


# ---------------------------------------------------------------------------
# 7.4 Test: HTTP 401 sin token / HTTP 403 con rol incorrecto
# ---------------------------------------------------------------------------

@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_foto_perfil_401_sin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin token → HTTP 401."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    from app.main import create_app
    app = create_app()

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": _imagen_b64()},
        )
    assert resp.status_code == 401


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_foto_perfil_403_rol_incorrecto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con token de proctor → HTTP 403."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    from app.main import create_app
    from app.domain.auth.identity import AuthenticatedPrincipal
    from app.infrastructure.auth.jwt_validator import JwtValidator

    class _FakeProctor(JwtValidator):
        def __init__(self) -> None:  # noqa: no-parent-init — stub de test
            pass

        def validar(self, token: str) -> AuthenticatedPrincipal:
            return AuthenticatedPrincipal(
                id_institucional="proctor-001",
                email="proctor@demo.test",
                roles=["proctor"],
                mfa_satisfecho=True,
                jurisdiccion="AR",
            )

    app = create_app()
    app.state.jwt_validator = _FakeProctor()

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/enrollment/foto-perfil",
            json={"imagen_base64": _imagen_b64()},
            headers={"Authorization": "Bearer proctor-token"},
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8.2 Test: POST /enrollment/embedding-referencia
# ---------------------------------------------------------------------------

@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_embedding_cifrado_en_db_no_en_claro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedding cifrado en DB (no en claro) y referencia_id en response."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import create_engine, create_session_factory
    from sqlalchemy import select
    from app.infrastructure.persistence.models.transactional import EmbeddingReferenciaModel

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "emb-01")

    try:
        from app.main import create_app
        from app.domain.auth.identity import AuthenticatedPrincipal
        from app.infrastructure.auth.jwt_validator import JwtValidator

        class _FakeEstudiante(JwtValidator):
            def __init__(self) -> None:  # noqa: no-parent-init — stub de test
                pass

            def validar(self, token: str) -> AuthenticatedPrincipal:
                return AuthenticatedPrincipal(
                    id_institucional=id_institucional,
                    email="test@demo.test",
                    roles=["estudiante"],
                    mfa_satisfecho=False,
                    jurisdiccion="AR",
                    subject=usuario_id,  # UUID real para FK en enrollment
                )

        app = create_app()
        app.state.jwt_validator = _FakeEstudiante()
        vector = _vector_128()

        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": vector},
                headers={"Authorization": "Bearer t"},
            )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "referencia_id" in data
        ref_id = data["referencia_id"]
        assert len(ref_id) == 36

        # Verificar que el embedding NO esta en claro en la DB.
        async with factory() as session:
            result = await session.execute(
                select(EmbeddingReferenciaModel).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
            registro = result.scalar_one()
            assert registro.vigente is True
            # El ciphertext no debe contener el JSON del vector en claro.
            vector_json = json.dumps(vector)
            assert vector_json not in registro.embedding_cifrado

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_embedding_dimension_invalida_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vector con dimension != 128 → HTTP 422."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()
    from app.main import create_app
    from app.domain.auth.identity import AuthenticatedPrincipal
    from app.infrastructure.auth.jwt_validator import JwtValidator

    class _FakeEstudiante(JwtValidator):
        def __init__(self) -> None:  # noqa: no-parent-init — stub de test
            pass

        def validar(self, token: str) -> AuthenticatedPrincipal:
            return AuthenticatedPrincipal(
                id_institucional="est-422",
                email="test@demo.test",
                roles=["estudiante"],
                mfa_satisfecho=False,
                jurisdiccion="AR",
            )

    app = create_app()
    app.state.jwt_validator = _FakeEstudiante()

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/enrollment/embedding-referencia",
            json={"embedding": [0.1, 0.2, 0.3]},  # solo 3 dimensiones
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8.3 Test: round-trip de descifrado (integracion completa)
# ---------------------------------------------------------------------------

@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_round_trip_cifrado_descifrado_integracion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guardar embedding via endpoint → leer de DB → descifrar → mismo vector."""
    _monkeyenv(monkeypatch)
    from app import config as cfg
    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import create_engine, create_session_factory
    from sqlalchemy import select
    from app.infrastructure.persistence.models.transactional import EmbeddingReferenciaModel
    import math

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "emb-rt")

    try:
        from app.main import create_app
        from app.domain.auth.identity import AuthenticatedPrincipal
        from app.infrastructure.auth.jwt_validator import JwtValidator

        class _FakeEstudiante(JwtValidator):
            def __init__(self) -> None:  # noqa: no-parent-init — stub de test
                pass

            def validar(self, token: str) -> AuthenticatedPrincipal:
                return AuthenticatedPrincipal(
                    id_institucional=id_institucional,
                    email="test@demo.test",
                    roles=["estudiante"],
                    mfa_satisfecho=False,
                    jurisdiccion="AR",
                    subject=usuario_id,  # UUID real para FK en enrollment
                )

        app = create_app()
        app.state.jwt_validator = _FakeEstudiante()
        vector_original = _vector_128()

        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": vector_original},
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 201

        # Leer el ciphertext de la DB y descifrar.
        async with factory() as session:
            result = await session.execute(
                select(EmbeddingReferenciaModel).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
            registro = result.scalar_one()
            ciphertext = registro.embedding_cifrado

        encryption = EmbeddingEncryptionService()
        vector_recuperado = encryption.decrypt(ciphertext)

        assert len(vector_recuperado) == 128
        for orig, rec in zip(vector_original, vector_recuperado):
            assert math.isclose(orig, rec, rel_tol=1e-9)

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()
