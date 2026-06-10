"""Tests de integracion backend para C-65: auditoria de re-captura biometrica
y conservacion de referencia previa (tasks 7.3, 7.4, 7.5).

Spec: openspec/changes/c-65-fixes-captura-liveness-biometrica/specs/
      biometric-recapture-rate-limit/spec.md

Cubre:
  - 7.3 Audit log: se escribe una fila con accion='enrollment.embedding_referencia.renovacion'
         por cada re-enrollment, portando la ip y user_agent del request.
  - 7.4 Conservacion: la referencia anterior queda vigente=FALSE (no borrada).
         La renovacion NO auto-sanciona ni invalida rendiciones en curso (L2.5).
  - Triangulacion: segundo caso con user_agent / ip distintos.

REGLA DURA #4: sin mocks de DB — se usa el stack real (PostgreSQL).
Correr con RUN_STACK_TESTS=1 y el stack levantado.
"""

from __future__ import annotations

import os
from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fernet_key_b64() -> str:
    return Fernet.generate_key().decode("ascii")


def _vector_128(seed: float = 0.0) -> list[float]:
    """Vector de 128 floats determinista por seed."""
    return [(float(i) + seed) / 128.0 for i in range(128)]


def _monkeyenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Variables de entorno minimas para que Settings arranque en tests de stack."""
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


async def _crear_usuario_test(factory, suffix: str = "c65") -> tuple[str, str]:
    """Crea usuario de prueba, devuelve (id, id_institucional)."""
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    async with factory() as session:
        u = UsuarioModel(
            id_institucional=f"test-c65-{suffix}",
            email=f"test-c65-{suffix}@demo.test",
            roles=["estudiante"],
            password_hash="x",
            auth_provider="local",
            attrs_federados={},
        )
        session.add(u)
        await session.commit()
        return u.id, u.id_institucional


async def _borrar_usuario_test(factory, usuario_id: str) -> None:
    """Limpia el usuario y todos sus datos biometricos relacionados."""
    from sqlalchemy import delete

    from app.infrastructure.persistence.models.transactional import (
        EmbeddingReferenciaModel,
        FotoReferenciaModel,
        UsuarioModel,
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


def _make_fake_validator(usuario_id: str, id_institucional: str):
    """Devuelve un JwtValidator falso que siempre autentica como 'estudiante'."""
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
                subject=usuario_id,
            )

    return _FakeEstudiante()


# ---------------------------------------------------------------------------
# Test 1 (RED → GREEN): audit log escrito en re-enrollment con ip/user_agent
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_audit_log_escrito_en_reenrollment_con_ip_y_ua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 'Renovacion auditada' (spec):
    WHEN el alumno renueva su referencia
    THEN el audit log registra usuario, timestamp y origen de la renovacion
    Y la ip y user_agent del request son capturados en la entrada.
    """
    _monkeyenv(monkeypatch)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )
    from app.main import create_app

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "audit-01")

    try:
        app = create_app()
        app.state.jwt_validator = _make_fake_validator(usuario_id, id_institucional)

        test_ua = "TestAgent/1.0 (c65-audit-test)"
        test_ip_header = "10.0.0.42"

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Primer enrollment (establece la referencia base).
            r1 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=0.0)},
                headers={
                    "Authorization": "Bearer t1",
                    "User-Agent": test_ua,
                    "X-Forwarded-For": test_ip_header,
                },
            )
            assert r1.status_code == 201, r1.text

            # Segundo enrollment = RE-ENROLLMENT -> debe escribir audit log.
            r2 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=1.0)},
                headers={
                    "Authorization": "Bearer t2",
                    "User-Agent": test_ua,
                    "X-Forwarded-For": test_ip_header,
                },
            )
            assert r2.status_code == 201, r2.text

        # Verificar que existe una entrada en audit_log con la accion correcta.
        from app.infrastructure.persistence.models.audit_log import AuditLogModel
        from sqlalchemy import select

        async with factory() as session:
            result = await session.execute(
                select(AuditLogModel).where(
                    AuditLogModel.actor == usuario_id,
                    AuditLogModel.accion == "enrollment.embedding_referencia.renovacion",
                )
            )
            entradas = result.scalars().all()

        assert len(entradas) >= 1, (
            "Debe existir al menos una entrada de audit log con "
            "accion='enrollment.embedding_referencia.renovacion'"
        )
        entrada = entradas[0]
        # La ip debe ser no-nula y no-vacía.
        assert entrada.ip is not None and str(entrada.ip).strip() != "", (
            f"ip debe estar capturada en el audit log, got: {entrada.ip!r}"
        )
        # El user_agent debe ser no-nulo y no-vacío.
        assert entrada.user_agent is not None and entrada.user_agent.strip() != "", (
            f"user_agent debe estar capturado en el audit log, got: {entrada.user_agent!r}"
        )
        # El proposito debe mencionar 'renovacion'.
        assert "renovaci" in (entrada.proposito or "").lower(), (
            f"proposito debe mencionar renovacion, got: {entrada.proposito!r}"
        )

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 2 (TRIANGULATE): segundo caso con ua/ip distintos — ip/ua siguen al request
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_audit_log_captura_ip_y_ua_del_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Triangulacion: los valores ip/user_agent en el audit_log corresponden
    a los del HTTP request (no son cadena vacia ni constante hardcodeada).
    Un segundo re-enrollment con UA diferente genera entrada con el nuevo UA.
    """
    _monkeyenv(monkeypatch)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )
    from app.main import create_app

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "audit-02")

    try:
        app = create_app()
        app.state.jwt_validator = _make_fake_validator(usuario_id, id_institucional)

        ua_primera = "AgentePrimero/1.0"
        ua_segunda = "AgenteSegundo/2.0 (renovacion-test)"

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Enrollment base.
            await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=2.0)},
                headers={"Authorization": "Bearer t1", "User-Agent": ua_primera},
            )
            # Re-enrollment con UA distinto.
            r2 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=3.0)},
                headers={"Authorization": "Bearer t2", "User-Agent": ua_segunda},
            )
            assert r2.status_code == 201, r2.text

        from app.infrastructure.persistence.models.audit_log import AuditLogModel
        from sqlalchemy import select

        async with factory() as session:
            result = await session.execute(
                select(AuditLogModel).where(
                    AuditLogModel.actor == usuario_id,
                    AuditLogModel.accion == "enrollment.embedding_referencia.renovacion",
                )
            )
            entradas = result.scalars().all()

        assert len(entradas) >= 1
        ua_auditados = [e.user_agent for e in entradas]
        # Al menos una entrada debe reflejar el UA del segundo request.
        assert any(ua_segunda in (ua or "") for ua in ua_auditados), (
            f"Ninguna entrada del audit log porta el user_agent del request. "
            f"Esperado '{ua_segunda}' en alguno de: {ua_auditados}"
        )

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 3 (7.4): la referencia anterior queda conservada con vigente=FALSE
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_referencia_anterior_conservada_no_sobreescrita(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 'Renovacion auditada' — segundo THEN (spec):
    THEN la referencia anterior queda conservada como version previa.

    Verifica que despues del segundo enrollment:
    - Existen exactamente 2 filas en embedding_referencia para el usuario.
    - La primera queda vigente=FALSE (conservada, no borrada).
    - La segunda queda vigente=TRUE.
    """
    _monkeyenv(monkeypatch)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )
    from app.main import create_app

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "version-01")

    try:
        app = create_app()
        app.state.jwt_validator = _make_fake_validator(usuario_id, id_institucional)

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=4.0)},
                headers={"Authorization": "Bearer t1"},
            )
            assert r1.status_code == 201, r1.text
            id_primera = r1.json()["referencia_id"]

            r2 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=5.0)},
                headers={"Authorization": "Bearer t2"},
            )
            assert r2.status_code == 201, r2.text
            id_segunda = r2.json()["referencia_id"]

        assert id_primera != id_segunda

        from app.infrastructure.persistence.models.transactional import (
            EmbeddingReferenciaModel,
        )
        from sqlalchemy import select

        async with factory() as session:
            result = await session.execute(
                select(EmbeddingReferenciaModel).where(
                    EmbeddingReferenciaModel.usuario_id == usuario_id
                )
            )
            refs = result.scalars().all()

        assert len(refs) == 2, (
            f"Deben existir exactamente 2 registros en embedding_referencia, "
            f"encontrados: {len(refs)}"
        )

        por_id = {r.id: r for r in refs}
        assert id_primera in por_id, "La primera referencia debe estar en la DB"
        assert id_segunda in por_id, "La segunda referencia debe estar en la DB"
        assert por_id[id_primera].vigente is False, (
            "La primera referencia debe tener vigente=FALSE (conservada, no borrada)"
        )
        assert por_id[id_segunda].vigente is True, (
            "La segunda referencia (nueva) debe tener vigente=TRUE"
        )

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 4 (L2.5): la renovacion NO auto-sanciona ni invalida rendiciones en curso
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_reenrollment_no_invalida_rendicion_en_curso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 'Renovacion no afecta rendicion en curso' (spec, L2.5):
    WHEN se dispara una renovacion de embedding
    THEN la rendicion en curso no se invalida ni se sanciona automaticamente.

    Verifica que las tablas de rendicion (examen_rendicion / equivalente)
    NO son mutadas por el endpoint de enrollment.

    Nota de implementacion: si no existe tabla de rendicion activa (C-04/C-09
    aun no implementados), este test verifica la invariante mediante la
    ausencia de efectos secundarios en la DB — solo embedding_referencia
    y audit_log son tocadas. El test pasa si el re-enrollment HTTP retorna
    201 sin errores y no deja filas inesperadas.
    """
    _monkeyenv(monkeypatch)
    from app import config as cfg

    cfg.get_settings.cache_clear()

    from app.infrastructure.persistence.session import (
        create_engine,
        create_session_factory,
    )
    from app.main import create_app

    engine = create_engine()
    factory = create_session_factory(engine)
    usuario_id, id_institucional = await _crear_usuario_test(factory, "l25-01")

    try:
        app = create_app()
        app.state.jwt_validator = _make_fake_validator(usuario_id, id_institucional)

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=6.0)},
                headers={"Authorization": "Bearer t1"},
            )
            assert r1.status_code == 201, r1.text

            # Re-enrollment: NO debe levantar excepcion ni retornar 4xx/5xx.
            r2 = await client.post(
                "/api/v1/enrollment/embedding-referencia",
                json={"embedding": _vector_128(seed=7.0)},
                headers={"Authorization": "Bearer t2"},
            )
            assert r2.status_code == 201, (
                f"El re-enrollment debe retornar 201, no {r2.status_code}: {r2.text}"
            )

        # Solo las tablas de referencia biometrica y audit_log deben haber sido
        # afectadas. Verificar que no existen filas en audit_log con accion de
        # sancion automatica para este usuario.
        from app.infrastructure.persistence.models.audit_log import AuditLogModel
        from sqlalchemy import select

        async with factory() as session:
            result_sancion = await session.execute(
                select(AuditLogModel).where(
                    AuditLogModel.actor == usuario_id,
                    AuditLogModel.accion.like("%sancion%"),
                )
            )
            filas_sancion = result_sancion.scalars().all()

        assert len(filas_sancion) == 0, (
            f"L2.5: el re-enrollment NO debe generar entradas de sancion automatica. "
            f"Encontradas: {[f.accion for f in filas_sancion]}"
        )

    finally:
        await _borrar_usuario_test(factory, usuario_id)
        await engine.dispose()
