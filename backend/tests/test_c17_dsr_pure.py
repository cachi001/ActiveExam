"""Tests puros del DSR (c-17 slim).

Cubre los 4 tipos de derecho del titular (Ley 25.326):
- ACCESS: devuelve los datos personales del usuario.
- RECTIFICATION: corrige email/nombre/apellido.
- ERASURE: borra biometria + screenshots + sesiones, anonimiza usuario.
- PORTABILITY: exporta JSON estructurado del titular.

Slim: el HoldVerifier es Null por default (reutilizamos el de c-19) — no hay
holds por caso disciplinario porque no existe la tabla. Cuando llegue c-69 se
inyecta un SqlHoldVerifier sin tocar este servicio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.application.dsr.service import DsrService
from app.domain.dsr.report import DsrErasureReport, DsrType
from app.domain.retention.hold import HoldDecision
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeUserRepo:
    """Devuelve datos del usuario y permite borrar/actualizar."""

    users: dict[str, dict] = field(default_factory=dict)
    deleted_sessions: list[str] = field(default_factory=list)
    embeddings_deleted: dict[str, int] = field(default_factory=dict)
    fotos_deleted: dict[str, int] = field(default_factory=dict)
    anonymized: list[str] = field(default_factory=list)
    sessions_by_user: dict[str, list[str]] = field(default_factory=dict)

    async def get_user(self, usuario_id: str) -> dict | None:
        return self.users.get(usuario_id)

    async def update_user_fields(
        self, usuario_id: str, *, email: str | None, nombre: str | None, apellido: str | None
    ) -> None:
        u = self.users[usuario_id]
        if email is not None:
            u["email"] = email
        if nombre is not None:
            u["nombre"] = nombre
        if apellido is not None:
            u["apellido"] = apellido

    async def list_sessions_for_user(self, usuario_id: str) -> list[str]:
        return list(self.sessions_by_user.get(usuario_id, []))

    async def delete_session(self, session_id: str) -> None:
        self.deleted_sessions.append(session_id)

    async def delete_embeddings(self, usuario_id: str) -> int:
        self.embeddings_deleted[usuario_id] = 1
        return 1

    async def delete_fotos(self, usuario_id: str) -> int:
        self.fotos_deleted[usuario_id] = 1
        return 1

    async def anonymize_user(self, usuario_id: str) -> None:
        self.anonymized.append(usuario_id)


@dataclass
class FakeAuditor:
    calls: list[tuple[str, str, str, str]] = field(default_factory=list)

    async def log_dsr(
        self, usuario_id: str, *, actor: str, tipo: str, proposito: str
    ) -> None:
        self.calls.append((usuario_id, actor, tipo, proposito))


@dataclass
class FakeHoldHold:
    """Verifier que reporta HOLD para todas las sesiones."""

    async def verify(self, session_id: str) -> HoldDecision:
        return HoldDecision.HOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(repo: FakeUserRepo, hold_verifier=None):
    auditor = FakeAuditor()
    service = DsrService(
        repo=repo,
        hold_verifier=hold_verifier or NullHoldVerifier(),
        auditor=auditor,
    )
    return service, auditor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dsr_type_enum_tiene_cuatro_valores() -> None:
    assert DsrType.ACCESS.value == "access"
    assert DsrType.RECTIFICATION.value == "rectification"
    assert DsrType.ERASURE.value == "erasure"
    assert DsrType.PORTABILITY.value == "portability"


@pytest.mark.asyncio
async def test_access_devuelve_datos_y_audita() -> None:
    repo = FakeUserRepo(
        users={
            "u1": {
                "id": "u1",
                "id_institucional": "EST-100",
                "email": "test@frm.utn.edu.ar",
                "nombre": "Maria",
                "apellido": "Gonzalez",
                "roles": ["estudiante"],
                "eliminado_en": None,
            }
        }
    )
    service, auditor = _make_service(repo)
    response = await service.access("u1", actor="self:u1")
    assert response.usuario_id == "u1"
    assert response.email == "test@frm.utn.edu.ar"
    assert response.nombre == "Maria"
    assert response.apellido == "Gonzalez"
    assert auditor.calls == [
        ("u1", "self:u1", "access", "DSR: acceso a datos personales (Ley 25.326)")
    ]


@pytest.mark.asyncio
async def test_access_usuario_inexistente_lanza_error() -> None:
    repo = FakeUserRepo(users={})
    service, _ = _make_service(repo)
    with pytest.raises(ValueError, match="no encontrado"):
        await service.access("desconocido", actor="self:desconocido")


@pytest.mark.asyncio
async def test_rectification_actualiza_campos_audita() -> None:
    repo = FakeUserRepo(
        users={
            "u1": {
                "id": "u1",
                "id_institucional": "EST-100",
                "email": "viejo@frm.utn.edu.ar",
                "nombre": "Maria",
                "apellido": "Gonzalez",
                "roles": ["estudiante"],
                "eliminado_en": None,
            }
        }
    )
    service, auditor = _make_service(repo)
    response = await service.rectification(
        "u1", actor="self:u1", email="nuevo@frm.utn.edu.ar", nombre=None, apellido=None
    )
    assert repo.users["u1"]["email"] == "nuevo@frm.utn.edu.ar"
    assert response.email == "nuevo@frm.utn.edu.ar"
    assert repo.users["u1"]["nombre"] == "Maria"  # sin cambio
    assert auditor.calls[0][2] == "rectification"


@pytest.mark.asyncio
async def test_erasure_sin_hold_borra_todo() -> None:
    """Sin holds: borra embeddings, fotos, sesiones; anonimiza usuario; audita."""
    repo = FakeUserRepo(
        users={
            "u1": {
                "id": "u1",
                "id_institucional": "EST-100",
                "email": "borrame@frm.utn.edu.ar",
                "nombre": "Maria",
                "apellido": "Gonzalez",
                "roles": ["estudiante"],
                "eliminado_en": None,
            }
        },
        sessions_by_user={"u1": ["s1", "s2"]},
    )
    service, auditor = _make_service(repo)
    report = await service.erasure("u1", actor="self:u1")
    assert isinstance(report, DsrErasureReport)
    assert report.usuario_id == "u1"
    assert report.embeddings_deleted == 1
    assert report.fotos_deleted == 1
    assert sorted(report.sessions_deleted) == ["s1", "s2"]
    assert report.sessions_deferred == []
    assert report.anonimizado is True
    assert "u1" in repo.anonymized
    assert sorted(repo.deleted_sessions) == ["s1", "s2"]
    assert auditor.calls[-1][2] == "erasure"


@pytest.mark.asyncio
async def test_erasure_con_holds_difiere_sesiones() -> None:
    """Con verifier HOLD: NO borra sesiones (las difiere), tampoco anonimiza."""
    repo = FakeUserRepo(
        users={
            "u1": {
                "id": "u1",
                "id_institucional": "EST-100",
                "email": "x@frm.utn.edu.ar",
                "nombre": "X",
                "apellido": "Y",
                "roles": ["estudiante"],
                "eliminado_en": None,
            }
        },
        sessions_by_user={"u1": ["s1"]},
    )
    service, auditor = _make_service(repo, hold_verifier=FakeHoldHold())
    report = await service.erasure("u1", actor="self:u1")
    # Sesiones se difieren
    assert report.sessions_deleted == []
    assert report.sessions_deferred == ["s1"]
    assert repo.deleted_sessions == []
    # Como hay holds, el usuario NO se anonimiza todavia (Ley 25.326:
    # se preserva mientras haya proceso abierto)
    assert report.anonimizado is False
    assert "u1" not in repo.anonymized
    # Igual se borra biometria (egreso es independiente)
    assert report.embeddings_deleted == 1
    assert report.fotos_deleted == 1


@pytest.mark.asyncio
async def test_portability_devuelve_estructura_completa() -> None:
    """Portability incluye datos del usuario + lista de sesiones (IDs) — JSON exportable."""
    repo = FakeUserRepo(
        users={
            "u1": {
                "id": "u1",
                "id_institucional": "EST-100",
                "email": "test@frm.utn.edu.ar",
                "nombre": "Maria",
                "apellido": "Gonzalez",
                "roles": ["estudiante"],
                "eliminado_en": None,
            }
        },
        sessions_by_user={"u1": ["s-a", "s-b"]},
    )
    service, auditor = _make_service(repo)
    response = await service.portability("u1", actor="self:u1")
    assert response.usuario_id == "u1"
    assert response.email == "test@frm.utn.edu.ar"
    assert sorted(response.session_ids) == ["s-a", "s-b"]
    assert auditor.calls[-1][2] == "portability"
