"""La baja y la degradación de una cuenta surten efecto SIN esperar al token.

Problema que resuelven estos tests: el permiso viaja dentro del access token y el
guard no consultaba la base, así que dar de baja a alguien —o quitarle un rol— no
lo sacaba: su token seguía siendo válido hasta 15 minutos. En un examen en curso
eso es una ventana durante la cual la persona sigue operando con permisos que ya
le fueron revocados.

Criterio (deliberado): solo se rechaza ante evidencia POSITIVA de revocación, o
sea cuando la fila del usuario existe y está dada de baja. Un `sub` que no
corresponde a ninguna fila NO se rechaza: el token está firmado y es válido, y no
todo emisor usa el id local como subject. Inventar un 401 ahí cerraría caminos
legítimos sin ganar seguridad.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.main import create_app
from app.presentation.api.v1.auth.dependencies import require_roles

_SECRET = b"revocacion-test-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"

_ENV: dict[str, str] = {
    "DATABASE_URL": os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://app@postgres:5432/proctoring"
    ),
    "STORAGE_ENDPOINT": "http://minio:9000",
    "STORAGE_ACCESS_KEY": "k",
    "STORAGE_SECRET_KEY": "s",
    "STORAGE_BUCKET_EVIDENCE": "evidence",
    "JWT_AUDIENCE": _AUD,
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://tempo:4317",
}


# ---------------------------------------------------------------------------
# El cache: sin él, esto sería una consulta a la base POR CADA request de cada
# alumno rindiendo. Con TTL corto la revocación tarda a lo sumo ese TTL, en vez
# de los 15 minutos del token.
# ---------------------------------------------------------------------------


class TestCacheEstadoCuenta:
    @pytest.mark.asyncio
    async def test_dentro_del_ttl_no_vuelve_a_consultar_la_base(self) -> None:
        from app.infrastructure.auth.estado_cuenta import CacheEstadoCuenta, EstadoCuenta

        reloj = {"t": 100.0}
        llamadas = {"n": 0}

        async def cargar() -> EstadoCuenta:
            llamadas["n"] += 1
            return EstadoCuenta(activa=True, roles=("admin_sistema",))

        cache = CacheEstadoCuenta(ttl_segundos=30.0, reloj=lambda: reloj["t"])

        assert await cache.obtener("u1", cargar) == EstadoCuenta(True, ("admin_sistema",))
        reloj["t"] = 129.0
        assert await cache.obtener("u1", cargar) == EstadoCuenta(True, ("admin_sistema",))
        assert llamadas["n"] == 1

    @pytest.mark.asyncio
    async def test_pasado_el_ttl_vuelve_a_consultar(self) -> None:
        from app.infrastructure.auth.estado_cuenta import CacheEstadoCuenta, EstadoCuenta

        reloj = {"t": 100.0}
        estado = {"actual": EstadoCuenta(activa=True, roles=("admin_sistema",))}

        async def cargar() -> EstadoCuenta:
            return estado["actual"]

        cache = CacheEstadoCuenta(ttl_segundos=30.0, reloj=lambda: reloj["t"])
        assert (await cache.obtener("u1", cargar)).activa is True

        # Le dan de baja en la base y pasa el TTL.
        estado["actual"] = EstadoCuenta(activa=False, roles=("admin_sistema",))
        reloj["t"] = 131.0
        assert (await cache.obtener("u1", cargar)).activa is False

    @pytest.mark.asyncio
    async def test_cada_usuario_tiene_su_propia_entrada(self) -> None:
        from app.infrastructure.auth.estado_cuenta import CacheEstadoCuenta, EstadoCuenta

        async def cargar_activo() -> EstadoCuenta:
            return EstadoCuenta(activa=True, roles=("estudiante",))

        async def cargar_de_baja() -> EstadoCuenta:
            return EstadoCuenta(activa=False, roles=("estudiante",))

        cache = CacheEstadoCuenta(ttl_segundos=30.0, reloj=lambda: 0.0)
        assert (await cache.obtener("u1", cargar_activo)).activa is True
        assert (await cache.obtener("u2", cargar_de_baja)).activa is False


# ---------------------------------------------------------------------------
# El guard, contra la base de verdad.
# ---------------------------------------------------------------------------


def _url_async() -> str:
    url = _ENV["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


async def _crear_usuario(roles: list[str], *, eliminado: bool = False) -> str:
    """Inserta un usuario real y devuelve su id."""
    from datetime import datetime, timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.infrastructure.persistence.models.transactional import UsuarioModel

    engine = create_async_engine(_url_async(), poolclass=NullPool, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    sufijo = uuid.uuid4().hex[:10]
    try:
        async with factory() as session:
            usuario = UsuarioModel(
                username=f"revoca_{sufijo}",
                email=f"revoca_{sufijo}@uni.edu",
                roles=roles,
                nombre="Revo",
                apellido="Cación",
                password_hash="x",
                auth_provider="local",
                eliminado_en=datetime.now(timezone.utc) if eliminado else None,
            )
            session.add(usuario)
            await session.commit()
            return str(usuario.id)
    finally:
        await engine.dispose()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    app = create_app(Settings())

    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )

    protegido = APIRouter()

    @protegido.get("/solo-admin")
    async def solo_admin(
        principal: AuthenticatedPrincipal = Depends(require_roles(Rol.ADMIN_SISTEMA)),
    ) -> dict:
        return {"ok": True}

    app.include_router(protegido, prefix="/api/v1/test")
    return TestClient(app)


def _token(sub: str, roles: list[str]) -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": sub,
            "preferred_username": "u1",
            "email": "u1@uni.edu",
            "exp": 9999999999,
            "amr": ["otp"],
            "realm_access": {"roles": roles},
        },
        _SECRET,
    )


@pytest.mark.requires_stack
class TestRevocacionConBaseReal:
    def test_cuenta_activa_sigue_entrando(self, client: TestClient) -> None:
        import asyncio

        uid = asyncio.run(_crear_usuario(["admin_sistema"]))
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token(uid, ['admin_sistema'])}"},
        )
        assert resp.status_code == 200

    def test_cuenta_dada_de_baja_no_entra_aunque_su_token_siga_vigente(
        self, client: TestClient
    ) -> None:
        import asyncio

        uid = asyncio.run(_crear_usuario(["admin_sistema"], eliminado=True))
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token(uid, ['admin_sistema'])}"},
        )
        assert resp.status_code == 401

    def test_rol_quitado_en_la_base_manda_sobre_el_del_token(
        self, client: TestClient
    ) -> None:
        """El token dice admin; la base ya no. Vale la base."""
        import asyncio

        uid = asyncio.run(_crear_usuario(["estudiante"]))
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token(uid, ['admin_sistema'])}"},
        )
        assert resp.status_code == 403

    def test_subject_que_no_es_una_cuenta_local_pasa_igual(
        self, client: TestClient
    ) -> None:
        """Sin fila que mirar no hay revocación que afirmar: no se inventa un 401."""
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token('s', ['admin_sistema'])}"},
        )
        assert resp.status_code == 200

    def test_fila_sin_roles_cargados_no_le_saca_los_del_token(
        self, client: TestClient
    ) -> None:
        """Roles vacíos en la base NO son una revocación: son un dato ausente.

        Vaciarle los permisos a alguien porque su fila no tiene roles cargados es
        inventar una revocación que nadie decidió. Mismo criterio que el `sub` sin
        fila: solo se actúa ante evidencia POSITIVA. Esto lo destapó la suite —
        varios módulos crean el usuario sin roles y mandan el rol en el token, y
        pasaban de 200 a 403.
        """
        import asyncio

        uid = asyncio.run(_crear_usuario([]))
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token(uid, ['admin_sistema'])}"},
        )
        assert resp.status_code == 200

    def test_la_baja_manda_aunque_no_tenga_roles_cargados(
        self, client: TestClient
    ) -> None:
        """Lo anterior no debilita la baja: esa sí es evidencia positiva."""
        import asyncio

        uid = asyncio.run(_crear_usuario([], eliminado=True))
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={"Authorization": f"Bearer {_token(uid, ['admin_sistema'])}"},
        )
        assert resp.status_code == 401

    def test_subject_uuid_inexistente_tampoco_rompe(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/test/solo-admin",
            headers={
                "Authorization": f"Bearer {_token(str(uuid.uuid4()), ['admin_sistema'])}"
            },
        )
        assert resp.status_code == 200
