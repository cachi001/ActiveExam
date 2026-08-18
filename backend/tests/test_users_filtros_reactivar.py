"""Tests E2E — Filtros de listado + endpoint reactivar usuario (C-67 / admin).

Cubre:
1. GET /api/v1/users/?rol=...         — filtro por rol exacto
2. GET /api/v1/users/?estado=...      — filtro por estado (activo/inactivo/todos)
3. GET /api/v1/users/?q=...           — búsqueda ILIKE por nombre/apellido/email
4. POST /api/v1/users/{id}/reactivar  — reactivar usuario dado de baja
5. DELETE /api/v1/users/{id}          — protección self-delete (409)

Sin mocks de DB — DB real del compose.
Seteá DATABASE_URL (asyncpg) para que los tests no se salten.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.infrastructure.persistence.models.exam_content import ComisionModel, MateriaModel
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.users.router import router as users_router

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constantes del fixture de auth
# ---------------------------------------------------------------------------

_SECRET = b"test-secret-filtros-reactivar-long"
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
    - factory: async_sessionmaker para manipular la DB en los tests.
    - suffix: sufijo único para nombres de esta ejecución.
    """
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integración (DB real).")

    # --- motor async ---
    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # --- seed: admin + estudiante con IDs únicos por ejecución ---
    suffix = uuid.uuid4().hex[:8]
    admin_iid = f"admin-flt-{suffix}"
    est_iid = f"est-flt-{suffix}"

    async with factory() as session:
        admin = UsuarioModel(
            username=admin_iid,
            email=f"{admin_iid}@test.local",
            roles=["admin_sistema"],
            auth_provider="local",
            attrs_federados={},
            nombre="AdminNombre",
            apellido="AdminApellido",
        )
        est = UsuarioModel(
            username=est_iid,
            email=f"{est_iid}@test.local",
            roles=["estudiante"],
            auth_provider="local",
            attrs_federados={},
            nombre="EstNombre",
            apellido="EstApellido",
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
            "suffix": suffix,
            "admin_token": _token_admin(admin_uid, admin_iid),
            "est_token": _token_estudiante(est_uid, est_iid),
        }

    # --- teardown: borrar usuarios seedeados (including soft-deleted ones) ---
    async with factory() as session:
        await session.execute(
            delete(UsuarioModel).where(
                UsuarioModel.username.in_([admin_iid, est_iid])
            )
        )
        await session.commit()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Helper: soft-delete directo via SQL (igual al router)
# ---------------------------------------------------------------------------


async def _soft_delete(factory, uid: str) -> None:
    """Soft-delete de un usuario via SQL directo (mismo patrón que el router)."""
    async with factory() as session:
        await session.execute(
            text("UPDATE usuario SET eliminado_en = :ahora WHERE id = :id"),
            {"ahora": datetime.now(UTC), "id": uid},
        )
        await session.commit()


# ===========================================================================
# 1. TestFiltroRol
# ===========================================================================


