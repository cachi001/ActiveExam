"""c-78 E-07: examen en borrador — invisible para el alumno, probable por el docente.

No había forma de probar un examen sin exponerlo: la ventana apertura/cierre es
obligatoria y se aplica igual al docente, así que adelantar la apertura para
esconderlo también lo dejaba afuera a él.

`borrador` corta al alumno en el enforcement (backstop server-side, igual que la
baja lógica: sacarlo de los listados no alcanza contra una URL guardada) y deja
pasar al staff, que es el punto.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.proctoring.enforcement import (
    ExamenDadoDeBajaError,
    ExamenEnBorradorError,
    FueraDeVentanaError,
    verificar_enforcement,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

_TABLES = [
    "proctoring_session",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]

AHORA = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                ComisionModel.__table__,
                CategoriaPreguntaModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                ProctoringSessionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _examen(
    session: AsyncSession,
    *,
    borrador: bool = False,
    apertura: datetime | None = None,
    cierre: datetime | None = None,
    eliminado: bool = False,
) -> str:
    examen_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido"
            " (id, titulo, nota_maxima, nota_aprobacion, intentos_permitidos,"
            "  borrador, apertura, cierre, eliminado_en)"
            " VALUES (:id, 'Parcial', 10, 6, 1, :b, :ap, :ci, :el)"
        ),
        {
            "id": examen_id,
            "b": borrador,
            "ap": apertura,
            "ci": cierre,
            "el": AHORA if eliminado else None,
        },
    )
    await session.commit()
    return examen_id


@pytest.mark.asyncio
async def test_el_alumno_no_puede_rendir_un_examen_en_borrador(session: AsyncSession):
    """RED→GREEN: aunque tenga la URL, el borrador lo corta server-side."""
    examen_id = await _examen(session, borrador=True)

    with pytest.raises(ExamenEnBorradorError):
        await verificar_enforcement(
            session,
            examen_contenido_id=examen_id,
            alumno_idnumber="alumno1",
            ahora=AHORA,
        )


@pytest.mark.asyncio
async def test_el_docente_si_puede_rendirlo_para_probarlo(session: AsyncSession):
    """El punto del borrador: el docente lo rinde entero antes de habilitarlo."""
    examen_id = await _examen(session, borrador=True)

    await verificar_enforcement(
        session,
        examen_contenido_id=examen_id,
        alumno_idnumber="docente1",
        ahora=AHORA,
        es_prueba_de_staff=True,
    )


@pytest.mark.asyncio
async def test_el_docente_puede_probarlo_antes_de_la_apertura(session: AsyncSession):
    """Sin esto el borrador no serviría de nada.

    Probar un examen tiene sentido ANTES de que abra, que es justo cuando la
    ventana de rendición lo bloquearía.
    """
    examen_id = await _examen(
        session, borrador=True, apertura=AHORA + timedelta(days=2)
    )

    await verificar_enforcement(
        session,
        examen_contenido_id=examen_id,
        alumno_idnumber="docente1",
        ahora=AHORA,
        es_prueba_de_staff=True,
    )

    # TRIANGULATE: al alumno la ventana lo sigue cortando.
    with pytest.raises((ExamenEnBorradorError, FueraDeVentanaError)):
        await verificar_enforcement(
            session,
            examen_contenido_id=examen_id,
            alumno_idnumber="alumno1",
            ahora=AHORA,
        )


@pytest.mark.asyncio
async def test_la_prueba_del_staff_no_saltea_la_baja_logica(session: AsyncSession):
    """Un examen retirado no se rinde ni de prueba: la baja es una decisión tomada."""
    examen_id = await _examen(session, borrador=True, eliminado=True)

    with pytest.raises(ExamenDadoDeBajaError):
        await verificar_enforcement(
            session,
            examen_contenido_id=examen_id,
            alumno_idnumber="docente1",
            ahora=AHORA,
            es_prueba_de_staff=True,
        )


@pytest.mark.asyncio
async def test_un_examen_habilitado_no_cambia_para_nadie(session: AsyncSession):
    """Compat: sin borrador, el enforcement se comporta igual que antes."""
    examen_id = await _examen(session, borrador=False)

    await verificar_enforcement(
        session,
        examen_contenido_id=examen_id,
        alumno_idnumber="alumno1",
        ahora=AHORA,
    )


@pytest.mark.asyncio
async def test_al_alumno_la_ventana_lo_sigue_cortando_en_un_examen_habilitado(
    session: AsyncSession,
):
    """TRIANGULATE: el bypass es SOLO para el staff, la ventana sigue viva."""
    examen_id = await _examen(session, apertura=AHORA + timedelta(hours=3))

    with pytest.raises(FueraDeVentanaError):
        await verificar_enforcement(
            session,
            examen_contenido_id=examen_id,
            alumno_idnumber="alumno1",
            ahora=AHORA,
        )
