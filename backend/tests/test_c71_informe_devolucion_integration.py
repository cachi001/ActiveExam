"""Informe de devolución al alumno (c-71 slice 2, D12) — HTTP contra DB real,
modelo de un solo paso.

Verifica (sin mocks de DB, regla #4):
- con `anulado`: el titular ve capturas (URL firmada 15 min) SOLO de la
  evidencia que el revisor eligió al decidir + análisis por señal + decisión
  + motivo de SU sesión;
- sesión ajena → 404 (sin revelar evidencia);
- `aprobado` / sin flag → 404 (minimización, Ley 25.326);
- cada acceso del titular queda auditado como derecho de acceso (RN-DSR-01).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.service import ReviewDecisionService
from app.domain.review.decision import DecisionSesion
from app.infrastructure.auth.verifiers import encode_hs256
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.infrastructure.persistence.session_slim import (
    create_slim_engine,
    create_slim_session_factory,
)
from app.infrastructure.storage.presign import StoragePresignService
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import (
    _TEST_JWT_AUDIENCE,
    _TEST_JWT_ISSUER,
    _TEST_JWT_SECRET,
    _build_test_jwt_validator,
)


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_slim_session_factory(create_slim_engine(url))


def _idn() -> str:
    return f"c71i-{uuid.uuid4().hex[:8]}"


def _token(idnumber: str) -> str:
    return encode_hs256(
        {
            "iss": _TEST_JWT_ISSUER,
            "aud": _TEST_JWT_AUDIENCE,
            "sub": f"sub-{idnumber}",
            "preferred_username": idnumber,
            "email": f"{idnumber}@u.edu",
            "exp": 9999999999,
            "amr": ["otp"],
            "realm_access": {"roles": ["estudiante"]},
        },
        _TEST_JWT_SECRET,
    )


@pytest_asyncio.fixture
def app(  # noqa: D401 - fixture
):
    factory = _factory()
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_taking_router(
            session_factory=factory,
            presign_service=StoragePresignService(
                endpoint="https://minio.test", bucket="evidence"
            ),
        ),
        prefix="/api/v1/exam-content",
    )
    return application, factory


def _client(app, idnumber: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(idnumber)}"},
    )


async def _sesion_con_dos_eventos(factory, idnumber: str) -> tuple[str, str, str]:
    """Sesion con DOS eventos con screenshot; devuelve (session_id, event_id_1, event_id_2)."""
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen", etiqueta=f"c71i-{_idn()}", alumno_idnumber=idnumber
        )
        sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        sid = sesion.id
        ev1 = ProctoringEventModel(
            session_id=sid,
            tipo="multiples_rostros",
            severidad="critico",
            ts_cliente=datetime.now(timezone.utc),
            face_count_servidor=2,
            veredicto_reinferencia="discrepancia",
            screenshot_sha256="a" * 64,
        )
        ev2 = ProctoringEventModel(
            session_id=sid,
            tipo="ausencia",
            severidad="media",
            ts_cliente=datetime.now(timezone.utc),
            face_count_servidor=0,
            veredicto_reinferencia="coincide",
            screenshot_sha256="b" * 64,
        )
        s.add_all([ev1, ev2])
        await s.commit()
        return sid, ev1.id, ev2.id


async def _decidir(factory, sid, decision, *, evidencia_ids=None) -> None:
    async with factory() as s:
        await ReviewDecisionService(
            repo=SqlSessionReviewRepository(s), auditor=SqlReviewAuditor(s)
        ).decide(
            sid,
            decision=decision,
            actor="autoridad",
            motivo="copia confirmada",
            evidencia_ids=evidencia_ids or [],
        )
        await s.commit()


async def _cleanup(factory, sid) -> None:
    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sid)
        )
        await s.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_titular_ve_informe_con_capturas_firmadas_y_senales(app) -> None:
    application, factory = app
    idn = _idn()
    sid, ev1, _ev2 = await _sesion_con_dos_eventos(factory, idn)
    try:
        await _decidir(factory, sid, DecisionSesion.ANULADO, evidencia_ids=[ev1])
        async with _client(application, idn) as c:
            resp = await c.get(f"/api/v1/exam-content/mis-notas/{sid}/informe")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] == "anulado"
        assert body["motivo"] == "copia confirmada"
        # Analisis por señal: ambos tipos de evento aparecen (contexto completo).
        assert len(body["senales"]) == 2
        # Pero las CAPTURAS se filtran a SOLO la evidencia elegida por el revisor.
        assert len(body["capturas"]) == 1
        assert body["capturas"][0]["tipo_evento"] == "multiples_rostros"
        # URL firmada que expira en 15 min (900 s).
        assert body["capturas"][0]["expires_in"] == 900
        # Cada acceso del titular queda auditado como derecho de acceso.
        async with factory() as s:
            acciones = {
                r[0]
                for r in (
                    await s.execute(
                        select(AuditLogModel.accion).where(
                            AuditLogModel.evidencia_id == sid
                        )
                    )
                ).all()
            }
            assert "derecho_acceso.informe_devolucion" in acciones
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_aprobado_no_expone_informe_minimizacion(app) -> None:
    application, factory = app
    idn = _idn()
    sid, _ev1, _ev2 = await _sesion_con_dos_eventos(factory, idn)
    try:
        await _decidir(factory, sid, DecisionSesion.APROBADO)
        async with _client(application, idn) as c:
            resp = await c.get(f"/api/v1/exam-content/mis-notas/{sid}/informe")
        assert resp.status_code == 404
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sesion_ajena_no_se_expone(app) -> None:
    application, factory = app
    dueno, intruso = _idn(), _idn()
    sid, ev1, _ev2 = await _sesion_con_dos_eventos(factory, dueno)
    try:
        await _decidir(factory, sid, DecisionSesion.ANULADO, evidencia_ids=[ev1])
        async with _client(application, intruso) as c:
            resp = await c.get(f"/api/v1/exam-content/mis-notas/{sid}/informe")
        assert resp.status_code == 404
    finally:
        await _cleanup(factory, sid)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sin_decision_no_expone_informe(app) -> None:
    application, factory = app
    idn = _idn()
    sid, _ev1, _ev2 = await _sesion_con_dos_eventos(factory, idn)
    try:
        async with _client(application, idn) as c:
            resp = await c.get(f"/api/v1/exam-content/mis-notas/{sid}/informe")
        assert resp.status_code == 404
    finally:
        await _cleanup(factory, sid)
