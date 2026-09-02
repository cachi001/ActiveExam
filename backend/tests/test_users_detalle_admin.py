"""Tests E2E — Endpoints de detalle de usuario para admin_sistema (C-68).

Cubre:
1. GET /api/v1/users/{usuario_id}                      → detalle del usuario
2. GET /api/v1/users/{usuario_id}/consent-profile      → consentimiento vigente
3. GET /api/v1/users/{usuario_id}/biometria/referencia/estado → estado biométrico

Reglas de gobernanza:
- Solo admin_sistema puede llamar estos endpoints (403 si no).
- Biometría NUNCA incluye embedding_cifrado ni el vector (assert explícito).
- 404 si el usuario no existe.
- consent-profile devuelve 200 con nulls si no hay consentimiento (NO 404).

Sin mocks de DB — DB real del compose.
Seteá DATABASE_URL (asyncpg) para que los tests no se salten.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.domain.auth.token import TokenPolicy
from app.infrastructure.persistence.models.exam_content import ComisionModel, MateriaModel
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.transactional import (
    ConsentimientoPerfilModel,
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.consent_perfil import (
    ConsentimientoPerfilSqlRepository,
)
from app.presentation.api.v1.users.router import router as users_router

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constantes del fixture de auth
# ---------------------------------------------------------------------------

_SECRET = b"test-secret-admin-detalle-c68-long"
_ISSUER = "http://test-issuer.local"
_AUD = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _token_admin(uid: str, id_inst: str) -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": uid,
            "preferred_username": id_inst,
            "email": f"{id_inst}@test.local",
            "exp": 9999999999,
            "realm_access": {"roles": ["admin_sistema"]},
        },
        _SECRET,
    )


def _token_estudiante(uid: str, id_inst: str) -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": uid,
            "preferred_username": id_inst,
            "email": f"{id_inst}@test.local",
            "exp": 9999999999,
            "realm_access": {"roles": ["estudiante"]},
        },
        _SECRET,
    )


# ---------------------------------------------------------------------------
# Fixture principal: app + usuarios seedeados
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ctx() -> AsyncGenerator[dict, None]:
    """Levanta la app con DB real y siembra usuarios de prueba.

    Devuelve un dict con:
    - client: AsyncClient apuntando a la app.
    - admin_uid, est_uid: UUIDs de los usuarios seedeados.
    - admin_token, est_token: tokens JWT firmados con HS256.
    - engine/factory: para manipular la DB en los tests.
    """
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integración (DB real).")

    # --- motor async ---
    # NullPool: conexion fresca por checkout en el loop actual (evita el
    # "asyncpg got Future attached to a different loop" entre setup y request HTTP).
    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Asegurar que existan las tablas que tocan estos tests. La DB de test puede no
    # estar migrada al schema completo (alembic marca head pero teardowns de otros
    # tests dropean tablas). usuario primero (FK de consentimiento_perfil).
    async with engine.begin() as conn:
        await conn.run_sync(UsuarioModel.__table__.create, checkfirst=True)
        await conn.run_sync(ConsentimientoPerfilModel.__table__.create, checkfirst=True)
        await conn.run_sync(MateriaModel.__table__.create, checkfirst=True)
        await conn.run_sync(ComisionModel.__table__.create, checkfirst=True)
        await conn.run_sync(InscripcionModel.__table__.create, checkfirst=True)
        # Faltaban las dos de biometría, aunque los modelos ya se importaban acá:
        # TODA la clase TestBiometriaReferenciaEstado moría con "relation
        # foto_referencia does not exist". Es decir, el endpoint de estado
        # biométrico no tenía cobertura real, y por eso pasó inadvertido que
        # `fecha_expiracion` llegaba siempre vacía a la pantalla.
        await conn.run_sync(EmbeddingReferenciaModel.__table__.create, checkfirst=True)
        await conn.run_sync(FotoReferenciaModel.__table__.create, checkfirst=True)

    # --- seed: admin + estudiante con IDs únicos por ejecución ---
    suffix = uuid.uuid4().hex[:8]
    admin_iid = f"admin-det-{suffix}"
    est_iid = f"est-det-{suffix}"

    async with factory() as session:
        admin = UsuarioModel(
            username=admin_iid,
            email=f"{admin_iid}@test.local",
            roles=["admin_sistema"],
            auth_provider="local",
            attrs_federados={},
        )
        est = UsuarioModel(
            username=est_iid,
            email=f"{est_iid}@test.local",
            roles=["estudiante"],
            auth_provider="local",
            attrs_federados={},
            nombre="Juan",
            apellido="Perez",
        )
        session.add(admin)
        session.add(est)
        await session.commit()
        await session.refresh(admin)
        await session.refresh(est)
        admin_uid = str(admin.id)
        est_uid = str(est.id)

    # --- JWT validator HS256 ---
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app = FastAPI()
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=build_hs256_verify(_SECRET),
    )
    app.state.session_factory = factory
    app.include_router(users_router, prefix="/api/v1/users")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "factory": factory,
            "admin_uid": admin_uid,
            "est_uid": est_uid,
            "admin_iid": admin_iid,
            "est_iid": est_iid,
            "admin_token": _token_admin(admin_uid, admin_iid),
            "est_token": _token_estudiante(est_uid, est_iid),
        }

    # --- teardown: borrar usuarios seedeados ---
    from sqlalchemy import delete

    async with factory() as session:
        await session.execute(
            delete(UsuarioModel).where(
                UsuarioModel.username.in_([admin_iid, est_iid])
            )
        )
        await session.commit()

    await engine.dispose()


# ===========================================================================
# 1. GET /api/v1/users/{usuario_id}  — detalle del usuario
# ===========================================================================


class TestDetalleUsuario:
    """Endpoint 1: GET /api/v1/users/{usuario_id}."""

    async def test_admin_obtiene_detalle_200(self, ctx):
        """Admin obtiene el detalle de un usuario existente → 200 con campos correctos."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ctx["est_uid"]
        assert data["nombre"] == "Juan"
        assert data["apellido"] == "Perez"
        assert "estudiante" in data["roles"]
        assert "eliminado_en" in data  # campo presente (null o ISO)
        # Gobernanza: NUNCA devolver password_hash ni embedding
        assert "password_hash" not in data
        assert "embedding_cifrado" not in data

    async def test_estudiante_sin_inscripciones_devuelve_lista_vacia(self, ctx):
        """Estudiante sin inscripciones → inscripciones=[] (no falla, no es null)."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["inscripciones"] == []

    async def test_estudiante_con_inscripcion_devuelve_materia_y_comision(self, ctx):
        """Estudiante inscripto en una comisión → detalle incluye materia+comisión."""
        codigo_materia = f"PROG-{uuid.uuid4().hex[:8]}"
        async with ctx["factory"]() as session:
            materia = MateriaModel(codigo=codigo_materia, nombre="Programación I")
            session.add(materia)
            await session.flush()
            comision = ComisionModel(
                materia_id=materia.id,
                codigo="C1",
                nombre="Comisión 1",
                codigo_matriculacion=f"{codigo_materia}-C1",
            )
            session.add(comision)
            await session.flush()
            session.add(InscripcionModel(usuario_id=ctx["est_uid"], comision_id=comision.id))
            await session.commit()
            materia_id = materia.id

        try:
            c = ctx["client"]
            resp = await c.get(
                f"/api/v1/users/{ctx['est_uid']}",
                headers={"Authorization": f"Bearer {ctx['admin_token']}"},
            )
            assert resp.status_code == 200
            inscripciones = resp.json()["inscripciones"]
            assert len(inscripciones) == 1
            assert inscripciones[0]["materia_codigo"] == codigo_materia
            assert inscripciones[0]["materia_nombre"] == "Programación I"
            assert inscripciones[0]["comision_codigo"] == "C1"
            assert inscripciones[0]["comision_nombre"] == "Comisión 1"
        finally:
            from sqlalchemy import delete as _delete

            async with ctx["factory"]() as session:
                await session.execute(_delete(MateriaModel).where(MateriaModel.id == materia_id))
                await session.commit()

    async def test_admin_no_estudiante_no_trae_inscripciones(self, ctx):
        """Usuario sin rol estudiante → inscripciones=[] aunque tenga filas de inscripcion (no aplica)."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['admin_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["inscripciones"] == []

    async def test_403_sin_rol_admin(self, ctx):
        """Estudiante no puede ver el detalle de otro usuario → 403."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}",
            headers={"Authorization": f"Bearer {ctx['est_token']}"},
        )
        assert resp.status_code == 403

    async def test_404_usuario_inexistente(self, ctx):
        """usuario_id no existente → 404."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 404

    async def test_eliminado_en_null_para_usuario_activo(self, ctx):
        """Usuario activo devuelve eliminado_en=null (no dado de baja)."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["eliminado_en"] is None


# ===========================================================================
# 2. GET /api/v1/users/{usuario_id}/consent-profile
# ===========================================================================


class TestConsentProfile:
    """Endpoint 2: GET /api/v1/users/{usuario_id}/consent-profile."""

    async def test_sin_consentimiento_200_nulls(self, ctx):
        """Usuario sin consentimiento → 200 con todos los campos null (no 404)."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/consent-profile",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado"] is None
        assert data["version_texto"] is None
        assert data["hash_texto"] is None
        assert data["timestamp"] is None

    async def test_con_consentimiento_otorgado_200(self, ctx):
        """Usuario con consentimiento registrado → 200 con datos correctos."""
        # Seedear un consentimiento
        async with ctx["factory"]() as session:
            repo = ConsentimientoPerfilSqlRepository(session)
            await repo.registrar(
                usuario_id=ctx["est_uid"],
                version_texto="v1",
                hash_texto="abc123",
                estado="otorgado",
            )
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/consent-profile",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado"] == "otorgado"
        assert data["version_texto"] == "v1"
        assert data["hash_texto"] is not None
        assert data["timestamp"] is not None

    async def test_403_sin_rol_admin(self, ctx):
        """Estudiante no puede ver el consentimiento de otro → 403."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/consent-profile",
            headers={"Authorization": f"Bearer {ctx['est_token']}"},
        )
        assert resp.status_code == 403

    async def test_404_usuario_inexistente(self, ctx):
        """usuario_id inexistente → 404 (el usuario no existe, no el consentimiento)."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/consent-profile",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 404


