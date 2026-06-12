"""Tests de integración del DSR contra slim DB real (c-17)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dsr.service import DsrService
from app.domain.dsr.report import DsrType
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.models.transactional import (
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.dsr import (
    SqlDsrAuditor,
    SqlUserDsrRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_slim_session_factory(create_slim_engine(url))


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _crear_user_con_biometria(
    factory: async_sessionmaker[AsyncSession],
) -> str:
    suf = _suf()
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"c17-{suf}",
            email=f"c17-{suf}@test.local",
            roles=["estudiante"],
            password_hash=None,
            auth_provider="local",
            nombre="Original",
            apellido="Test",
        )
        s.add(u)
        await s.flush()
        await s.execute(
            text(
                "INSERT INTO foto_referencia "
                "(usuario_id, foto_bytes, hash_sha256, vigente) "
                "VALUES (:uid, :bytes, :hash, true)"
            ),
            {"uid": u.id, "bytes": b"png-bytes", "hash": "b" * 64},
        )
        s.add(
            EmbeddingReferenciaModel(
                usuario_id=u.id,
                embedding_cifrado="gAAAAA-fernet-token",
                algoritmo="face-api-128d",
            )
        )
        await s.commit()
        return u.id


async def _cleanup(factory, usuario_id: str) -> None:
    async with factory() as s:
        await s.execute(
            delete(EmbeddingReferenciaModel).where(
                EmbeddingReferenciaModel.usuario_id == usuario_id
            )
        )
        await s.execute(
            delete(FotoReferenciaModel).where(
                FotoReferenciaModel.usuario_id == usuario_id
            )
        )
        await s.execute(
            delete(UsuarioModel).where(UsuarioModel.id == usuario_id)
        )
        await s.commit()


def _build_service(session: AsyncSession) -> DsrService:
    return DsrService(
        repo=SqlUserDsrRepository(session),
        hold_verifier=NullHoldVerifier(),
        auditor=SqlDsrAuditor(session),
    )


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_access_devuelve_usuario_real() -> None:
    factory = _factory()
    usuario_id = await _crear_user_con_biometria(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            r = await svc.access(usuario_id, actor="self")
            await s.commit()
        assert r.usuario_id == usuario_id
        assert r.nombre == "Original"
    finally:
        await _cleanup(factory, usuario_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_rectification_actualiza_email_real() -> None:
    factory = _factory()
    usuario_id = await _crear_user_con_biometria(factory)
    nuevo_email = f"nuevo-{_suf()}@test.local"
    try:
        async with factory() as s:
            svc = _build_service(s)
            r = await svc.rectification(
                usuario_id, actor="self", email=nuevo_email, nombre=None, apellido=None
            )
            await s.commit()
        assert r.email == nuevo_email
        # Confirmar en DB
        async with factory() as s:
            result = await s.execute(
                select(UsuarioModel.email).where(UsuarioModel.id == usuario_id)
            )
            assert result.scalar_one() == nuevo_email
    finally:
        await _cleanup(factory, usuario_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_erasure_borra_biometria_y_anonimiza_y_audita() -> None:
    factory = _factory()
    usuario_id = await _crear_user_con_biometria(factory)
    try:
        async with factory() as s:
            svc = _build_service(s)
            report = await svc.erasure(usuario_id, actor="self")
            await s.commit()
        assert report.embeddings_deleted == 1
        assert report.fotos_deleted == 1
        assert report.anonimizado is True
        # Verificar anonimizacion + biometria borrada
        async with factory() as s:
            usr = (
                await s.execute(
                    select(
                        UsuarioModel.email, UsuarioModel.nombre, UsuarioModel.eliminado_en
                    ).where(UsuarioModel.id == usuario_id)
                )
            ).first()
            assert usr is not None
            assert usr[0].startswith("anon-")
            assert usr[1] is None
            assert usr[2] is not None  # eliminado_en seteado

            emb = await s.execute(
                select(EmbeddingReferenciaModel.id).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
            assert emb.all() == []
            foto_count = await s.execute(
                text("SELECT count(*) FROM foto_referencia WHERE usuario_id = :uid"),
                {"uid": usuario_id},
            )
            assert foto_count.scalar() == 0

            audit = await s.execute(
                select(AuditLogModel.id).where(
                    AuditLogModel.accion == f"dsr.{DsrType.ERASURE.value}",
                    AuditLogModel.evidencia_id == usuario_id,
                )
            )
            assert len(audit.all()) == 1
    finally:
        await _cleanup(factory, usuario_id)
