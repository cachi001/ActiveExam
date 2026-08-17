"""Test de eliminacion al egreso del consentimiento de perfil via DSR (task 3.8).

El erasure DSR (derecho al olvido) DEBE purgar el consentimiento de perfil del
usuario cuando no hay holds que difieran (Ley 25.326, RN-BIO-08/RN-DSR-03).

DB real activeexam. Reusa el patron del test de integracion DSR (c-17).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dsr.service import DsrService
from app.infrastructure.persistence.models.transactional import (
    ConsentimientoPerfilModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.consent_perfil import (
    ConsentimientoPerfilSqlRepository,
)
from app.infrastructure.persistence.repositories.dsr import (
    SqlDsrAuditor,
    SqlUserDsrRepository,
)
from app.infrastructure.persistence.session_activeexam import (
    create_activeexam_engine,
    create_activeexam_session_factory,
)
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier

pytestmark = pytest.mark.asyncio


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_activeexam_session_factory(create_activeexam_engine(url))


async def _crear_user_con_consentimiento(factory) -> str:
    suf = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"cegr-{suf}",
            email=f"cegr-{suf}@test.local",
            roles=["estudiante"],
            auth_provider="local",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        repo = ConsentimientoPerfilSqlRepository(s)
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="otorgado")
        await s.commit()
    return uid


async def _cleanup(factory, uid: str) -> None:
    async with factory() as s:
        await s.execute(
            delete(ConsentimientoPerfilModel).where(
                ConsentimientoPerfilModel.usuario_id == uid
            )
        )
        await s.execute(delete(UsuarioModel).where(UsuarioModel.id == uid))
        await s.commit()


async def test_erasure_purga_consentimiento_perfil_sin_hold() -> None:
    factory = _factory()
    # Asegurar que la tabla existe.
    async with factory() as s:
        await s.execute(
            text(
                "CREATE TABLE IF NOT EXISTS consentimiento_perfil ("
                "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "usuario_id uuid NOT NULL REFERENCES usuario(id) ON DELETE CASCADE, "
                "version_texto varchar(64) NOT NULL, hash_texto varchar(64) NOT NULL, "
                "timestamp timestamptz NOT NULL DEFAULT now(), estado varchar(32) NOT NULL, "
                "hash_registro varchar(64) NOT NULL)"
            )
        )
        await s.commit()

    uid = await _crear_user_con_consentimiento(factory)
    try:
        async with factory() as s:
            svc = DsrService(
                repo=SqlUserDsrRepository(s),
                hold_verifier=NullHoldVerifier(),
                auditor=SqlDsrAuditor(s),
            )
            reporte = await svc.erasure(uid, actor="admin1")
            await s.commit()
        # Sin holds -> el consentimiento de perfil se purga.
        assert reporte.consent_perfil_deleted >= 1
        async with factory() as s2:
            vigente = await ConsentimientoPerfilSqlRepository(s2).vigente(uid)
        assert vigente is None
    finally:
        await _cleanup(factory, uid)
