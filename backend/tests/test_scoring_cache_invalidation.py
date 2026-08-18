"""Tests TDD: invalidacion de cache de ConfigService al editar evento_score_config.

TAREA 1 — BUG: PATCH /scoring/config/{tipo} no invalidaba el cache del ConfigService,
por lo que /config/effective seguia devolviendo el peso viejo.

FIX ESPERADO: el endpoint PATCH de scoring llama config_service.invalidate() despues
de commitear el cambio en evento_score_config.

DB real; si DATABASE_URL no esta seteada, se saltean.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.asyncio

_SECRET = b"scoring-cache-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


# ---------------------------------------------------------------------------
# Fixture: factory limpia (solo las tablas que necesitamos)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integracion (DB real).")

    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
        EventoScoreConfigModel,
    )

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    cfg_tbl = ConfiguracionSistemaModel.__table__
    score_tbl = EventoScoreConfigModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.run_sync(cfg_tbl.create, checkfirst=True)
        await conn.run_sync(score_tbl.create, checkfirst=True)
        # Dos tipos de evento con pesos conocidos para triangulacion.
        await conn.execute(
            text(
                "INSERT INTO evento_score_config (tipo_evento, severidad, peso, activo) "
                "VALUES ('rostro_ausente','media',20,true), "
                "('multiples_rostros','alta',50,true) "
                "ON CONFLICT (tipo_evento) DO UPDATE SET "
                "peso=EXCLUDED.peso, activo=EXCLUDED.activo, severidad=EXCLUDED.severidad"
            )
        )
        # Singleton de configuracion_sistema.
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )
    fac = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with fac() as s:
        await ConfiguracionSistemaSqlRepository(s).ensure_singleton()
        await s.commit()

    yield fac

    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.execute(
            text(
                "DELETE FROM evento_score_config WHERE tipo_evento IN "
                "('rostro_ausente','multiples_rostros')"
            )
        )
    await engine.dispose()


# ---------------------------------------------------------------------------
# Fixture: app HTTP con scoring + config routers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_client(factory) -> AsyncIterator[tuple]:
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.application.config.service import ConfigService
    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.presentation.api.v1.config.router import router as config_router
    from app.presentation.api.v1.scoring.router import router as scoring_router

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )
    app.state.session_factory = factory
    # ConfigService compartido — mismo singleton que usa el config router.
    app.state.config_service = ConfigService(factory)

    app.include_router(config_router, prefix="/api/v1/config")
    app.include_router(scoring_router, prefix="/api/v1/scoring")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app


def _token(roles) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256

    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": "s",
            "preferred_username": "admin1",
            "email": "admin1@uni.edu",
            "exp": 9999999999,
            "realm_access": {"roles": roles},
            "amr": ["otp"],
        },
        _SECRET,
    )


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# RED tests: estos FALLAN antes del fix (cache no se invalida)
# ---------------------------------------------------------------------------


async def test_patch_peso_refleja_en_effective_tipo1(app_client) -> None:
    """PATCH peso de rostro_ausente (20→28) -> GET /effective muestra 28, no 20.

    28 queda dentro del rango de severidad 'media' (11–30, migración 0021).
    """
    client, _ = app_client
    admin = _token(["admin_sistema"])

    before = await client.get("/api/v1/config/effective", headers=_h(admin))
    assert before.status_code == 200
    assert before.json()["scoring_weights"]["rostro_ausente"] == 20

    patch = await client.patch(
        "/api/v1/scoring/config/rostro_ausente",
        json={"peso": 28},
        headers=_h(admin),
    )
    assert patch.status_code == 200
    assert patch.json()["peso"] == 28

    after = await client.get("/api/v1/config/effective", headers=_h(admin))
    assert after.status_code == 200
    assert after.json()["scoring_weights"]["rostro_ausente"] == 28, (
        "BUG: cache no se invalido tras PATCH; /effective sigue devolviendo peso viejo"
    )


async def test_patch_peso_refleja_en_effective_tipo2(app_client) -> None:
    """Triangulacion: PATCH multiples_rostros (50→55) -> /effective muestra 55.

    55 queda dentro del rango de severidad 'alta' (31–60, migración 0021).
    """
    client, _ = app_client
    admin = _token(["admin_sistema"])

    patch = await client.patch(
        "/api/v1/scoring/config/multiples_rostros",
        json={"peso": 55},
        headers=_h(admin),
    )
    assert patch.status_code == 200
    assert patch.json()["peso"] == 55

    after = await client.get("/api/v1/config/effective", headers=_h(admin))
    assert after.status_code == 200
    assert after.json()["scoring_weights"]["multiples_rostros"] == 55, (
        "BUG: cache no se invalido tras PATCH de segundo tipo de evento"
    )


# ---------------------------------------------------------------------------
# Auditoria: editar un peso de scoring debe dejar rastro inmutable en audit_log
# (cadena de custodia — cambia que sesiones entran a la cola de revision).
# audit_log ya existe en la DB activeexam (migracion 0012); el test cuenta el delta.
# ---------------------------------------------------------------------------


async def _contar_config_update(factory) -> int:
    async with factory() as s:
        return (
            await s.execute(
                text("SELECT count(*) FROM audit_log WHERE accion = 'config_update'")
            )
        ).scalar_one()


async def test_patch_scoring_escribe_audit_log(app_client, factory) -> None:
    """PATCH peso de rostro_ausente escribe una fila config_update con before/after.

    28 dentro del rango de severidad 'media' (11–30, migración 0021).
    """
    client, _ = app_client
    admin = _token(["admin_sistema"])

    antes = await _contar_config_update(factory)
    patch = await client.patch(
        "/api/v1/scoring/config/rostro_ausente",
        json={"peso": 28},
        headers=_h(admin),
    )
    assert patch.status_code == 200
    despues = await _contar_config_update(factory)
    assert despues == antes + 1, "editar un peso de scoring debe dejar rastro en audit_log"

    async with factory() as s:
        accion, proposito = (
            await s.execute(
                text(
                    "SELECT accion, proposito FROM audit_log "
                    "WHERE accion = 'config_update' ORDER BY timestamp DESC, id DESC LIMIT 1"
                )
            )
        ).all()[0]
    assert accion == "config_update"
    # Snapshot before/after demostrable: peso viejo (20) y nuevo (28) en el rastro.
    assert "before" in proposito and "after" in proposito
    assert "rostro_ausente" in proposito
    assert "20" in proposito and "28" in proposito


async def test_patch_scoring_activo_escribe_audit_log(app_client, factory) -> None:
    """Triangulacion: desactivar un evento (activo=false) tambien deja rastro."""
    client, _ = app_client
    admin = _token(["admin_sistema"])

    antes = await _contar_config_update(factory)
    patch = await client.patch(
        "/api/v1/scoring/config/multiples_rostros",
        json={"activo": False},
        headers=_h(admin),
    )
    assert patch.status_code == 200
    despues = await _contar_config_update(factory)
    assert despues == antes + 1

    async with factory() as s:
        proposito = (
            await s.execute(
                text(
                    "SELECT proposito FROM audit_log WHERE accion = 'config_update' "
                    "ORDER BY timestamp DESC, id DESC LIMIT 1"
                )
            )
        ).scalar_one()
    assert "multiples_rostros" in proposito
    # before activo=true, after activo=false.
    assert "true" in proposito and "false" in proposito


# ---------------------------------------------------------------------------
# Test de capa de servicio (sin HTTP): editar via SQL directo + invalidate()
# ---------------------------------------------------------------------------


async def test_config_service_refleja_peso_nuevo_tras_invalidate(factory) -> None:
    """ConfigService.get_efectiva() refleja el peso editado en BD tras invalidate()."""
    from app.application.config.service import ConfigService

    svc = ConfigService(factory)
    efectiva = await svc.get_efectiva()
    assert efectiva.scoring_weights["rostro_ausente"] == 20

    # Edita peso directamente en BD (28 dentro del rango 'media' 11–30, migración 0021).
    async with factory() as s:
        await s.execute(
            text("UPDATE evento_score_config SET peso=28 WHERE tipo_evento='rostro_ausente'")
        )
        await s.commit()

    # Sin invalidate: cache devuelve viejo.
    aun_viejo = await svc.get_efectiva()
    assert aun_viejo.scoring_weights["rostro_ausente"] == 20, (
        "Cache no devuelve valor viejo (inesperado)"
    )

    # Tras invalidate: debe devolver nuevo.
    svc.invalidate()
    nuevo = await svc.get_efectiva()
    assert nuevo.scoring_weights["rostro_ausente"] == 28, (
        "ConfigService no reflejo el peso nuevo tras invalidate()"
    )


async def test_config_service_refleja_peso_nuevo_tipo2(factory) -> None:
    """Triangulacion de capa de servicio con multiples_rostros (50→55).

    55 dentro del rango de severidad 'alta' (31–60, migración 0021).
    """
    from app.application.config.service import ConfigService

    svc = ConfigService(factory)
    efectiva = await svc.get_efectiva()
    assert efectiva.scoring_weights["multiples_rostros"] == 50

    async with factory() as s:
        await s.execute(
            text(
                "UPDATE evento_score_config SET peso=55 WHERE tipo_evento='multiples_rostros'"
            )
        )
        await s.commit()

    svc.invalidate()
    nuevo = await svc.get_efectiva()
    assert nuevo.scoring_weights["multiples_rostros"] == 55
