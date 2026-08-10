"""Credencial personal de Moodle del docente (C-73 §10).

Lo que se clava acá:
- el token se guarda CIFRADO y la contraseña NO se guarda en ningún lado,
- una credencial `caida` se comporta como ausente (para caer al respaldo),
- recargarla la reactiva (es lo que hace el docente cuando le avisamos),
- borrar es idempotente.

DB real (DATABASE_URL). Sin mocks de DB.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.credencial_docente_service import (
    DIAS_VENCIMIENTO_CREDENCIAL,
    ESTADO_CAIDA,
    ESTADO_VENCIDA,
    CredencialDocenteService,
    esta_vencida,
)
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.transactional import (
    MoodleCredencialDocenteModel,
    UsuarioModel,
)

# Clave Fernet válida de test (no es un secreto de producción).
_KEY = "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
_TOKEN = "t0ken-de-moodle-abcd"  # noqa: S105


# ---------------------------------------------------------------------------
# esta_vencida() — pura, sin DB (C-73 §12: revalidacion cada 30 dias)
# ---------------------------------------------------------------------------


def test_esta_vencida_recien_guardada_no_vencio():
    ahora = datetime(2026, 8, 1, tzinfo=timezone.utc)
    actualizado_en = ahora
    assert esta_vencida(actualizado_en, ahora) is False


def test_esta_vencida_a_los_29_dias_no_vencio():
    actualizado_en = datetime(2026, 7, 1, tzinfo=timezone.utc)
    ahora = actualizado_en + timedelta(days=29)
    assert esta_vencida(actualizado_en, ahora) is False


def test_esta_vencida_a_los_30_dias_exactos_vencio():
    actualizado_en = datetime(2026, 7, 1, tzinfo=timezone.utc)
    ahora = actualizado_en + timedelta(days=DIAS_VENCIMIENTO_CREDENCIAL)
    assert esta_vencida(actualizado_en, ahora) is True


def test_esta_vencida_a_los_60_dias_vencio():
    actualizado_en = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ahora = actualizado_en + timedelta(days=60)
    assert esta_vencida(actualizado_en, ahora) is True


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def service(factory):
    return CredencialDocenteService(
        session_factory=factory, cipher=SecretCipher(key=_KEY)
    )


@pytest_asyncio.fixture
async def docente_id(factory):
    legajo = f"D-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=legajo,
            email=f"{legajo.lower()}@uni.edu",
            roles=["tutor"],
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    yield uid
    async with factory() as s:
        await s.execute(text("DELETE FROM usuario WHERE id = :i"), {"i": uid})
        await s.commit()


@pytest.mark.asyncio
async def test_sin_credencial_el_estado_dice_no_configurada(service, docente_id):
    estado = await service.estado(docente_id)
    assert estado.configurada is False
    assert estado.token_pista is None


@pytest.mark.asyncio
async def test_guardar_token_lo_cifra_y_expone_solo_la_pista(
    service, factory, docente_id
):
    estado = await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    assert estado.configurada is True
    assert estado.moodle_username == "jperez"
    assert estado.token_pista == _TOKEN[-4:]

    # En la DB el token NO está en claro.
    async with factory() as s:
        fila = (
            await s.execute(
                select(MoodleCredencialDocenteModel).where(
                    MoodleCredencialDocenteModel.usuario_id == docente_id
                )
            )
        ).scalar_one()
    assert fila.token_cifrado != _TOKEN
    assert _TOKEN not in fila.token_cifrado


@pytest.mark.asyncio
async def test_la_tabla_no_tiene_donde_guardar_una_password(factory, docente_id):
    """Guardrail estructural: si mañana alguien intenta persistirla, no hay columna."""
    async with factory() as s:
        cols = (
            await s.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'moodle_credencial_docente'"
                )
            )
        ).scalars().all()
    assert not [c for c in cols if "pass" in c.lower() or "clave" in c.lower()]


@pytest.mark.asyncio
async def test_token_de_devuelve_el_token_en_claro(service, docente_id):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    assert await service.token_de(docente_id) == _TOKEN


@pytest.mark.asyncio
async def test_credencial_caida_se_comporta_como_ausente(service, docente_id):
    """Reintentar con un token ya rechazado solo repite el mismo error N veces."""
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await service.marcar_caida(docente_id)

    assert await service.token_de(docente_id) is None
    estado = await service.estado(docente_id)
    # Sigue visible para poder avisarle a la persona: marcada, no borrada.
    assert estado.configurada is True
    assert estado.estado == ESTADO_CAIDA


@pytest.mark.asyncio
async def test_recargar_la_credencial_la_reactiva(service, docente_id):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await service.marcar_caida(docente_id)

    nuevo = "t0ken-nuevo-wxyz"  # noqa: S105
    estado = await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=nuevo
    )
    assert estado.estado == "activa"
    assert await service.token_de(docente_id) == nuevo


@pytest.mark.asyncio
async def test_borrar_es_idempotente(service, docente_id):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await service.borrar(docente_id)
    estado = await service.borrar(docente_id)
    assert estado.configurada is False
    assert await service.token_de(docente_id) is None


@pytest.mark.asyncio
async def test_marcar_uso_sella_el_ultimo_uso(service, docente_id):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    assert (await service.estado(docente_id)).ultimo_uso_en is None
    await service.marcar_uso(docente_id)
    assert (await service.estado(docente_id)).ultimo_uso_en is not None


async def _envejecer_credencial(factory, docente_id, dias: int) -> None:
    """Retrasa `actualizado_en` para simular una credencial con antiguedad dada."""
    async with factory() as s:
        await s.execute(
            text(
                "UPDATE moodle_credencial_docente SET actualizado_en = "
                ":ts WHERE usuario_id = :uid"
            ),
            {
                "ts": datetime.now(timezone.utc) - timedelta(days=dias),
                "uid": docente_id,
            },
        )
        await s.commit()


@pytest.mark.asyncio
async def test_credencial_vencida_a_los_30_dias_estado_dice_vencida(
    service, factory, docente_id
):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await _envejecer_credencial(factory, docente_id, DIAS_VENCIMIENTO_CREDENCIAL)

    estado = await service.estado(docente_id)
    assert estado.estado == ESTADO_VENCIDA


@pytest.mark.asyncio
async def test_credencial_vencida_token_de_devuelve_none_sin_reintentar(
    service, factory, docente_id
):
    """Igual que `caida`: no reintenta con un token cuya contrasena de origen
    ya no esta demostrada como vigente."""
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await _envejecer_credencial(factory, docente_id, DIAS_VENCIMIENTO_CREDENCIAL)

    assert await service.token_de(docente_id) is None


@pytest.mark.asyncio
async def test_credencial_a_los_29_dias_todavia_activa(service, factory, docente_id):
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await _envejecer_credencial(factory, docente_id, DIAS_VENCIMIENTO_CREDENCIAL - 1)

    estado = await service.estado(docente_id)
    assert estado.estado == "activa"
    assert await service.token_de(docente_id) == _TOKEN


@pytest.mark.asyncio
async def test_credencial_caida_prevalece_sobre_vencida(service, factory, docente_id):
    """Si Moodle ya la rechazo, importa poco que ademas sea vieja: el mensaje
    correcto es 'se cayo', no 'vencio', porque fue Moodle quien la tumbo."""
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await service.marcar_caida(docente_id)
    await _envejecer_credencial(factory, docente_id, DIAS_VENCIMIENTO_CREDENCIAL)

    estado = await service.estado(docente_id)
    assert estado.estado == ESTADO_CAIDA


@pytest.mark.asyncio
async def test_recargar_una_credencial_vencida_reinicia_el_contador_de_30_dias(
    service, factory, docente_id
):
    """Renovar (guardar_token de nuevo) es la UNICA forma de demostrar la
    contrasena vigente sin persistirla — tiene que pisar `actualizado_en`."""
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    await _envejecer_credencial(factory, docente_id, DIAS_VENCIMIENTO_CREDENCIAL)
    assert (await service.estado(docente_id)).estado == ESTADO_VENCIDA

    nuevo = "t0ken-renovado-zzzz"  # noqa: S105
    estado = await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=nuevo
    )
    assert estado.estado == "activa"
    assert (await service.estado(docente_id)).estado == "activa"
    assert await service.token_de(docente_id) == nuevo


@pytest.mark.asyncio
async def test_dar_de_baja_al_usuario_arrastra_su_credencial(
    service, factory, docente_id
):
    """FK ON DELETE CASCADE: no queda un token huérfano de un usuario borrado."""
    await service.guardar_token(
        usuario_id=docente_id, moodle_username="jperez", token=_TOKEN
    )
    async with factory() as s:
        await s.execute(text("DELETE FROM usuario WHERE id = :i"), {"i": docente_id})
        await s.commit()

    async with factory() as s:
        quedan = (
            await s.execute(
                select(MoodleCredencialDocenteModel).where(
                    MoodleCredencialDocenteModel.usuario_id == docente_id
                )
            )
        ).scalar_one_or_none()
    assert quedan is None
