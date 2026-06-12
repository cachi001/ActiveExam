"""Tests de integracion del motor de retencion contra slim DB real (c-19).

Requiere stack levantado con RUN_STACK_TESTS=1. Cubre:
  - SqlSessionAgingRepository encuentra sesiones por edad
  - SqlSessionDeleter borra sesion + cascade a eventos
  - SqlUserEgressRepository encuentra usuarios egresados con biometria
  - SqlEmbedding/FotoDeleter borran filas por usuario_id
  - SqlRetentionAuditor escribe al audit_log con triggers (cadena hash)
  - RetentionEngine.apply_session_retention orquesta todo
  - RetentionEngine.apply_embedding_egress orquesta egreso

Estos tests son aditivos: crean filas con id_institucional unicos y las
limpian al final. No tocan los usuarios seed (ADMIN-001/EST-001/PROC-001).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.retention.engine import RetentionEngine
from app.domain.retention.policy import RetentionPolicy
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.repositories.retention import (
    SqlEmbeddingDeleter,
    SqlFotoDeleter,
    SqlRetentionAuditor,
    SqlSessionAgingRepository,
    SqlSessionDeleter,
    SqlUserEgressRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _slim_factory() -> async_sessionmaker[AsyncSession]:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    engine = create_slim_engine(db_url)
    return create_slim_session_factory(engine)


def _suffix() -> str:
    """Suffix unico para evitar colisiones con seed/otros tests."""
    return uuid.uuid4().hex[:8]


async def _crear_sesion_aged(
    factory: async_sessionmaker[AsyncSession], creada_hace_dias: int
) -> tuple[str, int]:
    """Crea una sesion + 2 eventos con creada_en hacia atras. Devuelve (id, count_eventos)."""
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen",
            etiqueta=f"c19-test-{_suffix()}",
        )
        s.add(sesion)
        await s.flush()
        # Pisar creada_en hacia atras (no se puede setear en el constructor server_default).
        sesion.creada_en = datetime.now(timezone.utc) - timedelta(days=creada_hace_dias)
        s.add(
            ProctoringEventModel(
                session_id=sesion.id,
                tipo="FACE_ABSENT",
                severidad="medio",
                ts_cliente=datetime.now(timezone.utc),
                ts_backend=datetime.now(timezone.utc),
                payload={},
            )
        )
        s.add(
            ProctoringEventModel(
                session_id=sesion.id,
                tipo="GAZE_DEVIATION",
                severidad="bajo",
                ts_cliente=datetime.now(timezone.utc),
                ts_backend=datetime.now(timezone.utc),
                payload={},
            )
        )
        await s.commit()
        return sesion.id, 2


async def _crear_usuario_egresado_con_biometria(
    factory: async_sessionmaker[AsyncSession],
) -> str:
    """Crea un usuario con eliminado_en NOT NULL + 1 embedding + 1 foto."""
    suf = _suffix()
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"c19-egress-{suf}",
            email=f"c19-egress-{suf}@test.local",
            roles=["estudiante"],
            password_hash=None,
            auth_provider="local",
            eliminado_en=datetime.now(timezone.utc) - timedelta(days=10),
        )
        s.add(u)
        await s.flush()
        # foto_referencia: usar SQL raw porque el ORM model es para FULL
        # (con uri_storage/bucket) pero slim usa foto_bytes (BYTEA).
        # Misma estrategia que DbPhotoStorageService.
        await s.execute(
            text(
                "INSERT INTO foto_referencia "
                "(usuario_id, foto_bytes, hash_sha256, vigente) "
                "VALUES (:uid, :bytes, :hash, true)"
            ),
            {"uid": u.id, "bytes": b"fake-png-bytes", "hash": "a" * 64},
        )
        s.add(
            EmbeddingReferenciaModel(
                usuario_id=u.id,
                embedding_cifrado="gAAAAA-fernet-fake-token-c19-test",
                algoritmo="face-api-128d",
            )
        )
        await s.commit()
        return u.id


async def _contar_audit(
    factory: async_sessionmaker[AsyncSession], accion: str
) -> int:
    async with factory() as s:
        result = await s.execute(
            select(AuditLogModel.id).where(AuditLogModel.accion == accion)
        )
        return len(result.all())


async def _cleanup_sesion(
    factory: async_sessionmaker[AsyncSession], sesion_id: str
) -> None:
    """Borra una sesion si todavia existe (test puede fallar antes de borrarla)."""
    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.id == sesion_id
            )
        )
        await s.commit()


async def _cleanup_usuario(
    factory: async_sessionmaker[AsyncSession], usuario_id: str
) -> None:
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


def _build_engine(session: AsyncSession) -> RetentionEngine:
    return RetentionEngine(
        aging_repo=SqlSessionAgingRepository(session),
        egress_repo=SqlUserEgressRepository(session),
        hold_verifier=NullHoldVerifier(),
        session_deleter=SqlSessionDeleter(session),
        embedding_deleter=SqlEmbeddingDeleter(session),
        foto_deleter=SqlFotoDeleter(session),
        auditor=SqlRetentionAuditor(session),
    )


# ---------------------------------------------------------------------------
# Tests de integracion
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_aging_repo_encuentra_sesion_vieja() -> None:
    """La sesion creada hace 200 dias debe aparecer con cutoff a 180."""
    factory = _slim_factory()
    sesion_id, _ = await _crear_sesion_aged(factory, creada_hace_dias=200)
    try:
        async with factory() as s:
            repo = SqlSessionAgingRepository(s)
            cutoff = datetime.now(timezone.utc) - timedelta(days=180)
            ids = await repo.find_older_than(cutoff)
        assert sesion_id in ids
    finally:
        await _cleanup_sesion(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_session_deleter_cascade_a_eventos() -> None:
    """Borrar la sesion borra los 2 eventos hijos (FK CASCADE)."""
    factory = _slim_factory()
    sesion_id, count = await _crear_sesion_aged(factory, creada_hace_dias=5)
    try:
        async with factory() as s:
            # Precondicion: 2 eventos en la sesion
            evts = await s.execute(
                select(ProctoringEventModel.id).where(
                    ProctoringEventModel.session_id == sesion_id
                )
            )
            assert len(evts.all()) == count

            await SqlSessionDeleter(s).delete(sesion_id)
            await s.commit()

        async with factory() as s:
            # Postcondicion: sesion ni eventos existen
            ses = await s.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.id == sesion_id
                )
            )
            assert ses.all() == []
            evts = await s.execute(
                select(ProctoringEventModel.id).where(
                    ProctoringEventModel.session_id == sesion_id
                )
            )
            assert evts.all() == []
    finally:
        await _cleanup_sesion(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_engine_session_retention_borra_aged_y_audita() -> None:
    """Sesion vieja + null verifier -> se borra. Audit log tiene la entrada."""
    factory = _slim_factory()
    sesion_id, _ = await _crear_sesion_aged(factory, creada_hace_dias=200)
    audit_before = await _contar_audit(factory, "retention.session.deleted")
    try:
        async with factory() as s:
            engine = _build_engine(s)
            report = await engine.apply_session_retention(
                RetentionPolicy.default(), actor="test-actor"
            )
            await s.commit()

        # Reporte incluye el borrado
        deletion_ids = [d.target_id for d in report.deletions]
        assert sesion_id in deletion_ids
        assert sesion_id not in report.holds_deferred

        # DB no tiene la sesion
        async with factory() as s:
            result = await s.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.id == sesion_id
                )
            )
            assert result.all() == []

        # Audit log tiene 1 entrada mas
        audit_after = await _contar_audit(factory, "retention.session.deleted")
        assert audit_after == audit_before + len(deletion_ids)
    finally:
        await _cleanup_sesion(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_engine_no_borra_sesion_reciente() -> None:
    """Sesion de hace 5 dias NO se borra con politica 180d."""
    factory = _slim_factory()
    sesion_id, _ = await _crear_sesion_aged(factory, creada_hace_dias=5)
    try:
        async with factory() as s:
            engine = _build_engine(s)
            report = await engine.apply_session_retention(
                RetentionPolicy.default(), actor="test-actor"
            )
            await s.commit()
        deletion_ids = [d.target_id for d in report.deletions]
        assert sesion_id not in deletion_ids
        async with factory() as s:
            result = await s.execute(
                select(ProctoringSessionModel.id).where(
                    ProctoringSessionModel.id == sesion_id
                )
            )
            assert result.all() != []
    finally:
        await _cleanup_sesion(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_egress_repo_encuentra_usuario_egresado_con_biometria() -> None:
    factory = _slim_factory()
    usuario_id = await _crear_usuario_egresado_con_biometria(factory)
    try:
        async with factory() as s:
            ids = await SqlUserEgressRepository(s).find_egressed_with_biometry()
        assert usuario_id in ids
    finally:
        await _cleanup_usuario(factory, usuario_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_engine_biometric_egress_borra_embedding_y_foto() -> None:
    factory = _slim_factory()
    usuario_id = await _crear_usuario_egresado_con_biometria(factory)
    audit_before = await _contar_audit(factory, "retention.biometric.egress")
    try:
        async with factory() as s:
            engine = _build_engine(s)
            report = await engine.apply_embedding_egress(actor="test-actor")
            await s.commit()

        # El usuario aparece en el reporte 2 veces: foto + embedding
        ids_kinds = sorted(
            (d.target_id, d.target_kind) for d in report.deletions
            if d.target_id == usuario_id
        )
        assert (usuario_id, "embedding_referencia") in ids_kinds
        assert (usuario_id, "foto_referencia") in ids_kinds

        # DB no tiene mas su embedding ni foto
        async with factory() as s:
            emb = await s.execute(
                select(EmbeddingReferenciaModel.id).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
            assert emb.all() == []
            foto = await s.execute(
                select(FotoReferenciaModel.id).where(
                    FotoReferenciaModel.usuario_id == usuario_id
                )
            )
            assert foto.all() == []

        audit_after = await _contar_audit(factory, "retention.biometric.egress")
        assert audit_after > audit_before
    finally:
        await _cleanup_usuario(factory, usuario_id)
