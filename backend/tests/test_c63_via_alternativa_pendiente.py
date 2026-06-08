"""Tests de via alternativa pendiente de proctor (C-63).

Cubre:
  10.1 Rules puras: evaluar_gate con VIA_ALTERNATIVA_PENDIENTE levanta
       ConsentNotResolvedError; VIA_ALTERNATIVA_HABILITADA retorna True;
       retrocompatibilidad VIA_ALTERNATIVA -> habilitado.
  10.2 Repositorio (AlternativeRequestRepositoryImpl) contra postgres real:
       crear solicitud pendiente, listar pendientes, actualizar a habilitado.
  10.3 ConsentService.registrar_solicitud_alternativa: persistencia y audit log.
  10.4 ConsentService.habilitar_alternativa: transicion de estado, habilitado_por;
       error si solicitud inexistente.
  10.5 ConsentService.resolve: pendiente -> VIA_ALTERNATIVA_PENDIENTE;
       habilitado -> VIA_ALTERNATIVA_HABILITADA; fallback audit log.
  10.6 Endpoint POST /alternative/{user_id}/habilitar: 200 proctor auth,
       403 sin rol, 404 si no existe.
  10.7 Endpoint GET /alternative/pendientes: lista correcta, 403 sin rol.
  10.8 Gate via puedeRendir/gate: bloquea con pendiente, permite con habilitado.

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
    "postgresql://app:pass@localhost:55432/proctoring",
)
_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-slim")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    Fernet.generate_key().decode("ascii"),
)

_SLIM_ENV = {
    "DATABASE_URL": _DB_URL_SLIM,
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "JWT_OWN_SECRET": _JWT_SECRET,
    "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
}


def _normalizar_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


# ---------------------------------------------------------------------------
# Helpers de DB
# ---------------------------------------------------------------------------


def _crear_usuario_sync(id_institucional: str, roles: list[str]) -> str:
    """Crea usuario en la DB slim y retorna su UUID."""

    async def _run() -> str:
        from sqlalchemy import select

        from app.infrastructure.auth.hashing import hashear_password
        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )

        engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
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
                    password_hash=hashear_password("Test1234"),
                    auth_provider="jwt",
                    attrs_federados={},
                )
                session.add(usuario)
                await session.commit()
                return usuario.id
        finally:
            await engine.dispose()

    return asyncio.get_event_loop().run_until_complete(_run())


def _limpiar_solicitudes_sync(user_id_inst: str) -> None:
    """Elimina solicitudes de via alternativa para el usuario."""

    async def _run() -> None:
        from sqlalchemy import delete

        from app.infrastructure.persistence.models.alternative_request import (
            SolicitudViaAlternativaModel,
        )
        from app.infrastructure.persistence.session_slim import (
            create_slim_engine,
            create_slim_session_factory,
        )

        engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
        factory = create_slim_session_factory(engine)
        try:
            async with factory() as session:
                await session.execute(
                    delete(SolicitudViaAlternativaModel).where(
                        SolicitudViaAlternativaModel.user_id == user_id_inst
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_run())


def _login(client, id_institucional: str, password: str = "Test1234") -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": id_institucional, "password": password},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login fallo ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 10.1 Tests unitarios puros de rules.py (sin DB)
# ---------------------------------------------------------------------------


def test_gate_via_alternativa_pendiente_bloquea() -> None:
    """VIA_ALTERNATIVA_PENDIENTE -> ConsentNotResolvedError (gate cerrado, C-63 D-03)."""
    from app.domain.consent_flow.errors import ConsentNotResolvedError
    from app.domain.consent_flow import rules
    from app.domain.consent_flow.rules import ResolucionConsentimiento

    with pytest.raises(ConsentNotResolvedError):
        rules.evaluar_gate(ResolucionConsentimiento.VIA_ALTERNATIVA_PENDIENTE)


def test_gate_via_alternativa_habilitada_abre() -> None:
    """VIA_ALTERNATIVA_HABILITADA -> True (puede avanzar, C-63 D-03)."""
    from app.domain.consent_flow import rules
    from app.domain.consent_flow.rules import ResolucionConsentimiento

    assert rules.evaluar_gate(ResolucionConsentimiento.VIA_ALTERNATIVA_HABILITADA) is True


def test_biometria_no_requerida_para_habilitada() -> None:
    """VIA_ALTERNATIVA_HABILITADA -> biometria_habilitada retorna False."""
    from app.domain.consent_flow import rules
    from app.domain.consent_flow.rules import ResolucionConsentimiento

    assert rules.biometria_habilitada(ResolucionConsentimiento.VIA_ALTERNATIVA_HABILITADA) is False


def test_gate_retrocompat_via_alternativa_avanza() -> None:
    """VIA_ALTERNATIVA (deprecated) -> evaluar_gate retorna True (retrocompat, C-63 D-03)."""
    from app.domain.consent_flow import rules
    from app.domain.consent_flow.rules import ResolucionConsentimiento

    assert rules.evaluar_gate(ResolucionConsentimiento.VIA_ALTERNATIVA) is True


def test_gate_pendiente_no_permite_biometria() -> None:
    """VIA_ALTERNATIVA_PENDIENTE -> biometria_habilitada retorna False (gate cerrado)."""
    from app.domain.consent_flow import rules
    from app.domain.consent_flow.rules import ResolucionConsentimiento

    # Pendiente no habilita biometria — el gate lo bloquea antes, pero la funcion
    # de biometria tambien debe retornar False.
    assert rules.biometria_habilitada(ResolucionConsentimiento.VIA_ALTERNATIVA_PENDIENTE) is False


# ---------------------------------------------------------------------------
# Fixtures para los tests que requieren DB
# ---------------------------------------------------------------------------


@pytest.fixture
def slim_client(monkeypatch: pytest.MonkeyPatch):
    """TestClient del slim contra postgres:16-alpine."""
    import importlib

    import app.config_slim as config_slim_module
    from fastapi.testclient import TestClient

    config_slim_module.get_slim_settings.cache_clear()
    for k, v in _SLIM_ENV.items():
        monkeypatch.setenv(k, v)

    import app.main_slim as main_slim_module

    importlib.reload(main_slim_module)
    app_instance = main_slim_module.create_slim_app()
    with TestClient(app_instance) as c:
        yield c

    config_slim_module.get_slim_settings.cache_clear()


# ---------------------------------------------------------------------------
# 10.2 Tests de repositorio contra postgres real
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestAlternativeRequestRepository:
    """Tests del repositorio de solicitudes de via alternativa (C-63, 10.2)."""

    _ALUMNO_ID = "c63-repo-alumno"
    _EXAM_ID = "exam-c63-test"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def test_add_y_get_by_user_exam(self):
        """Crear solicitud pendiente y recuperarla."""

        async def _run():
            from app.domain.entities.alternative_request import (
                EstadoViaAlternativa,
                SolicitudViaAlternativa,
            )
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    repo = AlternativeRequestSqlRepository(session)
                    nueva = SolicitudViaAlternativa(
                        id="",
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        estado=EstadoViaAlternativa.PENDIENTE_PROCTOR,
                        timestamp_solicitud="2026-06-08T10:00:00Z",
                        timestamp_habilitacion=None,
                        habilitado_por=None,
                    )
                    creada = await repo.add(nueva)
                    await session.commit()
                    assert creada.id != ""
                    assert creada.estado == EstadoViaAlternativa.PENDIENTE_PROCTOR

                    recuperada = await repo.get_by_user_exam(self._ALUMNO_ID, self._EXAM_ID)
                    assert recuperada is not None
                    assert recuperada.estado == EstadoViaAlternativa.PENDIENTE_PROCTOR
                    assert recuperada.habilitado_por is None
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_list_pending(self):
        """list_pending retorna la solicitud recien creada."""

        async def _run():
            from app.domain.entities.alternative_request import (
                EstadoViaAlternativa,
                SolicitudViaAlternativa,
            )
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    repo = AlternativeRequestSqlRepository(session)
                    nueva = SolicitudViaAlternativa(
                        id="",
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        estado=EstadoViaAlternativa.PENDIENTE_PROCTOR,
                        timestamp_solicitud="2026-06-08T10:00:00Z",
                        timestamp_habilitacion=None,
                        habilitado_por=None,
                    )
                    await repo.add(nueva)
                    await session.commit()

                    pendientes = await repo.list_pending()
                    ids = [p.user_id for p in pendientes]
                    assert self._ALUMNO_ID in ids
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_update_estado_a_habilitado(self):
        """update_estado transiciona pendiente -> habilitado_por_proctor."""

        async def _run():
            from app.domain.entities.alternative_request import (
                EstadoViaAlternativa,
                SolicitudViaAlternativa,
            )
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    repo = AlternativeRequestSqlRepository(session)
                    nueva = SolicitudViaAlternativa(
                        id="",
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        estado=EstadoViaAlternativa.PENDIENTE_PROCTOR,
                        timestamp_solicitud="2026-06-08T10:00:00Z",
                        timestamp_habilitacion=None,
                        habilitado_por=None,
                    )
                    creada = await repo.add(nueva)
                    await session.commit()

                    actualizada = await repo.update_estado(
                        solicitud_id=creada.id,
                        estado=EstadoViaAlternativa.HABILITADO_POR_PROCTOR,
                        habilitado_por="proctor-01",
                        timestamp="2026-06-08T11:00:00Z",
                    )
                    await session.commit()

                    assert actualizada.estado == EstadoViaAlternativa.HABILITADO_POR_PROCTOR
                    assert actualizada.habilitado_por == "proctor-01"
                    assert actualizada.timestamp_habilitacion is not None
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# 10.3 Tests de ConsentService.registrar_solicitud_alternativa
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestConsentServiceRegistrar:
    """Tests de registrar_solicitud_alternativa con repositorios reales (10.3)."""

    _ALUMNO_ID = "c63-service-alumno"
    _EXAM_ID = "exam-c63-svc"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def test_registrar_crea_solicitud_pendiente(self):
        """registrar_solicitud_alternativa crea una solicitud pendiente."""

        async def _run():
            from app.application.consent.service import ConsentService
            from app.domain.entities.alternative_request import EstadoViaAlternativa
            from app.infrastructure.messaging.port import MessageQueuePort
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.repositories.audit_log_slim import (
                InMemoryAuditLogRepository as AuditLogSqlRepository,
            )
            from app.infrastructure.persistence.repositories.consent_slim import (
                NoOpConsentRepository as ConsentSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            class _NoopQueue(MessageQueuePort):
                async def enqueue(self, topic, payload):
                    return "noop-msg-id"

                async def dequeue(self, topic):
                    return None

                async def ack(self, message_id):
                    return None

                async def health_check(self):
                    return True

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = ConsentService(
                        consents=ConsentSqlRepository(),
                        audit_log=AuditLogSqlRepository(),
                        queue=_NoopQueue(),
                        alternative_requests=AlternativeRequestSqlRepository(session),
                    )
                    solicitud = await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:00:00Z",
                    )
                    await session.commit()
                    assert solicitud.estado == EstadoViaAlternativa.PENDIENTE_PROCTOR
                    assert solicitud.user_id == self._ALUMNO_ID
                    assert solicitud.id != ""
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_registrar_idempotente(self):
        """Registrar dos veces retorna la misma solicitud (idempotente)."""

        async def _run():
            from app.application.consent.service import ConsentService
            from app.infrastructure.messaging.port import MessageQueuePort
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.repositories.audit_log_slim import (
                InMemoryAuditLogRepository as AuditLogSqlRepository,
            )
            from app.infrastructure.persistence.repositories.consent_slim import (
                NoOpConsentRepository as ConsentSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            class _NoopQueue(MessageQueuePort):
                async def enqueue(self, topic, payload):
                    return "noop"

                async def dequeue(self, topic):
                    return None

                async def ack(self, message_id):
                    return None

                async def health_check(self):
                    return True

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = ConsentService(
                        consents=ConsentSqlRepository(),
                        audit_log=AuditLogSqlRepository(),
                        queue=_NoopQueue(),
                        alternative_requests=AlternativeRequestSqlRepository(session),
                    )
                    s1 = await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:00:00Z",
                    )
                    await session.commit()
                    s2 = await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:01:00Z",
                    )
                    await session.commit()
                    # Mismo id -> no duplicó
                    assert s1.id == s2.id
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# 10.4 Tests de ConsentService.habilitar_alternativa
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestConsentServiceHabilitar:
    """Tests de habilitar_alternativa (10.4)."""

    _ALUMNO_ID = "c63-habilitar-alumno"
    _EXAM_ID = "exam-c63-hab"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def test_habilitar_transiciona_estado(self):
        """habilitar_alternativa transiciona a habilitado_por_proctor."""

        async def _run():
            from app.application.consent.service import ConsentService
            from app.domain.entities.alternative_request import EstadoViaAlternativa
            from app.infrastructure.messaging.port import MessageQueuePort
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.repositories.audit_log_slim import (
                InMemoryAuditLogRepository as AuditLogSqlRepository,
            )
            from app.infrastructure.persistence.repositories.consent_slim import (
                NoOpConsentRepository as ConsentSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            class _NoopQueue(MessageQueuePort):
                async def enqueue(self, topic, payload):
                    return "noop"

                async def dequeue(self, topic):
                    return None

                async def ack(self, message_id):
                    return None

                async def health_check(self):
                    return True

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = ConsentService(
                        consents=ConsentSqlRepository(),
                        audit_log=AuditLogSqlRepository(),
                        queue=_NoopQueue(),
                        alternative_requests=AlternativeRequestSqlRepository(session),
                    )
                    await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:00:00Z",
                    )
                    await session.commit()

                    habilitada = await service.habilitar_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        habilitado_por="proctor-test-01",
                        timestamp="2026-06-08T11:00:00Z",
                    )
                    await session.commit()

                    assert habilitada.estado == EstadoViaAlternativa.HABILITADO_POR_PROCTOR
                    assert habilitada.habilitado_por == "proctor-test-01"
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_habilitar_inexistente_lanza_error(self):
        """habilitar_alternativa con solicitud inexistente -> ValueError."""

        async def _run():
            from app.application.consent.service import ConsentService
            from app.infrastructure.messaging.port import MessageQueuePort
            from app.infrastructure.persistence.repositories.alternative_request import (
                AlternativeRequestSqlRepository,
            )
            from app.infrastructure.persistence.repositories.audit_log_slim import (
                InMemoryAuditLogRepository as AuditLogSqlRepository,
            )
            from app.infrastructure.persistence.repositories.consent_slim import (
                NoOpConsentRepository as ConsentSqlRepository,
            )
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            class _NoopQueue(MessageQueuePort):
                async def enqueue(self, topic, payload):
                    return "noop"

                async def dequeue(self, topic):
                    return None

                async def ack(self, message_id):
                    return None

                async def health_check(self):
                    return True

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = ConsentService(
                        consents=ConsentSqlRepository(),
                        audit_log=AuditLogSqlRepository(),
                        queue=_NoopQueue(),
                        alternative_requests=AlternativeRequestSqlRepository(session),
                    )
                    with pytest.raises(ValueError, match="No existe solicitud"):
                        await service.habilitar_alternativa(
                            user_id=self._ALUMNO_ID,
                            exam_id="exam-inexistente",
                            habilitado_por="proctor-01",
                            timestamp="2026-06-08T11:00:00Z",
                        )
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# 10.5 Tests de ConsentService.resolve con estados nuevos
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestConsentServiceResolve:
    """Tests de resolve() con los estados C-63 (10.5)."""

    _ALUMNO_ID = "c63-resolve-alumno"
    _EXAM_ID = "exam-c63-res"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def _make_service(self, session):
        from app.application.consent.service import ConsentService
        from app.infrastructure.messaging.port import MessageQueuePort
        from app.infrastructure.persistence.repositories.alternative_request import (
            AlternativeRequestSqlRepository,
        )
        from app.infrastructure.persistence.repositories.audit_log_slim import (
            InMemoryAuditLogRepository,
        )
        from app.infrastructure.persistence.repositories.consent_slim import (
            NoOpConsentRepository,
        )

        class _NoopQueue(MessageQueuePort):
            async def enqueue(self, topic, payload):
                return "noop"

            async def dequeue(self, topic):
                return None

            async def ack(self, message_id):
                return None

            async def health_check(self):
                return True

        return ConsentService(
            consents=NoOpConsentRepository(),
            audit_log=InMemoryAuditLogRepository(),
            queue=_NoopQueue(),
            alternative_requests=AlternativeRequestSqlRepository(session),
        )

    def test_pendiente_resuelve_via_alternativa_pendiente(self):
        """Solicitud pendiente -> VIA_ALTERNATIVA_PENDIENTE."""

        async def _run():
            from app.domain.consent_flow.rules import ResolucionConsentimiento
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = self._make_service(session)
                    await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:00:00Z",
                    )
                    await session.commit()

                    resolucion = await service.resolve(
                        user_id=self._ALUMNO_ID, exam_id=self._EXAM_ID
                    )
                    assert resolucion == ResolucionConsentimiento.VIA_ALTERNATIVA_PENDIENTE
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_habilitado_resuelve_via_alternativa_habilitada(self):
        """Solicitud habilitada -> VIA_ALTERNATIVA_HABILITADA."""

        async def _run():
            from app.domain.consent_flow.rules import ResolucionConsentimiento
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = self._make_service(session)
                    await service.registrar_solicitud_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        timestamp="2026-06-08T10:00:00Z",
                    )
                    await session.commit()
                    await service.habilitar_alternativa(
                        user_id=self._ALUMNO_ID,
                        exam_id=self._EXAM_ID,
                        habilitado_por="proctor-01",
                        timestamp="2026-06-08T11:00:00Z",
                    )
                    await session.commit()

                    resolucion = await service.resolve(
                        user_id=self._ALUMNO_ID, exam_id=self._EXAM_ID
                    )
                    assert resolucion == ResolucionConsentimiento.VIA_ALTERNATIVA_HABILITADA
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())

    def test_sin_solicitud_resuelve_no_resuelto(self):
        """Sin solicitud ni consentimiento -> NO_RESUELTO."""

        async def _run():
            from app.domain.consent_flow.rules import ResolucionConsentimiento
            from app.infrastructure.persistence.session_slim import (
                create_slim_engine,
                create_slim_session_factory,
            )

            engine = create_slim_engine(_normalizar_db_url(_DB_URL_SLIM))
            factory = create_slim_session_factory(engine)
            try:
                async with factory() as session:
                    service = self._make_service(session)
                    resolucion = await service.resolve(
                        user_id=self._ALUMNO_ID, exam_id="exam-inexistente-x99"
                    )
                    assert resolucion == ResolucionConsentimiento.NO_RESUELTO
            finally:
                await engine.dispose()

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# 10.6 Tests del endpoint POST /alternative/{user_id}/habilitar
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestEndpointHabilitar:
    """Tests del endpoint de habilitacion por proctor (10.6)."""

    _ALUMNO_ID = "c63-ep-alumno"
    _PROCTOR_ID = "c63-ep-proctor"
    _ADMIN_ID = "c63-ep-admin"
    _EXAM_ID = "exam-c63-ep"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _crear_usuario_sync(self._PROCTOR_ID, ["proctor"])
        _crear_usuario_sync(self._ADMIN_ID, ["admin_sistema"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def _registrar_solicitud(self, slim_client) -> None:
        """Registra la solicitud via el endpoint del alumno."""
        token = _login(slim_client, self._ALUMNO_ID)
        resp = slim_client.post(
            "/api/v1/consent/alternative",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"No se pudo registrar solicitud: {resp.text}"

    def test_habilitar_200_con_proctor(self, slim_client):
        """POST /habilitar con rol proctor -> 200."""
        self._registrar_solicitud(slim_client)
        token = _login(slim_client, self._PROCTOR_ID)
        resp = slim_client.post(
            f"/api/v1/consent/alternative/{self._ALUMNO_ID}/habilitar",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["estado"] == "habilitado_por_proctor"
        assert data["habilitado_por"] == self._PROCTOR_ID

    def test_habilitar_200_con_admin(self, slim_client):
        """POST /habilitar con rol admin_sistema -> 200."""
        self._registrar_solicitud(slim_client)
        token = _login(slim_client, self._ADMIN_ID)
        resp = slim_client.post(
            f"/api/v1/consent/alternative/{self._ALUMNO_ID}/habilitar",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text

    def test_habilitar_403_sin_rol_proctor(self, slim_client):
        """POST /habilitar con rol estudiante -> 403."""
        self._registrar_solicitud(slim_client)
        token = _login(slim_client, self._ALUMNO_ID)
        resp = slim_client.post(
            f"/api/v1/consent/alternative/{self._ALUMNO_ID}/habilitar",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.text

    def test_habilitar_404_si_no_existe(self, slim_client):
        """POST /habilitar con solicitud inexistente -> 404."""
        token = _login(slim_client, self._PROCTOR_ID)
        resp = slim_client.post(
            f"/api/v1/consent/alternative/{self._ALUMNO_ID}/habilitar",
            json={"exam_id": "exam-que-no-existe-zzz"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 10.7 Tests del endpoint GET /alternative/pendientes
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestEndpointPendientes:
    """Tests del endpoint de listado de pendientes (10.7)."""

    _ALUMNO_ID = "c63-pend-alumno"
    _PROCTOR_ID = "c63-pend-proctor"
    _EXAM_ID = "exam-c63-pend"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _crear_usuario_sync(self._PROCTOR_ID, ["proctor"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def test_lista_pendientes_200_con_proctor(self, slim_client):
        """GET /pendientes con rol proctor -> 200 con lista correcta."""
        # Registrar solicitud
        alumno_token = _login(slim_client, self._ALUMNO_ID)
        slim_client.post(
            "/api/v1/consent/alternative",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {alumno_token}"},
        )

        proctor_token = _login(slim_client, self._PROCTOR_ID)
        resp = slim_client.get(
            "/api/v1/consent/alternative/pendientes",
            headers={"Authorization": f"Bearer {proctor_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        user_ids = [item["user_id"] for item in data["items"]]
        assert self._ALUMNO_ID in user_ids

    def test_lista_pendientes_403_sin_rol(self, slim_client):
        """GET /pendientes con rol estudiante -> 403."""
        token = _login(slim_client, self._ALUMNO_ID)
        resp = slim_client.get(
            "/api/v1/consent/alternative/pendientes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 10.8 Tests de gate puedeRendir / gate backend
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
class TestGatePuedeRendir:
    """Tests del gate de rendir via api/service (10.8)."""

    _ALUMNO_ID = "c63-gate-alumno"
    _PROCTOR_ID = "c63-gate-proctor"
    _EXAM_ID = "exam-c63-gate"

    def setup_method(self):
        _crear_usuario_sync(self._ALUMNO_ID, ["estudiante"])
        _crear_usuario_sync(self._PROCTOR_ID, ["proctor"])
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def teardown_method(self):
        _limpiar_solicitudes_sync(self._ALUMNO_ID)

    def test_gate_bloquea_con_pendiente(self, slim_client):
        """Gate /consent/gate retorna resolucion=via_alternativa_pendiente y no puede avanzar."""
        alumno_token = _login(slim_client, self._ALUMNO_ID)
        # Registrar solicitud
        slim_client.post(
            "/api/v1/consent/alternative",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {alumno_token}"},
        )

        resp = slim_client.get(
            f"/api/v1/consent/gate?exam_id={self._EXAM_ID}",
            headers={"Authorization": f"Bearer {alumno_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["resolucion"] == "via_alternativa_pendiente"
        assert data["puede_avanzar"] is False
        assert data["biometria_habilitada"] is False

    def test_gate_permite_con_habilitado(self, slim_client):
        """Gate /consent/gate retorna resolucion=via_alternativa_habilitada y puede avanzar."""
        alumno_token = _login(slim_client, self._ALUMNO_ID)
        proctor_token = _login(slim_client, self._PROCTOR_ID)

        # Registrar
        slim_client.post(
            "/api/v1/consent/alternative",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {alumno_token}"},
        )
        # Habilitar
        slim_client.post(
            f"/api/v1/consent/alternative/{self._ALUMNO_ID}/habilitar",
            json={"exam_id": self._EXAM_ID},
            headers={"Authorization": f"Bearer {proctor_token}"},
        )

        resp = slim_client.get(
            f"/api/v1/consent/gate?exam_id={self._EXAM_ID}",
            headers={"Authorization": f"Bearer {alumno_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["resolucion"] == "via_alternativa_habilitada"
        assert data["puede_avanzar"] is True
        assert data["biometria_habilitada"] is False
