"""Test de cascade delete sobre foto_referencia y embedding_referencia (C-56 task 1.4).

Verifica el comportamiento de la FK con ondelete=CASCADE definida en la
migracion 0007:

    sa.ForeignKey("usuario.id", ondelete="CASCADE")

Al eliminar un usuario, Postgres debe eliminar automaticamente todas las filas
de foto_referencia y embedding_referencia asociadas, sin necesidad de logica
de aplicacion.

Requiere stack levantado (RUN_STACK_TESTS=1) con migraciones 0001-0007
aplicadas sobre la rama principal (full, con TimescaleDB).
"""

from __future__ import annotations

import base64
import os

import pytest
from cryptography.fernet import Fernet


def _monkeyenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vars minimas para que Settings arranque."""
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
    monkeypatch.setenv("EMBEDDING_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_cascade_delete_usuario_elimina_foto_y_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borrar usuario -> foto_referencia y embedding_referencia se eliminan en cascada."""
    _monkeyenv(monkeypatch)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from sqlalchemy import select

    from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService
    from app.infrastructure.persistence.models.transactional import (
        EmbeddingReferenciaModel,
        FotoReferenciaModel,
        UsuarioModel,
    )
    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )

    engine = create_engine()
    factory = create_session_factory(engine)

    # --- Setup: crear usuario + foto + embedding cifrado --------------------
    async with factory() as session:
        usuario = UsuarioModel(
            id_institucional="cascade-test-01",
            email="cascade-test-01@demo.test",
            roles=["estudiante"],
            password_hash="x",
            auth_provider="local",
            attrs_federados={},
        )
        session.add(usuario)
        await session.flush()

        foto = FotoReferenciaModel(
            usuario_id=usuario.id,
            bucket="activeexam-perfil",
            object_key=f"perfil/{usuario.id}/foto.png",
            content_type="image/png",
            tamano_bytes=64,
            hash_sha256="a" * 64,
            vigente=True,
        )
        session.add(foto)

        enc = EmbeddingEncryptionService()
        cifrado_b64 = enc.encrypt([0.1] * 128)
        embedding = EmbeddingReferenciaModel(
            usuario_id=usuario.id,
            embedding_cifrado=base64.b64decode(cifrado_b64),
            dimension=128,
            algoritmo="fernet-aes128-cbc-hmac-sha256",
            vigente=True,
        )
        session.add(embedding)
        await session.commit()
        usuario_id = usuario.id

    # --- Precondicion: las filas hijas existen ------------------------------
    async with factory() as session:
        fotos_pre = (
            await session.execute(
                select(FotoReferenciaModel).where(
                    FotoReferenciaModel.usuario_id == usuario_id
                )
            )
        ).scalars().all()
        embeds_pre = (
            await session.execute(
                select(EmbeddingReferenciaModel).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
        ).scalars().all()
        assert len(fotos_pre) == 1, "Setup fallo: no se creo foto_referencia"
        assert len(embeds_pre) == 1, "Setup fallo: no se creo embedding_referencia"

    # --- Act: borrar el usuario (sin tocar las hijas manualmente) -----------
    async with factory() as session:
        usuario_db = await session.get(UsuarioModel, usuario_id)
        assert usuario_db is not None, "Usuario no se encuentra antes de borrar"
        await session.delete(usuario_db)
        await session.commit()

    # --- Assert: las filas hijas se eliminaron por CASCADE de PG ------------
    async with factory() as session:
        fotos_post = (
            await session.execute(
                select(FotoReferenciaModel).where(
                    FotoReferenciaModel.usuario_id == usuario_id
                )
            )
        ).scalars().all()
        embeds_post = (
            await session.execute(
                select(EmbeddingReferenciaModel).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
        ).scalars().all()
        assert fotos_post == [], (
            "CASCADE fallo: foto_referencia sigue existiendo tras borrar usuario"
        )
        assert embeds_post == [], (
            "CASCADE fallo: embedding_referencia sigue existiendo tras borrar usuario"
        )