class TestFiltroRol:
    """GET /api/v1/users/?rol=<rol> filtra por rol exacto."""

    async def test_filtro_rol_devuelve_solo_ese_rol(self, ctx):
        """Seed admin+estudiante; filter rol=estudiante → solo el estudiante aparece."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/",
            params={"rol": "estudiante", "estado": "todos"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["est_uid"] in ids
        assert ctx["admin_uid"] not in ids
        # Todos los items tienen rol estudiante
        for item in data["items"]:
            assert "estudiante" in item["roles"]


# ===========================================================================
# 1b. TestFiltroMateriaComision
# ===========================================================================


class TestFiltroMateriaComision:
    """GET /api/v1/users/?comision_id=... / ?materia_id=... filtra por inscripción."""

    async def test_filtro_comision_id_devuelve_solo_inscriptos(self, ctx):
        """Dos estudiantes, solo uno inscripto en la comisión → filtro devuelve solo ese."""
        c = ctx["client"]
        factory = ctx["factory"]
        suffix = ctx["suffix"]

        async with factory() as session:
            otro_est = UsuarioModel(
                username=f"est2-flt-{suffix}",
                email=f"est2-flt-{suffix}@test.local",
                roles=["estudiante"],
                auth_provider="local",
                attrs_federados={},
            )
            session.add(otro_est)
            materia = MateriaModel(codigo=f"MAT-{suffix}", nombre="Materia Test")
            session.add(materia)
            await session.flush()
            comision = ComisionModel(
                materia_id=materia.id,
                codigo="C1",
                nombre="Comisión Test",
                codigo_matriculacion=f"MAT-{suffix}-C1",
            )
            session.add(comision)
            await session.flush()
            session.add(InscripcionModel(usuario_id=ctx["est_uid"], comision_id=comision.id))
            await session.commit()
            comision_id = comision.id
            materia_id = materia.id
            otro_est_uid = str(otro_est.id)

        try:
            resp = await c.get(
                "/api/v1/users/",
                params={"rol": "estudiante", "estado": "todos", "comision_id": comision_id},
                headers={"Authorization": f"Bearer {ctx['admin_token']}"},
            )
            assert resp.status_code == 200
            ids = [item["id"] for item in resp.json()["items"]]
            assert ctx["est_uid"] in ids
            assert otro_est_uid not in ids

            resp_materia = await c.get(
                "/api/v1/users/",
                params={"rol": "estudiante", "estado": "todos", "materia_id": materia_id},
                headers={"Authorization": f"Bearer {ctx['admin_token']}"},
            )
            assert resp_materia.status_code == 200
            ids_materia = [item["id"] for item in resp_materia.json()["items"]]
            assert ctx["est_uid"] in ids_materia

            # El item incluye la inscripción (materia + comisión) para pintar la columna.
            item = next(i for i in resp.json()["items"] if i["id"] == ctx["est_uid"])
            assert len(item["inscripciones"]) == 1
            assert item["inscripciones"][0]["comision_id"] == comision_id
        finally:
            async with factory() as session:
                await session.execute(delete(MateriaModel).where(MateriaModel.id == materia_id))
                await session.execute(
                    delete(UsuarioModel).where(UsuarioModel.id == otro_est_uid)
                )
                await session.commit()

    async def test_filtro_rol_vacio_si_no_hay(self, ctx):
        """Filtro por rol sin coincidencias → lista vacía (o sin nuestros seeds).

        c-76: se usa 'coordinador' (rol vivo) en vez del eliminado 'proctor';
        ninguno de los seeds (estudiante/admin) lo tiene, así que sigue vacío."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/",
            params={"rol": "coordinador", "estado": "todos"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Ninguno de nuestros usuarios seeded debe aparecer
        ids = [item["id"] for item in data["items"]]
        assert ctx["est_uid"] not in ids
        assert ctx["admin_uid"] not in ids


# ===========================================================================
# 2. TestFiltroEstado
# ===========================================================================


class TestFiltroEstado:
    """GET /api/v1/users/?estado=... filtra por estado activo/inactivo/todos."""

    async def test_estado_inactivo_solo_dados_de_baja(self, ctx):
        """Soft-delete del estudiante → estado=inactivo devuelve solo ese usuario."""
        await _soft_delete(ctx["factory"], ctx["est_uid"])

        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/",
            params={"estado": "inactivo"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["est_uid"] in ids
        # El admin (activo) NO debe aparecer en inactivos
        assert ctx["admin_uid"] not in ids
        # El eliminado_en debe estar presente (no null)
        est_items = [item for item in data["items"] if item["id"] == ctx["est_uid"]]
        assert len(est_items) == 1
        assert est_items[0]["eliminado_en"] is not None

    async def test_estado_todos_incluye_ambos(self, ctx):
        """Seed activo + soft-deleted → estado=todos devuelve ambos."""
        await _soft_delete(ctx["factory"], ctx["est_uid"])

        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/",
            params={"estado": "todos"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["est_uid"] in ids
        assert ctx["admin_uid"] in ids

    async def test_estado_default_solo_activos(self, ctx):
        """Sin param estado (default=activo) → solo activos; inactivos excluidos."""
        await _soft_delete(ctx["factory"], ctx["est_uid"])

        c = ctx["client"]
        # Sin pasar ?estado= → usa default "activo"
        resp = await c.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["admin_uid"] in ids
        assert ctx["est_uid"] not in ids


# ===========================================================================
# 3. TestFiltroQ
# ===========================================================================


class TestFiltroQ:
    """GET /api/v1/users/?q=... búsqueda ILIKE por nombre/apellido/email/username."""

    async def test_q_matchea_por_nombre(self, ctx):
        """ILIKE search en nombre → devuelve el usuario correcto."""
        c = ctx["client"]
        # El estudiante tiene nombre="EstNombre"
        resp = await c.get(
            "/api/v1/users/",
            params={"q": "estnombre", "estado": "activo"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["est_uid"] in ids
        # El admin (nombre=AdminNombre) NO debe aparecer
        assert ctx["admin_uid"] not in ids

    async def test_q_matchea_por_email(self, ctx):
        """ILIKE search en email, case-insensitive → devuelve el usuario correcto."""
        c = ctx["client"]
        # El admin tiene email admin-flt-<suffix>@test.local
        query = ctx["admin_iid"].upper()  # MAYÚSCULAS para verificar case-insensitive
        resp = await c.get(
            "/api/v1/users/",
            params={"q": query, "estado": "activo"},
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ctx["admin_uid"] in ids
        assert ctx["est_uid"] not in ids


# ===========================================================================
# 4. TestReactivar
# ===========================================================================


class TestReactivar:
    """POST /api/v1/users/{usuario_id}/reactivar — solo admin_sistema."""

    async def test_reactivar_usuario_dado_de_baja(self, ctx):
        """DELETE user → POST reactivar → 200, eliminado_en is None."""
        # Primero soft-delete via la API
        c = ctx["client"]
        del_resp = await c.delete(
            f"/api/v1/users/{ctx['est_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert del_resp.status_code == 204

        # Reactivar
        resp = await c.post(
            f"/api/v1/users/{ctx['est_uid']}/reactivar",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ctx["est_uid"]
        assert data["eliminado_en"] is None

    async def test_reactivar_404_inexistente(self, ctx):
        """Reactivar UUID que no existe → 404."""
        c = ctx["client"]
        resp = await c.post(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/reactivar",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 404

    async def test_reactivar_409_ya_activo(self, ctx):
        """Reactivar usuario ya activo (no dado de baja) → 409."""
        c = ctx["client"]
        resp = await c.post(
            f"/api/v1/users/{ctx['est_uid']}/reactivar",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 409

    async def test_reactivar_409_si_mismo(self, ctx):
        """Admin intenta reactivarse a sí mismo → 409."""
        # Primero soft-delete directo para dejarlo inactivo
        await _soft_delete(ctx["factory"], ctx["admin_uid"])

        c = ctx["client"]
        resp = await c.post(
            f"/api/v1/users/{ctx['admin_uid']}/reactivar",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 409


# ===========================================================================
# 5. TestDeletePropia
# ===========================================================================


class TestDeletePropia:
    """DELETE /api/v1/users/{id} — protección self-delete."""

    async def test_delete_si_mismo_409(self, ctx):
        """Admin intenta darse de baja a sí mismo → 409."""
        c = ctx["client"]
        resp = await c.delete(
            f"/api/v1/users/{ctx['admin_uid']}",
            headers={"Authorization": f"Bearer {ctx['admin_token']}"},
        )
        assert resp.status_code == 409


# ===========================================================================
# 6. TestForbiddenSinAdmin
# ===========================================================================


class TestForbiddenSinAdmin:
    """Endpoints de admin solo accesibles con rol admin_sistema."""

    async def test_403_filtros_sin_admin(self, ctx):
        """Estudiante llama GET /api/v1/users/ → 403."""
        c = ctx["client"]
        resp = await c.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {ctx['est_token']}"},
        )
        assert resp.status_code == 403

    async def test_403_reactivar_sin_admin(self, ctx):
        """Estudiante llama POST reactivar → 403."""
        c = ctx["client"]
        resp = await c.post(
            f"/api/v1/users/{ctx['est_uid']}/reactivar",
            headers={"Authorization": f"Bearer {ctx['est_token']}"},
        )
        assert resp.status_code == 403
