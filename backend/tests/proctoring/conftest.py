"""Fixtures compartidas para los tests del modulo activeexam de proctoring.

Los tests de integracion (requires_db_real) usan Postgres real/efimero.
Sin mocks de DB (regla dura de codigo: mockear la DB invalida el test).

Para correr los tests de integracion:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/ -v

Los tests unitarios (scoring, integridad, reinferencia sin DB) corren sin env vars.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.models.proctoring import (  # noqa: F401 -- registra tablas
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.chat_pausa import (  # noqa: F401 -- registra tablas (C-15 6.x)
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.observacion import (  # noqa: F401 -- registra tabla (C-15 3.2)
    ObservacionTutorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401 -- registra tabla (C-69)
    ExamenContenidoModel,
)
from app.infrastructure.persistence.base import Base


def _get_test_db_url() -> str | None:
    """Devuelve DATABASE_URL del entorno para tests (None si no esta seteada)."""
    return os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _get_test_db_url()
    if not url:
        pytest.skip(
            "DATABASE_URL no esta seteada. "
            "Para tests de integracion: DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/"
        )
    return url


_ACTIVEEXAM_TABLE_NAMES = (
    "observacion_tutor",
    "mensaje_chat",
    "pausa_autorizada",
    "proctoring_biometria",
    "proctoring_event",
    "proctoring_session",
    # C-69: contenido de examen — vinculado por proctoring_session.examen_contenido_id
    # (FK ON DELETE SET NULL, migracion activeexam 0027). Se crea ANTES de proctoring_session
    # (ver activeexam_tables abajo) para que el FK resuelva; CASCADE cubre el orden de drop.
    "examen_contenido",
)


@pytest_asyncio.fixture(scope="session")
async def activeexam_engine(db_url: str):
    """Engine async para los tests — usa Postgres real.

    Setup/teardown usan ``DROP TABLE ... CASCADE`` via SQL crudo: el ``table.drop``
    de SQLAlchemy emite ``DROP TABLE`` sin CASCADE, y falla si quedan vistas,
    triggers o referencias previas (cualquier estado sucio de una corrida anterior
    deja los tests rojos al iniciar).
    """
    engine = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    from app.infrastructure.persistence.models.proctoring import (  # noqa
        ProctoringBiometriaModel,
        ProctoringEventModel,
        ProctoringSessionModel,
    )
    from app.infrastructure.persistence.models.chat_pausa import (  # noqa
        MensajeChatModel,
        PausaAutorizadaModel,
    )
    from app.infrastructure.persistence.models.observacion import (  # noqa
        ObservacionTutorModel,
    )
    from app.infrastructure.persistence.models.exam_content import (  # noqa
        ExamenContenidoModel,
    )
    activeexam_tables = [
        # examen_contenido PRIMERO: proctoring_session tiene un FK hacia ella (C-69).
        ExamenContenidoModel.__table__,
        ProctoringSessionModel.__table__,
        ProctoringEventModel.__table__,
        ProctoringBiometriaModel.__table__,
        MensajeChatModel.__table__,
        PausaAutorizadaModel.__table__,
        ObservacionTutorModel.__table__,
    ]
    async with engine.begin() as conn:
        # Limpieza previa robusta (CASCADE) — tolera estado sucio de corridas previas.
        for name in _ACTIVEEXAM_TABLE_NAMES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        for table in activeexam_tables:
            await conn.run_sync(table.create, checkfirst=True)
    yield engine
    # Teardown final: idem, CASCADE para no dejar restos.
    async with engine.begin() as conn:
        for name in _ACTIVEEXAM_TABLE_NAMES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _limpiar_tablas_activeexam(engine) -> None:
    """Resetea las tablas activeexam. Usa TRUNCATE ... CASCADE (rapido y respeta FKs)."""
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{n}"' for n in _ACTIVEEXAM_TABLE_NAMES)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def db_session(activeexam_engine) -> AsyncIterator[AsyncSession]:
    """Sesion de DB para cada test — rollback al finalizar para aislar tests."""
    factory = async_sessionmaker(activeexam_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Auth de test: JwtValidator HS256 (stdlib, sin red) + emisor de tokens por rol.
#
# Los endpoints de proctoring activeexam quedan endurecidos por rol (auth/RBAC). Para
# testearlos sin levantar Keycloak ni el stack completo, cableamos un
# ``JwtValidator`` HS256-only en ``app.state.jwt_validator`` (mismo mecanismo que
# produccion lee en ``get_current_principal``) y emitimos tokens firmados con el
# mismo secreto via ``encode_hs256`` (helper de test del repo).
# ---------------------------------------------------------------------------

_TEST_JWT_SECRET = b"proctoring-activeexam-test-secret"
_TEST_JWT_ISSUER = "activeexam-auth"
_TEST_JWT_AUDIENCE = "proctoring-api"

#: `sub` por defecto de los tokens de test. Es un UUID real porque el dominio lo
#: usa como usuario_id contra la base: con un literal suelto, las consultas de
#: perfil y de pertenencia fallan con 500 en vez de responder lo que corresponde.
ALUMNO_DE_TEST = "11111111-1111-4111-8111-111111111111"


def token_for(
    roles: list[str],
    *,
    mfa: bool = True,
    username: str | None = None,
    email: str = "test@uni.edu",
    subject: str = ALUMNO_DE_TEST,
) -> str:
    """Emite un JWT HS256 de test con los roles dados (claims shape Keycloak).

    ``mfa=True`` agrega ``amr=['otp']`` para satisfacer el segundo factor de los
    roles que lo exigen; los endpoints de proctoring activeexam solo chequean rol (no
    MFA), pero lo incluimos por defecto para no acoplar el test a esa decision.

    ``username`` overridea el ``preferred_username`` (del que el dominio deriva
    ``username``); ``email`` overridea el email. Por defecto coinciden con
    el alumno historico ("estudiante"/"test@uni.edu"). Sirven para emitir tokens
    de DOS alumnos distintos en los tests de propiedad de sesion (IDOR).
    """
    from app.infrastructure.auth.verifiers import encode_hs256

    claims: dict = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": subject,
        "preferred_username": username or ("+".join(roles) or "anon"),
        "email": email,
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }
    if mfa:
        claims["amr"] = ["otp"]
    return encode_hs256(claims, _TEST_JWT_SECRET)


def auth_headers(
    roles: list[str],
    *,
    mfa: bool = True,
    username: str | None = None,
    email: str = "test@uni.edu",
    subject: str = ALUMNO_DE_TEST,
) -> dict[str, str]:
    """Header Authorization Bearer con un token de test para los roles dados.

    ``subject`` fija el claim ``sub``, del que el dominio deriva
    ``principal.subject`` = id del usuario. Necesario para los tests de PERTENENCIA
    (C-73 §9): dos docentes distintos son dos ``sub`` distintos."""
    return {
        "Authorization": (
            f"Bearer {token_for(roles, mfa=mfa, username=username, email=email, subject=subject)}"
        )
    }


def _build_test_jwt_validator():
    """JwtValidator HS256-only para los tests (stdlib, sin PyJWT ni red)."""
    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify

    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({_TEST_JWT_ISSUER}),
        audience=_TEST_JWT_AUDIENCE,
    )
    return JwtValidator(
        jwks_cache=cache,
        policy=policy,
        verify_fn=build_hs256_verify(_TEST_JWT_SECRET),
    )


@pytest.fixture(scope="session")
def activeexam_reinferencia():
    """Una UNICA instancia de MediaPipeReinferencia para toda la sesion de tests.

    Espeja produccion (uvicorn crea el adapter una sola vez al arranque, vive para
    siempre). Crear uno NUEVO por test hace que el FaceDetector real de MediaPipe
    quede sin referencias y el GC dispare su ``__del__`` → ``close()``, que delega
    en un *serial dispatcher* ya finalizado y se cuelga eternamente en
    ``executor.submit(...).result()``. Reusar una sola instancia evita ese deadlock.
    """
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    return MediaPipeReinferencia()


@pytest.fixture
def activeexam_app(activeexam_engine, activeexam_reinferencia):
    """App activeexam instanciada con el engine de test.

    Cablea ``app.state.jwt_validator`` (HS256 de test) para que los guards de rol
    de los endpoints de proctoring activeexam resuelvan el principal igual que en prod.
    """
    from app.infrastructure.persistence.session_activeexam import create_activeexam_session_factory
    from app.presentation.api.v1.proctoring.router import create_proctoring_router
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    factory = create_activeexam_session_factory(activeexam_engine)
    reinferencia = activeexam_reinferencia
    proctoring_router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
    )
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")
    return app


@pytest_asyncio.fixture
async def client(activeexam_app, activeexam_engine) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP async AUTENTICADO COMO ESTUDIANTE para tests del flujo del alumno.

    El alumno usa los endpoints compartidos (crear sesion, eventos, chat, pausas,
    finalizar). Inyecta por defecto un Bearer de rol ``estudiante`` para que el
    flujo del alumno siga verde tras el endurecimiento por rol. Los tests de
    guards (proctor/admin/401) usan ``client_noauth`` + ``auth_headers(...)``.

    Limpia las tablas activeexam ANTES de cada test para aislar estado entre tests."""
    await _limpiar_tablas_activeexam(activeexam_engine)
    async with AsyncClient(
        transport=ASGITransport(app=activeexam_app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def client_noauth(activeexam_app, activeexam_engine) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP async SIN auth por defecto (para tests de 401/403 y roles).

    Igual que ``client`` pero sin Authorization header preinyectado: cada test
    decide que token mandar (o ninguno) via ``auth_headers(...)``."""
    await _limpiar_tablas_activeexam(activeexam_engine)
    async with AsyncClient(
        transport=ASGITransport(app=activeexam_app), base_url="http://test"
    ) as c:
        yield c


async def dar_perfil_completo(db, usuario_id: str = ALUMNO_DE_TEST) -> None:
    """Deja al alumno en condiciones de rendir: consentimiento + biometria + foto.

    El gate de perfil (`domain/exam_content/perfil_para_rendir`) es server-side y
    corre al crear la sesion de un examen. Los tests que ejercitan el flujo del
    alumno tienen que pasar por ahi como pasa un alumno de verdad: sembrando el
    perfil, no salteando la regla.

    El `usuario_id` por defecto es el `sub` que inyecta `auth_headers`.
    """
    from sqlalchemy import text as _text

    from app.infrastructure.persistence.base import Base
    from app.infrastructure.persistence.models.transactional import (
        ConsentimientoPerfilModel,
        EmbeddingReferenciaModel,
        FotoReferenciaModel,
        UsuarioModel,
    )

    # Cada modulo de tests crea solo las tablas que usa, y estas son nuevas para
    # los del flujo del alumno: se crean si faltan en vez de exigirle a cada
    # fixture que se acuerde de listarlas.
    await db.run_sync(
        lambda sync: Base.metadata.create_all(
            sync.get_bind(),
            tables=[
                UsuarioModel.__table__,
                ConsentimientoPerfilModel.__table__,
                EmbeddingReferenciaModel.__table__,
                FotoReferenciaModel.__table__,
            ],
            checkfirst=True,
        )
    )

    await db.execute(
        _text(
            "INSERT INTO usuario (id, username, email, nombre, apellido,"
            " password_hash, roles)"
            " VALUES (:id, :u, :e, 'Test', 'Alumno', 'x', '[\"estudiante\"]'::jsonb)"
            " ON CONFLICT (id) DO NOTHING"
        ),
        {"id": usuario_id, "u": f"alumno-{usuario_id[:8]}", "e": f"{usuario_id[:8]}@test.local"},
    )
    # Idempotente: varios tests del mismo modulo llaman a esto y las tablas de
    # perfil no se limpian entre ellos. Sin el borrado previo quedan dos filas
    # vigentes y el repositorio, que espera una sola, revienta.
    for tabla in ("consentimiento_perfil", "embedding_referencia", "foto_referencia"):
        await db.execute(
            _text(f"DELETE FROM {tabla} WHERE usuario_id = :u"), {"u": usuario_id}
        )

    await db.execute(
        _text(
            "INSERT INTO consentimiento_perfil"
            " (usuario_id, version_texto, hash_texto, estado, hash_registro)"
            " VALUES (:u, 'v1', 'h', 'otorgado', 'hr')"
        ),
        {"u": usuario_id},
    )
    await db.execute(
        _text(
            "INSERT INTO embedding_referencia (usuario_id, embedding_cifrado)"
            " VALUES (:u, 'cifrado')"
        ),
        {"u": usuario_id},
    )
    await db.execute(
        _text(
            "INSERT INTO foto_referencia (usuario_id, uri_storage, hash_sha256, bucket)"
            " VALUES (:u, 'memoria://foto', 'h', 'test')"
        ),
        {"u": usuario_id},
    )
    await db.commit()
