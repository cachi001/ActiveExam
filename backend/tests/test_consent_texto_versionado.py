"""Tests del texto de consentimiento versionado (consent_texto_version, C-08 ext).

Cubre:
1. Seed presente: GET /consent/text sin ?version devuelve v1 con 5 bloques y hash correcto.
2. Listado de versiones: GET /consent/text/versions lista v1.
3. Crear v2: POST /consent/text/versions con contenido nuevo crea v2; listing muestra ambas.
4. 409 conflicto: POST /consent/text/versions con el mismo v2 de nuevo devuelve 409.
5. Cambiar version activa: PATCH /config con consent_version_vigente=v2 -> 200;
   luego GET /consent/text devuelve v2 (triangulado: campo version + campo hash).
6. Version invalida en config: PATCH /config con consent_version_vigente=inexistente -> 422.
7. Consulta por version: GET /consent/text?version=v1 devuelve v1;
   GET /consent/text?version=bogus devuelve 404/422.
8. Hash determinista: mismo contenido -> mismo hash; distintos bloques -> distinto hash.
9. 403 en endpoints de admin: sin admin_sistema -> 403 en POST y GET /versions.
10. Señal de re-consentimiento: alumno acepto v1; al cambiar a v2, la comparacion
    de version identifica discordancia sin tocar la tabla consentimiento_perfil.

DB real (DATABASE_URL). Sin mocks de DB. Tests listos para pytest-asyncio.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="function")

_SECRET = b"consent-texto-versionado-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_V2_BLOQUES = [
    {"titulo": "¿Qué datos recolectamos?", "cuerpo": "Datos biometricos faciales v2 (actualizado)."},
    {"titulo": "¿Cómo los recolectamos?", "cuerpo": "Mediante camara y captura de pantalla v2."},
    {"titulo": "¿Dónde se guardan?", "cuerpo": "Infraestructura self-hosted v2."},
    {"titulo": "¿Cuánto tiempo los conservamos?", "cuerpo": "Segun politica de retencion v2."},
    {"titulo": "Tus derechos", "cuerpo": "Acceso, rectificacion y supresion v2."},
]

_V2_BLOQUES_ALT = [
    {"titulo": "¿Qué datos recolectamos?", "cuerpo": "DIFERENTE contenido para triangulacion."},
    {"titulo": "¿Cómo los recolectamos?", "cuerpo": "Otro proceso de captura."},
    {"titulo": "¿Dónde se guardan?", "cuerpo": "En otro lugar."},
    {"titulo": "¿Cuánto tiempo los conservamos?", "cuerpo": "30 dias."},
    {"titulo": "Tus derechos", "cuerpo": "Derechos distintos."},
]


def _compute_hash(version: str, bloques: list[dict]) -> str:
    canonical = json.dumps(
        {
            "version": version,
            "bloques": [{"titulo": b["titulo"], "cuerpo": b["cuerpo"]} for b in bloques],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _token(roles: list[str]) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256

    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": "testuser",
            "preferred_username": "testuser",
            "email": "testuser@test.local",
            "exp": 9999999999,
            "realm_access": {"roles": roles},
        },
        _SECRET,
    )


def _h(roles: list[str]) -> dict:
    return {"Authorization": f"Bearer {_token(roles)}"}


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


# ---------------------------------------------------------------------------
# Fixture: arma una FastAPI minimal con los routers necesarios y DB real
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple]:
    """Provee (client, factory) con:
    - tabla consent_texto_version creada fresh.
    - tabla configuracion_sistema presente (singleton init en primer GET).
    - routers /api/v1/consent + /api/v1/config montados.
    """
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integracion (DB real).")

    from fastapi import FastAPI
    from sqlalchemy import text as sqla_text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage
    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
        ConsentTextoVersionModel,
    )
    from app.presentation.api.v1.consent.router import router as consent_router
    from app.presentation.api.v1.config.router import router as config_router

    class _NoOpQueue(MessageQueuePort):
        async def enqueue(self, topic: str, payload: dict) -> str:
            import uuid
            return str(uuid.uuid4())
        async def dequeue(self, topic: str) -> QueuedMessage | None:
            return None
        async def ack(self, message_id: str) -> None:
            return None
        async def health_check(self) -> bool:
            return True

    # NullPool: sin pool, cada checkout abre una conexion fresca en el loop actual.
    # Evita el "asyncpg got Future attached to a different loop" cuando el setup del
    # fixture y la request HTTP (httpx ASGITransport) corren en loops distintos.
    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)

    # Reset consent_texto_version para aislamiento de test (seed limpio de v1).
    import hashlib as _hl
    import json as _json

    _BLOQUES_V1_SEED = [
        {"titulo": "¿Qué datos recolectamos?", "cuerpo": "Se recolectan datos biometricos faciales (un embedding derivado de tu rostro), senales de tu camara y pantalla durante el examen, y metadatos de la sesion. El embedding se trata como dato sensible (Ley 25.326)."},
        {"titulo": "¿Cómo los recolectamos?", "cuerpo": "Mediante tu camara y la captura de pantalla, con analisis en tu navegador; el servidor re-procesa y firma la evidencia (cadena de custodia)."},
        {"titulo": "¿Dónde se guardan?", "cuerpo": "En infraestructura self-hosted de la institucion (soberania de datos), con la evidencia cifrada at-rest en almacenamiento WORM."},
        {"titulo": "¿Cuánto tiempo los conservamos?", "cuerpo": "Segun la politica de retencion del examen; el embedding se elimina al egreso salvo que un caso disciplinario en curso difiera la eliminacion."},
        {"titulo": "Tus derechos", "cuerpo": "Tenes derecho de acceso, rectificacion, supresion y a impugnar decisiones; la decision disciplinaria es siempre humana, el sistema no sanciona solo."},
    ]

    def _seed_hash(version: str, bloques: list) -> str:
        canonical = _json.dumps(
            {"version": version, "bloques": [{"titulo": b["titulo"], "cuerpo": b["cuerpo"]} for b in bloques]},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return _hl.sha256(canonical.encode()).hexdigest()

    _v1_hash = _seed_hash("v1", _BLOQUES_V1_SEED)
    _v1_bloques_json = _json.dumps(_BLOQUES_V1_SEED, ensure_ascii=False)
    _v1_bloques_escaped = _v1_bloques_json.replace("'", "''")

    async with engine.begin() as conn:
        # Tabla nueva: usar IF NOT EXISTS + truncate para re-runs limpios.
        await conn.execute(sqla_text(
            """
            CREATE TABLE IF NOT EXISTS consent_texto_version (
                version VARCHAR PRIMARY KEY,
                bloques JSONB NOT NULL,
                hash_texto VARCHAR NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                created_by VARCHAR
            )
            """
        ))
        await conn.execute(sqla_text("TRUNCATE TABLE consent_texto_version"))
        # Reseed v1 para que cada test empiece con v1 presente.
        await conn.execute(sqla_text(
            f"INSERT INTO consent_texto_version (version, bloques, hash_texto, created_by) "
            f"VALUES ('v1', '{_v1_bloques_escaped}'::jsonb, '{_v1_hash}', 'test-fixture') "
            f"ON CONFLICT (version) DO NOTHING"
        ))

    # configuracion_sistema: drop+create para reset limpio
    cfg_tbl = ConfiguracionSistemaModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.run_sync(cfg_tbl.create, checkfirst=True)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )
    app.state.session_factory = factory
    app.state.message_queue = _NoOpQueue()
    app.include_router(consent_router, prefix="/api/v1/consent")
    app.include_router(config_router, prefix="/api/v1/config")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(sqla_text("TRUNCATE TABLE consent_texto_version"))
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
    await engine.dispose()


# ===========================================================================
# TEST 1 — Seed presente: v1 con 5 bloques y hash correcto
# ===========================================================================


async def test_seed_v1_presente_5_bloques(ctx) -> None:
    """GET /consent/text sin ?version devuelve v1 con 5 bloques y hash correcto (TDD RED)."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text", headers=_h(["estudiante"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v1"
    assert isinstance(body["bloques"], list)
    assert len(body["bloques"]) == 5
    assert "hash_texto" in body
    # Cada bloque tiene titulo y cuerpo
    for bloque in body["bloques"]:
        assert "titulo" in bloque
        assert "cuerpo" in bloque


async def test_seed_v1_hash_correcto(ctx) -> None:
    """El hash de v1 coincide con el hash canonico computado localmente (triangulacion)."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text", headers=_h(["estudiante"]))
    body = resp.json()
    assert body["version"] == "v1"
    expected_hash = _compute_hash("v1", body["bloques"])
    assert body["hash_texto"] == expected_hash


# ===========================================================================
# TEST 2 — Listado de versiones: GET /consent/text/versions lista v1
# ===========================================================================


async def test_list_versions_contiene_v1(ctx) -> None:
    """GET /consent/text/versions devuelve lista con v1 (admin requerido)."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text/versions", headers=_h(["admin_sistema"]))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    versions = [item["version"] for item in body]
    assert "v1" in versions


async def test_list_versions_tiene_hash_y_created_at(ctx) -> None:
    """Cada item del listing tiene version, hash_texto y created_at (triangulacion)."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text/versions", headers=_h(["admin_sistema"]))
    body = resp.json()
    for item in body:
        assert "version" in item
        assert "hash_texto" in item
        assert "created_at" in item


# ===========================================================================
# TEST 3 — Crear v2: POST /consent/text/versions + listing muestra ambas
# ===========================================================================


async def test_crear_v2_exitoso(ctx) -> None:
    """POST /consent/text/versions con v2 nuevo devuelve 201."""
    client, _ = ctx
    resp = await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == "v2"
    assert len(body["bloques"]) == 5
    assert "hash_texto" in body
    assert body["hash_texto"] == _compute_hash("v2", _V2_BLOQUES)


async def test_listing_muestra_v1_y_v2(ctx) -> None:
    """Luego de crear v2, el listing incluye v1 y v2 (triangulacion)."""
    client, _ = ctx
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    resp = await client.get("/api/v1/consent/text/versions", headers=_h(["admin_sistema"]))
    body = resp.json()
    versions = {item["version"] for item in body}
    assert "v1" in versions
    assert "v2" in versions


# ===========================================================================
# TEST 4 — 409 conflicto: segunda creacion del mismo v2
# ===========================================================================


async def test_crear_v2_duplicado_409(ctx) -> None:
    """POST con mismo version de nuevo devuelve 409."""
    client, _ = ctx
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    resp = await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 409


async def test_crear_v2_duplicado_contenido_diferente_sigue_409(ctx) -> None:
    """409 incluso si el contenido cambia: version es la PK, texto nunca muta (triangulacion)."""
    client, _ = ctx
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    resp = await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES_ALT},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 409


# ===========================================================================
# TEST 5 — Cambiar version activa: PATCH /config y luego GET /consent/text
# ===========================================================================


async def test_cambiar_version_activa_a_v2(ctx) -> None:
    """PATCH /config con consent_version_vigente=v2 devuelve 200."""
    client, _ = ctx
    # Crear v2 primero
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    resp = await client.patch(
        "/api/v1/config",
        json={"consent_version_vigente": "v2"},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 200
    assert resp.json()["consent_version_vigente"] == "v2"


async def test_get_text_devuelve_v2_tras_switch(ctx) -> None:
    """Tras PATCH /config a v2, GET /consent/text devuelve v2 (triangulacion: version + hash)."""
    client, _ = ctx
    # Crear v2
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    # Cambiar config
    await client.patch(
        "/api/v1/config",
        json={"consent_version_vigente": "v2"},
        headers=_h(["admin_sistema"]),
    )
    # Leer texto — debe ser v2
    resp = await client.get("/api/v1/consent/text", headers=_h(["estudiante"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v2"
    # Triangulacion: hash correcto para v2
    assert body["hash_texto"] == _compute_hash("v2", _V2_BLOQUES)


# ===========================================================================
# TEST 6 — Version invalida en config → 422
# ===========================================================================


async def test_config_version_inexistente_422(ctx) -> None:
    """PATCH /config con consent_version_vigente=nonexistent devuelve 422."""
    client, _ = ctx
    resp = await client.patch(
        "/api/v1/config",
        json={"consent_version_vigente": "version-que-no-existe"},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 422


async def test_config_version_invalida_no_persiste(ctx) -> None:
    """Tras el 422, la version vigente sigue siendo v1 (triangulacion)."""
    client, _ = ctx
    # Intento fallido
    await client.patch(
        "/api/v1/config",
        json={"consent_version_vigente": "no-existe"},
        headers=_h(["admin_sistema"]),
    )
    # La config no cambio
    resp = await client.get("/api/v1/config/effective", headers=_h(["admin_sistema"]))
    assert resp.json()["consent_version_vigente"] == "v1"


# ===========================================================================
# TEST 7 — Consulta por version: ?version=v1 y ?version=bogus
# ===========================================================================


async def test_get_text_by_version_v1(ctx) -> None:
    """GET /consent/text?version=v1 devuelve v1 correctamente."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text?version=v1", headers=_h(["estudiante"]))
    assert resp.status_code == 200
    assert resp.json()["version"] == "v1"


