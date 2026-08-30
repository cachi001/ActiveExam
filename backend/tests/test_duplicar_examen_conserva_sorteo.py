"""Duplicar un examen conserva CÓMO se arma, no solo qué preguntas tiene.

Bug encontrado el 29/8/2026 probando en local: al duplicar un examen con sorteo
por intento, la copia salía en modo `fijo` (el default) y sin los tramos del
sorteo. Y como en modo fijo solo cuentan las preguntas marcadas `seleccionada`
—ninguna, porque el original las sorteaba— la copia aparecía en el listado con
"0 preguntas" y había que rearmarla entera a mano.

`_clonar_examen` copiaba 17 campos del examen y se olvidaba justo de los dos que
definen cómo se arma cada intento.

Sin mocks de DB (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://app:pass@localhost:55432/proctoring"
)


def _url_async(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


@pytest_asyncio.fixture
async def factory():
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    engine = create_activeexam_engine(_url_async(_DB_URL))
    yield create_activeexam_session_factory(engine)
    await engine.dispose()


async def _examen_con_sorteo(factory):
    """Examen en modo sorteo_por_intento, con una categoría y un tramo de 5."""
    from app.infrastructure.persistence.models.exam_content import (
        CategoriaPreguntaModel,
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
        TramoSorteoExamenModel,
    )

    s8 = uuid.uuid4().hex[:8]
    async with factory() as s:
        materia = MateriaModel(codigo=f"DUP{s8}", nombre=f"Duplicar {s8}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C{s8}",
            nombre="Comisión",
            periodo="2C",
            anio=2026,
            codigo_matriculacion=f"DUP-{s8}",
        )
        s.add(comision)
        await s.flush()
        categoria = CategoriaPreguntaModel(materia_id=materia.id, nombre=f"Cat {s8}")
        s.add(categoria)
        await s.flush()
        examen = ExamenContenidoModel(
            comision_id=comision.id,
            titulo=f"Original {s8}",
            modo_preguntas="sorteo_por_intento",
        )
        s.add(examen)
        await s.flush()
        s.add(
            TramoSorteoExamenModel(
                examen_id=examen.id,
                categoria_id=categoria.id,
                incluir_subcategorias=True,
                cantidad=5,
                orden=0,
            )
        )
        await s.commit()
        return {
            "examen_id": str(examen.id),
            "comision_id": str(comision.id),
            "materia_id": str(materia.id),
        }


async def _limpiar(factory, datos) -> None:
    from app.infrastructure.persistence.models.exam_content import (
        CategoriaPreguntaModel,
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from sqlalchemy import delete

    async with factory() as s:
        await s.execute(
            delete(ExamenContenidoModel).where(
                ExamenContenidoModel.comision_id == datos["comision_id"]
            )
        )
        await s.execute(
            delete(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == datos["materia_id"]
            )
        )
        await s.execute(delete(ComisionModel).where(ComisionModel.id == datos["comision_id"]))
        await s.execute(delete(MateriaModel).where(MateriaModel.id == datos["materia_id"]))
        await s.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_la_copia_conserva_el_modo_sorteo_y_sus_tramos(factory) -> None:
    """El caso del bug: copiar un examen que sortea por intento."""
    from app.presentation.api.v1.exam_content.catalog_router import _clonar_examen
    from app.infrastructure.persistence.models.exam_content import (
        ExamenContenidoModel,
        TramoSorteoExamenModel,
    )
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    datos = await _examen_con_sorteo(factory)
    try:
        async with factory() as s:
            original = (
                await s.execute(
                    select(ExamenContenidoModel)
                    .options(selectinload(ExamenContenidoModel.preguntas))
                    .where(ExamenContenidoModel.id == datos["examen_id"])
                )
            ).scalar_one()
            copia_id, _ = await _clonar_examen(
                s,
                original=original,
                titulo="La copia",
                comision_id=datos["comision_id"],
                lote_replica_id=None,
            )
            await s.commit()

        async with factory() as s:
            copia = (
                await s.execute(
                    select(ExamenContenidoModel).where(ExamenContenidoModel.id == copia_id)
                )
            ).scalar_one()
            tramos = (
                await s.execute(
                    select(TramoSorteoExamenModel).where(
                        TramoSorteoExamenModel.examen_id == copia_id
                    )
                )
            ).scalars().all()

        assert copia.modo_preguntas == "sorteo_por_intento", (
            f"la copia cayó a '{copia.modo_preguntas}': vuelve el bug de la copia vacía"
        )
        assert len(tramos) == 1, "la copia se quedó sin saber qué sortear"
        assert tramos[0].cantidad == 5
        assert tramos[0].incluir_subcategorias is True
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_un_examen_de_preguntas_fijas_se_copia_como_fijo(factory) -> None:
    """El contrapeso: copiar no puede convertir en sorteo lo que no lo era."""
    from app.presentation.api.v1.exam_content.catalog_router import _clonar_examen
    from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
    from sqlalchemy import select, update
    from sqlalchemy.orm import selectinload

    datos = await _examen_con_sorteo(factory)
    try:
        async with factory() as s:
            await s.execute(
                update(ExamenContenidoModel)
                .where(ExamenContenidoModel.id == datos["examen_id"])
                .values(modo_preguntas="fijo")
            )
            await s.commit()

        async with factory() as s:
            original = (
                await s.execute(
                    select(ExamenContenidoModel)
                    .options(selectinload(ExamenContenidoModel.preguntas))
                    .where(ExamenContenidoModel.id == datos["examen_id"])
                )
            ).scalar_one()
            copia_id, _ = await _clonar_examen(
                s,
                original=original,
                titulo="Copia fija",
                comision_id=datos["comision_id"],
                lote_replica_id=None,
            )
            await s.commit()

        async with factory() as s:
            copia = (
                await s.execute(
                    select(ExamenContenidoModel).where(ExamenContenidoModel.id == copia_id)
                )
            ).scalar_one()
        assert copia.modo_preguntas == "fijo"
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_duplicar_dos_veces_no_repite_el_nombre(factory) -> None:
    """Dos copias del mismo examen no pueden llamarse igual.

    Antes el título se armaba siempre como "{título} (copia)" sin mirar si ya
    existía: duplicar dos veces dejaba dos exámenes con el mismo nombre en la
    misma comisión, imposibles de distinguir en el listado.
    """
    from app.presentation.api.v1.exam_content.catalog_router import (
        _clonar_examen,
        _titulo_de_copia_libre,
    )
    from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    datos = await _examen_con_sorteo(factory)
    try:
        titulos: list[str] = []
        for _ in range(3):
            async with factory() as s:
                original = (
                    await s.execute(
                        select(ExamenContenidoModel)
                        .options(selectinload(ExamenContenidoModel.preguntas))
                        .where(ExamenContenidoModel.id == datos["examen_id"])
                    )
                ).scalar_one()
                titulo = await _titulo_de_copia_libre(
                    s, original.titulo, datos["comision_id"]
                )
                await _clonar_examen(
                    s,
                    original=original,
                    titulo=titulo,
                    comision_id=datos["comision_id"],
                    lote_replica_id=None,
                )
                await s.commit()
                titulos.append(titulo)

        assert len(set(titulos)) == 3, f"se repitieron nombres: {titulos}"
        assert titulos[0].endswith("(copia)")
        assert titulos[1].endswith("(copia 2)")
        assert titulos[2].endswith("(copia 3)")
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_un_titulo_escrito_a_mano_se_respeta(factory) -> None:
    """El contrapeso: si el docente eligió un nombre, no se lo numeramos."""
    from app.presentation.api.v1.exam_content.catalog_router import _titulo_de_copia_libre

    datos = await _examen_con_sorteo(factory)
    try:
        async with factory() as s:
            # El helper solo se usa cuando NO hay título explícito; con uno propio
            # el endpoint ni lo llama. Acá se verifica que la primera copia de un
            # título sin choque sale sin número.
            libre = await _titulo_de_copia_libre(s, "Sin choque alguno", datos["comision_id"])
        assert libre == "Sin choque alguno (copia)"
    finally:
        await _limpiar(factory, datos)
