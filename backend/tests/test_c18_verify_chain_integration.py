"""Tests de integración del verify-chain contra slim DB real (c-18).

Cubre:
  - SqlEventMaterialRepository lee proctoring_event.screenshot_b64 + sha256
  - SqlChainVerificationAuditor escribe al audit_log con triggers
  - VerifyChainService end-to-end:
      * cadena integra (hash coincide)
      * cadena rota (hash modificado)
      * material missing (screenshot null)
      * evento no encontrado (404 path en HTTP)
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.verify_chain.service import VerifyChainService
from app.domain.verify_chain.certificate import ChainVerificationStatus
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.verify_chain import (
    SqlChainVerificationAuditor,
    SqlEventMaterialRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_slim_session_factory(create_slim_engine(url))


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _crear_sesion_con_evento(
    factory: async_sessionmaker[AsyncSession],
    *,
    screenshot: str | None,
    sha256_registrado: str | None,
) -> tuple[str, str]:
    """Devuelve (session_id, event_id)."""
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", etiqueta=f"c18-{_suf()}")
        s.add(sesion)
        await s.flush()
        ev = ProctoringEventModel(
            session_id=sesion.id,
            tipo="GAZE_DEVIATION",
            severidad="medio",
            ts_cliente=datetime.now(timezone.utc),
            ts_backend=datetime.now(timezone.utc),
            payload={},
            screenshot_b64=screenshot,
            screenshot_sha256=sha256_registrado,
        )
        s.add(ev)
        await s.commit()
        return sesion.id, ev.id


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], sesion_id: str
) -> None:
    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.id == sesion_id
            )
        )
        await s.commit()


async def _contar_audit(factory, accion: str) -> int:
    async with factory() as s:
        result = await s.execute(
            select(AuditLogModel.id).where(AuditLogModel.accion == accion)
        )
        return len(result.all())


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_material_repo_lee_screenshot_y_hash() -> None:
    factory = _factory()
    content = "screenshot-original-test-c18"
    sha = _sha256_str(content)
    sesion_id, ev_id = await _crear_sesion_con_evento(
        factory, screenshot=content, sha256_registrado=sha
    )
    try:
        async with factory() as s:
            material = await SqlEventMaterialRepository(s).get_event_material(
                ev_id
            )
        assert material is not None
        assert material[0] == content
        assert material[1] == sha
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_material_repo_devuelve_none_si_evento_no_existe() -> None:
    factory = _factory()
    async with factory() as s:
        material = await SqlEventMaterialRepository(s).get_event_material(
            "00000000-0000-0000-0000-000000000000"
        )
    assert material is None


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_verify_cadena_integra_e2e() -> None:
    factory = _factory()
    content = "evidencia-integra"
    sha = _sha256_str(content)
    sesion_id, ev_id = await _crear_sesion_con_evento(
        factory, screenshot=content, sha256_registrado=sha
    )
    before = await _contar_audit(factory, "verify_chain.intact")
    try:
        async with factory() as s:
            service = VerifyChainService(
                event_repo=SqlEventMaterialRepository(s),
                auditor=SqlChainVerificationAuditor(s),
            )
            cert = await service.verify(ev_id, actor="test-revisor")
            await s.commit()
        assert cert.status == ChainVerificationStatus.INTACT
        assert cert.stages[0].match is True
        after = await _contar_audit(factory, "verify_chain.intact")
        assert after == before + 1
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_verify_cadena_rota_e2e() -> None:
    """Cuando el sha256 registrado no coincide con el recomputado → BROKEN + audit."""
    factory = _factory()
    sesion_id, ev_id = await _crear_sesion_con_evento(
        factory, screenshot="contenido-real", sha256_registrado="0" * 64
    )
    before = await _contar_audit(factory, "verify_chain.broken")
    try:
        async with factory() as s:
            service = VerifyChainService(
                event_repo=SqlEventMaterialRepository(s),
                auditor=SqlChainVerificationAuditor(s),
            )
            cert = await service.verify(ev_id, actor="test-revisor")
            await s.commit()
        assert cert.status == ChainVerificationStatus.BROKEN
        assert cert.stages[0].match is False
        after = await _contar_audit(factory, "verify_chain.broken")
        assert after == before + 1
    finally:
        await _cleanup(factory, sesion_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_verify_material_missing_si_screenshot_null() -> None:
    factory = _factory()
    sesion_id, ev_id = await _crear_sesion_con_evento(
        factory, screenshot=None, sha256_registrado=None
    )
    before = await _contar_audit(factory, "verify_chain.material_missing")
    try:
        async with factory() as s:
            service = VerifyChainService(
                event_repo=SqlEventMaterialRepository(s),
                auditor=SqlChainVerificationAuditor(s),
            )
            cert = await service.verify(ev_id, actor="test-revisor")
            await s.commit()
        assert cert.status == ChainVerificationStatus.MATERIAL_MISSING
        after = await _contar_audit(factory, "verify_chain.material_missing")
        assert after == before + 1
    finally:
        await _cleanup(factory, sesion_id)