async def test_get_text_by_version_bogus_404(ctx) -> None:
    """GET /consent/text?version=bogus devuelve 404 o 422."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text?version=bogus-xyz", headers=_h(["estudiante"]))
    assert resp.status_code in (404, 422)


# ===========================================================================
# TEST 8 — Hash determinista
# ===========================================================================


def test_hash_determinista_mismo_contenido() -> None:
    """Mismo contenido -> mismo hash (sin DB)."""
    h1 = _compute_hash("v1", _V2_BLOQUES)
    h2 = _compute_hash("v1", _V2_BLOQUES)
    assert h1 == h2


def test_hash_determinista_diferente_contenido() -> None:
    """Distintos bloques -> distinto hash (triangulacion, sin DB)."""
    h1 = _compute_hash("v1", _V2_BLOQUES)
    h2 = _compute_hash("v1", _V2_BLOQUES_ALT)
    assert h1 != h2


def test_hash_determinista_diferente_version() -> None:
    """Mismos bloques pero distinta version -> distinto hash (triangulacion)."""
    h1 = _compute_hash("v1", _V2_BLOQUES)
    h2 = _compute_hash("v2", _V2_BLOQUES)
    assert h1 != h2


# ===========================================================================
# TEST 9 — 403 en endpoints de admin sin rol admin_sistema
# ===========================================================================


async def test_get_versions_sin_admin_403(ctx) -> None:
    """GET /consent/text/versions sin admin_sistema devuelve 403."""
    client, _ = ctx
    resp = await client.get(
        "/api/v1/consent/text/versions", headers=_h(["estudiante"])
    )
    assert resp.status_code == 403


async def test_post_versions_sin_admin_403(ctx) -> None:
    """POST /consent/text/versions sin admin_sistema devuelve 403."""
    client, _ = ctx
    resp = await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v99", "bloques": _V2_BLOQUES},
        headers=_h(["estudiante"]),
    )
    assert resp.status_code == 403


async def test_get_versions_sin_token_401(ctx) -> None:
    """GET /consent/text/versions sin token devuelve 401 (triangulacion)."""
    client, _ = ctx
    resp = await client.get("/api/v1/consent/text/versions")
    assert resp.status_code == 401


# ===========================================================================
# TEST 10 — Señal de re-consentimiento
# ===========================================================================


async def test_reconsentimiento_version_mismatch(ctx) -> None:
    """
    Alumno acepto v1; config cambia a v2; la comparacion de versiones detecta
    discordancia. No toca la tabla consentimiento_perfil: solo compara strings.
    """
    client, _ = ctx

    # Crear v2
    await client.post(
        "/api/v1/consent/text/versions",
        json={"version": "v2", "bloques": _V2_BLOQUES},
        headers=_h(["admin_sistema"]),
    )
    # Cambiar version vigente a v2
    await client.patch(
        "/api/v1/config",
        json={"consent_version_vigente": "v2"},
        headers=_h(["admin_sistema"]),
    )

    # Obtener la version vigente actual de la config
    cfg_resp = await client.get("/api/v1/config/effective", headers=_h(["estudiante"]))
    version_vigente = cfg_resp.json()["consent_version_vigente"]

    # Simular que el alumno acepto v1
    version_aceptada_por_alumno = "v1"

    # La señal de re-consentimiento: versiones distintas
    assert version_vigente != version_aceptada_por_alumno
    assert version_vigente == "v2"


async def test_reconsentimiento_no_requerido_version_igual(ctx) -> None:
    """Alumno acepto la version vigente: no hay discordancia (triangulacion)."""
    client, _ = ctx

    # La version vigente es v1 (default)
    cfg_resp = await client.get("/api/v1/config/effective", headers=_h(["estudiante"]))
    version_vigente = cfg_resp.json()["consent_version_vigente"]

    # Alumno acepto v1 (la vigente)
    version_aceptada_por_alumno = "v1"

    # No hay discordancia
    assert version_vigente == version_aceptada_por_alumno
