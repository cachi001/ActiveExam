"""Tests puros del verificador de cadena de custodia (c-18 slim).

Slim: la "cadena" se reduce a la etapa que existe en `proctoring_event`:
- `screenshot_b64` — el binario crudo subido por el cliente
- `screenshot_sha256` — hash SHA-256 registrado al recibir

El verify-chain slim re-calcula SHA-256 del binario actual y lo compara con
el hash registrado al momento de la ingesta. Si coincide → cadena INTEGRA.
Si difiere → cadena ROTA (la evidencia fue modificada o el hash original era
incorrecto). Si falta material (screenshot null) → cadena INCOMPLETA.

Las 4 etapas full (cliente HMAC, backend, worker firma maestra,
re-inferencia) viven en c-68 (sucesor planificado) cuando llegue tabla
`evidencia`.
"""

from __future__ import annotations

import hashlib

import pytest

from app.application.verify_chain.service import VerifyChainService
from app.domain.verify_chain.certificate import (
    ChainStageResult,
    ChainVerificationStatus,
    CustodyChainCertificate,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeEventRepo:
    """Repo en memoria con el contrato (id) -> (screenshot_b64, sha256_registrado)."""

    def __init__(self, events: dict[str, tuple[str | None, str | None]]) -> None:
        self._events = events

    async def get_event_material(
        self, event_id: str
    ) -> tuple[str | None, str | None] | None:
        return self._events.get(event_id)


class FakeAuditor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    async def log_chain_verification(
        self, event_id: str, *, actor: str, status: str, proposito: str
    ) -> None:
        self.calls.append((event_id, actor, status, proposito))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_b64(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _make_service(events: dict[str, tuple[str | None, str | None]]):
    auditor = FakeAuditor()
    service = VerifyChainService(
        event_repo=FakeEventRepo(events),
        auditor=auditor,
    )
    return service, auditor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_certificate_es_value_object_inmutable() -> None:
    """El certificado emitido es inmutable (frozen dataclass)."""
    from dataclasses import FrozenInstanceError

    cert = CustodyChainCertificate(
        event_id="e1",
        status=ChainVerificationStatus.INTACT,
        algorithm="sha256",
        stages=[
            ChainStageResult(
                stage="screenshot_recorded",
                expected="abc",
                actual="abc",
                match=True,
            ),
        ],
        verified_at="2026-06-11T12:00:00+00:00",
    )
    with pytest.raises(FrozenInstanceError):
        cert.event_id = "otro"  # type: ignore[misc]


def test_status_enum_tiene_tres_valores() -> None:
    assert ChainVerificationStatus.INTACT.value == "intact"
    assert ChainVerificationStatus.BROKEN.value == "broken"
    assert ChainVerificationStatus.MATERIAL_MISSING.value == "material_missing"
    assert len(list(ChainVerificationStatus)) == 3


@pytest.mark.asyncio
async def test_verify_cadena_integra_cuando_hash_coincide() -> None:
    """screenshot + sha256 registrado coinciden → cadena INTEGRA."""
    content = "fake-screenshot-content"
    registered_hash = _sha256_b64(content)
    service, auditor = _make_service({"e1": (content, registered_hash)})

    cert = await service.verify("e1", actor="revisor:tribunal")

    assert cert.event_id == "e1"
    assert cert.status == ChainVerificationStatus.INTACT
    assert len(cert.stages) == 1
    assert cert.stages[0].stage == "screenshot_recorded"
    assert cert.stages[0].match is True
    assert cert.stages[0].expected == registered_hash
    assert cert.stages[0].actual == registered_hash
    # Audit log con el resultado
    assert auditor.calls == [
        ("e1", "revisor:tribunal", "intact", "verify-chain: cadena integra")
    ]


@pytest.mark.asyncio
async def test_verify_cadena_rota_cuando_hash_difiere() -> None:
    """sha256 registrado != re-calculado → cadena ROTA (evidencia no sostenida)."""
    content = "screenshot-modificado"
    bad_hash = "0" * 64  # hash registrado distinto al real
    service, auditor = _make_service({"e1": (content, bad_hash)})

    cert = await service.verify("e1", actor="revisor:tribunal")

    assert cert.status == ChainVerificationStatus.BROKEN
    assert cert.stages[0].match is False
    assert cert.stages[0].expected == bad_hash
    assert cert.stages[0].actual == _sha256_b64(content)
    # Audit log con cadena rota
    assert auditor.calls == [
        ("e1", "revisor:tribunal", "broken", "verify-chain: cadena rota — evidencia no sostenida")
    ]


@pytest.mark.asyncio
async def test_verify_material_missing_cuando_no_hay_screenshot() -> None:
    """Evento sin screenshot guardado (NULL) → MATERIAL_MISSING."""
    service, auditor = _make_service({"e1": (None, "abc")})

    cert = await service.verify("e1", actor="revisor:tribunal")

    assert cert.status == ChainVerificationStatus.MATERIAL_MISSING
    assert cert.stages[0].match is False
    assert auditor.calls[0][2] == "material_missing"


@pytest.mark.asyncio
async def test_verify_material_missing_cuando_no_hay_hash_registrado() -> None:
    """Evento sin sha256_registrado → MATERIAL_MISSING (no hay con que comparar)."""
    service, auditor = _make_service({"e1": ("contenido", None)})

    cert = await service.verify("e1", actor="revisor:tribunal")

    assert cert.status == ChainVerificationStatus.MATERIAL_MISSING


@pytest.mark.asyncio
async def test_verify_evento_inexistente_lanza_error() -> None:
    """Si el event_id no existe en el repo → ValueError descriptivo."""
    service, _ = _make_service({})
    with pytest.raises(ValueError, match="no encontrado"):
        await service.verify("inexistente", actor="actor")


def test_certificate_no_contiene_pii() -> None:
    """El certificado expone hashes + algoritmo + timestamp, NO el binario.
    Un perito independiente puede recomputar sin acceso a la API."""
    cert = CustodyChainCertificate(
        event_id="e1",
        status=ChainVerificationStatus.INTACT,
        algorithm="sha256",
        stages=[
            ChainStageResult(
                stage="screenshot_recorded",
                expected="abc",
                actual="abc",
                match=True,
            ),
        ],
        verified_at="2026-06-11T12:00:00+00:00",
    )
    # No deberia haber atributo que exponga el binario crudo
    assert not hasattr(cert, "screenshot")
    assert not hasattr(cert, "screenshot_b64")
    assert not hasattr(cert, "content")
