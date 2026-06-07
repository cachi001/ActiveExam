"""Tests de DbRefreshTokenStore (C-55, D4).

Verifica: issue → is_valid → rotate → reuso detectado (RefreshTokenError).
Confirma que el token rotado queda con rotado_en != NULL.

Requiere el stack de DB (RUN_STACK_TESTS=1).
"""

from __future__ import annotations

import pytest

from app.infrastructure.auth.db_refresh_store import DbRefreshTokenStore
from app.infrastructure.auth.refresh_store import RefreshTokenError


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_issue_is_valid_rotate_reuso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flujo completo: issue → valid → rotate → viejo invalido → reuso rechazado."""
    import os  # noqa: PLC0415
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+asyncpg://app@db:5432/proctoring"))
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "k")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "s")
    monkeypatch.setenv("STORAGE_BUCKET_EVIDENCE", "evidence")
    monkeypatch.setenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/proctoring")
    monkeypatch.setenv("KEYCLOAK_JWKS_URL", "http://keycloak:8080/realms/proctoring/protocol/openid-connect/certs")
    monkeypatch.setenv("JWT_AUDIENCE", "proctoring-api")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")

    from app.infrastructure.persistence.session import create_engine, create_session_factory  # noqa: PLC0415
    from app.infrastructure.persistence.models.transactional import UsuarioModel, RefreshTokenModel  # noqa: PLC0415
    from sqlalchemy import select, delete  # noqa: PLC0415

    engine = create_engine()
    factory = create_session_factory(engine)

    # Crear un usuario de prueba para FK.
    async with factory() as session:
        usuario = UsuarioModel(
            id_institucional="test-refresh-store-user",
            email="test-refresh-store@demo.test",
            roles=["estudiante"],
            password_hash="x",
            auth_provider="local",
            attrs_federados={},
        )
        session.add(usuario)
        await session.commit()
        usuario_id = usuario.id

    try:
        # Issue.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            jti = await store.issue_para_usuario(usuario_id)
            await session.commit()

        # is_valid → True.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            assert await store.is_valid_async(jti) is True

        # Rotate.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            nuevo_jti = await store.rotate_async(jti, usuario_id)
            await session.commit()

        assert nuevo_jti != jti

        # Token viejo → inválido.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            assert await store.is_valid_async(jti) is False

        # Nuevo → válido.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            assert await store.is_valid_async(nuevo_jti) is True

        # Reuso del viejo → RefreshTokenError.
        async with factory() as session:
            store = DbRefreshTokenStore(session, ttl_seconds=3600)
            with pytest.raises(RefreshTokenError):
                await store.rotate_async(jti, usuario_id)

        # Confirmar que rotado_en != NULL para el token viejo.
        async with factory() as session:
            result = await session.execute(
                select(RefreshTokenModel).where(RefreshTokenModel.jti == jti)
            )
            registro = result.scalar_one_or_none()
            assert registro is not None
            assert registro.rotado_en is not None

    finally:
        # Cleanup.
        async with factory() as session:
            await session.execute(delete(RefreshTokenModel).where(RefreshTokenModel.usuario_id == usuario_id))
            await session.execute(delete(UsuarioModel).where(UsuarioModel.id == usuario_id))
            await session.commit()

        await engine.dispose()
