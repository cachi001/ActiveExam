"""Tests del EventIngestionService con puertos EN MEMORIA (C-10, sin DB).

Cubre: validacion de firma antes de persistir, rechazo de no firmado / invalido
(no persiste ni fan-out), persistencia + fan-out de evento valido, evento critico
sin sancion (L2.5), heartbeat firmado / con firma invalida, y fan-out swappable.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.events.ingestion import (
    EventIngestionService,
    SesionInexistenteError,
)
from app.domain.biometrics import custody
from app.domain.events.schema import EventoMalFormadoError, VersionNoSoportadaError
from app.domain.events.signature import (
    FirmaInvalidaError,
    firmar_evento,
)
from app.domain.events.schema import construir_entrante
from app.domain.entities.session import Sesion
from app.infrastructure.messaging.backplane import build_backplane

# Reusa el repo de Evento en memoria y el de Sesion del test de biometria.
from tests.test_biometrics_service import InMemoryEventRepo, InMemorySessionRepo

_CLAVE = custody.derivar_clave_sesion(secreto_maestro=b"secreto", session_id="sess-1")


class FakeBackplaneRecorder:
    """Publisher inyectable que registra las publicaciones para asertarlas."""

    def __init__(self) -> None:
        self.publicados: list[tuple[str, dict]] = []

    async def __call__(self, canal: str, evento: dict) -> None:
        self.publicados.append((canal, evento))


def _datos(firma: str, **over) -> dict:
    base = {
        "id": "evt-1", "session_id": "sess-1", "exam_id": "e1",
        "tipo": "multiples_rostros", "severidad": "alta",
        "ts_client": "2026-05-30T10:00:00Z", "payload": {"rostros": 2},
        "firma": firma, "schema_version": 1,
    }
    base.update(over)
    return base


def _firma_valida(**over) -> str:
    ev = construir_entrante(_datos("x", **over))
    return firmar_evento(ev, clave_sesion=_CLAVE)


def _build(backend: str = "postgres"):
    sesion = Sesion(id="sess-1", user_id="u1", exam_id="e1", clave_sesion=_CLAVE)
    eventos = InMemoryEventRepo()
    sesiones = InMemorySessionRepo(sesion)
    recorder = FakeBackplaneRecorder()
    backplane = build_backplane(backend, recorder)
    svc = EventIngestionService(eventos=eventos, sesiones=sesiones, backplane=backplane)
    return svc, eventos, recorder, backplane


def test_evento_firmado_se_persiste_y_propaga() -> None:
    async def run() -> None:
        svc, eventos, recorder, _ = _build()
        firma = _firma_valida()
        res = await svc.ingest(_datos(firma), ts_backend="2026-05-30T10:00:01Z")
        assert res.persistido is True
        assert len(eventos.items) == 1
        # ts_backend completado server-side (no por el cliente).
        assert eventos.items[0].timestamp_backend == "2026-05-30T10:00:01Z"
        # Fan-out al canal del examen.
        assert len(recorder.publicados) == 1
        assert recorder.publicados[0][0] == "panel:e1"

    asyncio.run(run())


def test_evento_con_firma_invalida_no_persiste_ni_propaga() -> None:
    async def run() -> None:
        svc, eventos, recorder, _ = _build()
        with pytest.raises(FirmaInvalidaError):
            await svc.ingest(_datos("00" * 32), ts_backend="t")
        assert eventos.items == []  # NO persistio
        assert recorder.publicados == []  # NO hizo fan-out

    asyncio.run(run())


def test_evento_sin_firma_se_rechaza() -> None:
    async def run() -> None:
        svc, eventos, recorder, _ = _build()
        with pytest.raises(EventoMalFormadoError):
            # firma ausente -> mal formado (campo obligatorio).
            datos = _datos("x")
            del datos["firma"]
            await svc.ingest(datos, ts_backend="t")
        assert eventos.items == []
        assert recorder.publicados == []

    asyncio.run(run())


def test_version_no_soportada_se_rechaza() -> None:
    async def run() -> None:
        svc, eventos, _, _ = _build()
        with pytest.raises(VersionNoSoportadaError):
            await svc.ingest(_datos("x", schema_version=99), ts_backend="t")
        assert eventos.items == []

    asyncio.run(run())


def test_version_confiable_es_la_refirmada_server_side() -> None:
    async def run() -> None:
        svc, eventos, _, _ = _build()
        firma_cliente = _firma_valida()
        await svc.ingest(_datos(firma_cliente), ts_backend="t")
        # Lo persistido lleva la firma re-calculada server-side (fuente de verdad).
        persistido = eventos.items[0]
        ev = construir_entrante(_datos(firma_cliente))
        from app.domain.events.signature import firmar_evento as refirma
        assert persistido.firma == refirma(ev, clave_sesion=_CLAVE)

    asyncio.run(run())


def test_evento_critico_se_persiste_sin_sancion() -> None:
    async def run() -> None:
        svc, eventos, recorder, _ = _build()
        firma = _firma_valida(
            id="evt-2", tipo="posible_cambio_identidad", severidad="critica"
        )
        res = await svc.ingest(
            _datos(firma, id="evt-2", tipo="posible_cambio_identidad", severidad="critica"),
            ts_backend="t",
        )
        # Persiste + propaga; el resultado NO contiene ninguna sancion/abort (L2.5).
        assert res.persistido is True
        assert len(recorder.publicados) == 1
        assert not hasattr(res, "sancion")
        assert not hasattr(res, "abortar")

    asyncio.run(run())


def test_heartbeat_firmado_cuenta_como_prueba_de_vida() -> None:
    async def run() -> None:
        svc, _, _, _ = _build()
        firma = _firma_valida(id="hb-1", tipo="heartbeat", severidad="baseline")
        ok = await svc.ingest_heartbeat(
            _datos(firma, id="hb-1", tipo="heartbeat", severidad="baseline"),
            ts_backend="t",
        )
        assert ok is True

    asyncio.run(run())


def test_heartbeat_con_firma_invalida_no_cuenta() -> None:
    async def run() -> None:
        svc, eventos, _, _ = _build()
        ok = await svc.ingest_heartbeat(
            _datos("00" * 32, id="hb-1", tipo="heartbeat", severidad="baseline"),
            ts_backend="t",
        )
        assert ok is False
        assert eventos.items == []

    asyncio.run(run())


def test_sesion_inexistente_se_rechaza() -> None:
    async def run() -> None:
        svc, eventos, _, _ = _build()
        with pytest.raises(SesionInexistenteError):
            await svc.ingest(_datos(_firma_valida(), session_id="otra"), ts_backend="t")
        assert eventos.items == []

    asyncio.run(run())


def test_backplane_swappable_redis_sin_cambiar_ingesta() -> None:
    async def run() -> None:
        # Mismo flujo de ingesta, adaptador Redis: el canal/contrato no cambia.
        svc, eventos, recorder, backplane = _build(backend="redis")
        from app.infrastructure.messaging.backplane import RedisPubSubBackplane
        assert isinstance(backplane, RedisPubSubBackplane)
        await svc.ingest(_datos(_firma_valida()), ts_backend="t")
        assert recorder.publicados[0][0] == "panel:e1"

    asyncio.run(run())