# ===========================================================================
# 3. GET /api/v1/users/{usuario_id}/biometria/referencia/estado
# ===========================================================================


class TestBiometriaReferenciaEstado:
    """Endpoint 3: GET /api/v1/users/{usuario_id}/biometria/referencia/estado."""

    async def test_sin_referencia_200(self, ctx):
        """Usuario sin embedding de referencia → 200 con tiene_referencia_vigente=false."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_referencia_vigente"] is False
        assert data["algoritmo"] is None
        assert data["fecha_expiracion"] is None
        assert data["created_at"] is None
        assert data["tiene_foto"] is False
        assert data["foto_hash"] is None
        assert data["foto_created_at"] is None

    async def test_con_referencia_vigente_200(self, ctx):
        """Usuario con embedding vigente → tiene_referencia_vigente=true y metadatos."""
        # Seedear embedding (ciphertext ficticio — no se descifra, solo metadatos)
        async with ctx["factory"]() as session:
            emb = EmbeddingReferenciaModel(
                usuario_id=ctx["est_uid"],
                embedding_cifrado="gAAAAAB_FAKE_CIPHERTEXT_FOR_TEST_ONLY",
                algoritmo="face-api-128d",
                vigente=True,
            )
            session.add(emb)
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_referencia_vigente"] is True
        assert data["algoritmo"] == "face-api-128d"
        assert data["created_at"] is not None

    # -----------------------------------------------------------------------
    # Fecha de vencimiento (1/9/2026).
    #
    # El dueño vio "Fecha de vencimiento" VACIO en el detalle del usuario despues
    # de que un alumno completara consentimiento + biometria. La causa: la columna
    # `embedding_referencia.fecha_expiracion` no la escribe NADIE (queda NULL), y
    # el endpoint la leia de ahi. La vigencia real existe, pero se DERIVA de
    # `fecha_captura + BIOMETRIC_VALIDITY_MONTHS` en `_referencia_sigue_vigente`.
    #
    # O sea: la pantalla leia una columna muerta mientras la logica usaba otra
    # cosa. Ademas el texto de consentimiento que el alumno acepta promete "vale
    # 24 meses", asi que mostrar el campo en blanco contradice lo prometido.
    #
    # Se calcula en la respuesta en vez de persistir la columna: si se guardara,
    # cambiar BIOMETRIC_VALIDITY_MONTHS dejaria las filas viejas con una fecha que
    # ya no es la que usa la logica de vigencia. Una sola fuente: `fecha_captura`.
    # -----------------------------------------------------------------------

    async def test_la_fecha_de_vencimiento_viene_calculada(self, ctx):
        """Con una referencia recien capturada, el vencimiento NO puede venir vacio."""
        from datetime import UTC, datetime

        async with ctx["factory"]() as session:
            session.add(
                EmbeddingReferenciaModel(
                    usuario_id=ctx["est_uid"],
                    embedding_cifrado="gAAAAAB_FAKE_CIPHERTEXT_FOR_TEST_ONLY",
                    algoritmo="face-api-128d",
                    vigente=True,
                )
            )
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["fecha_expiracion"] is not None, "el campo llegaba vacio a la pantalla"
        # 24 meses de vigencia: la referencia capturada hoy vence dentro de 2 anios.
        assert data["fecha_expiracion"][:4] == str(datetime.now(UTC).year + 2)

    async def test_una_referencia_vieja_vence_antes(self, ctx):
        """Triangulación: el vencimiento sale de la captura, no es una constante."""
        from datetime import UTC, datetime

        async with ctx["factory"]() as session:
            emb = EmbeddingReferenciaModel(
                usuario_id=ctx["est_uid"],
                embedding_cifrado="gAAAAAB_FAKE_CIPHERTEXT_FOR_TEST_ONLY",
                algoritmo="face-api-128d",
                vigente=True,
            )
            # Capturada hace un anio: le queda uno.
            emb.fecha_captura = datetime.now(UTC).replace(
                year=datetime.now(UTC).year - 1, month=1, day=15
            )
            session.add(emb)
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )

        data = resp.json()
        assert data["fecha_expiracion"] is not None
        assert data["fecha_expiracion"][:4] == str(datetime.now(UTC).year + 1)
        assert data["fecha_expiracion"][5:7] == "01"

    async def test_biometria_nunca_expone_embedding_cifrado(self, ctx):
        """GOBERNANZA CRITICA: el JSON de biometría NUNCA contiene embedding_cifrado."""
        # Seedear embedding
        async with ctx["factory"]() as session:
            emb = EmbeddingReferenciaModel(
                usuario_id=ctx["est_uid"],
                embedding_cifrado="gAAAAAB_VERY_SECRET_EMBEDDING",
                algoritmo="face-api-128d",
                vigente=True,
            )
            session.add(emb)
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        raw = resp.text
        # Assert explícito: el ciphertext NO debe aparecer en el body
        assert "embedding_cifrado" not in raw
        assert "embedding" not in raw
        assert "VERY_SECRET_EMBEDDING" not in raw

    async def test_403_sin_rol_admin(self, ctx):
        """Estudiante no puede ver el estado biométrico de otro → 403."""
        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['est_token']}"},
        )
        assert resp.status_code == 403

    async def test_404_usuario_inexistente(self, ctx):
        """usuario_id inexistente → 404."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 404

    async def test_con_foto_vigente_200(self, ctx):
        """Usuario con foto de perfil vigente → tiene_foto=true con hash."""
        # La tabla foto_referencia en el schema activeexam usa foto_bytes (no uri_storage/bucket).
        # Sembramos via SQL crudo para no depender de qué columnas tiene el ORM vs la DB.
        from sqlalchemy import text

        async with ctx["factory"]() as session:
            await session.execute(
                text(
                    "INSERT INTO foto_referencia (usuario_id, foto_bytes, hash_sha256, vigente)"
                    " VALUES (:uid, :foto, :hash, true)"
                ),
                {
                    "uid": ctx["est_uid"],
                    "foto": b"\x89PNG\r\n",
                    "hash": "sha256fakehashfortesting",
                },
            )
            await session.commit()

        c = ctx["client"]
        resp = await c.get(
            f"/api/v1/users/{ctx['est_uid']}/biometria/referencia/estado",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_foto"] is True
        assert data["foto_hash"] == "sha256fakehashfortesting"
        assert data["foto_created_at"] is not None
