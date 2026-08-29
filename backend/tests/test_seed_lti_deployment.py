"""El seed siembra el deployment LTI de confianza y NO siembra contenido academico.

Por que existe este test: sin una fila en ``lti_deployment_confiable`` TODO launch
desde el campus muere en ``POST /api/v1/lti/login`` con
``403 {"detail":"lti_iss_no_confiable"}``, antes de mirar que usuario es. Esa fila
no tenia seed ni migracion que la poblara, asi que cada vez que se recreaba la base
habia que restaurarla a mano desde un backup. Un dato del que depende que entre
CUALQUIER alumno no puede depender de que alguien se acuerde.

Los valores salen del entorno (``LTI_ISS``, ``LTI_CLIENT_ID``, ``LTI_DEPLOYMENT_ID``,
``LTI_JWKS_URI``) y nunca del codigo: este repo es publico y el emisor real es un
campus concreto.

Requiere DB real (``requires_stack``): mockear la base no probaria la idempotencia,
que es una restriccion de unicidad del propio Postgres.
"""

from __future__ import annotations

import importlib.util
import os
from types import ModuleType

import pytest
from sqlalchemy import delete, func, select

ISS_TEST = "https://campus-de-prueba.invalid"
CLIENT_ID_TEST = "client-de-prueba-1"
DEPLOYMENT_ID_TEST = "42"
JWKS_TEST = "https://campus-de-prueba.invalid/mod/lti/certs.php"


def _cargar_seed() -> ModuleType:
    """Carga scripts/seed_users.py como modulo (no es importable por nombre)."""
    seed_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "seed_users.py",
    )
    spec = importlib.util.spec_from_file_location("seed_users_bajo_test", seed_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _factory():
    """Engine activeexam: solo necesita DATABASE_URL.

    El engine del stack full exige Keycloak/MinIO/OTEL en el entorno y aca no
    hacen falta para hablar con una tabla.
    """
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    engine = create_activeexam_engine(os.environ["DATABASE_URL"])
    return create_activeexam_session_factory(engine), engine


def _configurar_lti(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LTI_ISS", ISS_TEST)
    monkeypatch.setenv("LTI_CLIENT_ID", CLIENT_ID_TEST)
    monkeypatch.setenv("LTI_DEPLOYMENT_ID", DEPLOYMENT_ID_TEST)
    monkeypatch.setenv("LTI_JWKS_URI", JWKS_TEST)


async def _limpiar(factory) -> None:
    from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

    async with factory() as session:
        await session.execute(
            delete(LtiDeploymentConfiableModel).where(
                LtiDeploymentConfiableModel.iss == ISS_TEST
            )
        )
        await session.commit()


async def _contar(factory) -> int:
    from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

    async with factory() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(LtiDeploymentConfiableModel)
                .where(LtiDeploymentConfiableModel.iss == ISS_TEST)
            )
        ).scalar_one()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_siembra_el_deployment_cuando_falta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Base sin la fila: el seed la crea activa y con los valores del entorno."""
    from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

    _configurar_lti(monkeypatch)
    seed = _cargar_seed()
    factory, engine = _factory()
    try:
        await _limpiar(factory)

        await seed._seed_lti_deployment(factory)

        async with factory() as session:
            fila = (
                await session.execute(
                    select(LtiDeploymentConfiableModel).where(
                        LtiDeploymentConfiableModel.iss == ISS_TEST
                    )
                )
            ).scalar_one()
        assert fila.client_id == CLIENT_ID_TEST
        assert fila.deployment_id == DEPLOYMENT_ID_TEST
        assert fila.jwks_uri == JWKS_TEST
        assert fila.activo is True, "una fila inactiva rechaza todos los launches"

        await _limpiar(factory)
    finally:
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_no_duplica_al_correr_dos_veces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idempotente: el CMD del contenedor corre el seed en CADA deploy."""
    _configurar_lti(monkeypatch)
    seed = _cargar_seed()
    factory, engine = _factory()
    try:
        await _limpiar(factory)

        await seed._seed_lti_deployment(factory)
        await seed._seed_lti_deployment(factory)

        assert await _contar(factory) == 1

        await _limpiar(factory)
    finally:
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sin_variables_no_hace_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin configurar, el seed no inventa un emisor ni rompe el arranque.

    El CMD del contenedor encadena el seed con el arranque de uvicorn: una
    excepcion aca dejaria el server sin levantar en un entorno que ni siquiera
    usa LTI.
    """
    for var in ("LTI_ISS", "LTI_CLIENT_ID", "LTI_DEPLOYMENT_ID", "LTI_JWKS_URI"):
        monkeypatch.delenv(var, raising=False)
    seed = _cargar_seed()
    factory, engine = _factory()
    try:
        await _limpiar(factory)

        await seed._seed_lti_deployment(factory)

        assert await _contar(factory) == 0
    finally:
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_respeta_un_deployment_desactivado_a_mano(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si un admin lo desactivo, el deploy siguiente NO lo revive.

    Desactivar es la forma de cortar el acceso de un campus comprometido. Que un
    redeploy lo volviera a habilitar convertiria al seed en un bypass.
    """
    from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

    _configurar_lti(monkeypatch)
    seed = _cargar_seed()
    factory, engine = _factory()
    try:
        await _limpiar(factory)
        await seed._seed_lti_deployment(factory)

        async with factory() as session:
            fila = (
                await session.execute(
                    select(LtiDeploymentConfiableModel).where(
                        LtiDeploymentConfiableModel.iss == ISS_TEST
                    )
                )
            ).scalar_one()
            fila.activo = False
            await session.commit()

        await seed._seed_lti_deployment(factory)

        async with factory() as session:
            fila = (
                await session.execute(
                    select(LtiDeploymentConfiableModel).where(
                        LtiDeploymentConfiableModel.iss == ISS_TEST
                    )
                )
            ).scalar_one()
        assert fila.activo is False
        assert await _contar(factory) == 1

        await _limpiar(factory)
    finally:
        await engine.dispose()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_seed_ya_no_crea_la_materia_demo() -> None:
    """El seed no siembra Programacion 1 / Comision 1.

    Decision del dueño (29/8/2026): la estructura academica la carga cada
    institucion; un PROG1 fantasma reaparecia en cada deploy y ensuciaba la base
    de produccion.
    """
    seed = _cargar_seed()
    assert not hasattr(seed, "_seed_contenido")
    assert not hasattr(seed, "_seed_matriculaciones")
