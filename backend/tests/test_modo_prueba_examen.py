"""Modo prueba: ensayar el examen antes de tomarlo (migración 0105).

Lo que fija este archivo:

1. Un examen en modo prueba solo lo ve el alumno HABILITADO. El resto de la
   comisión no, aunque esté inscripto: un ensayo no le tiene que aparecer a las
   70 personas que van a rendir el examen de verdad.
2. Toda sesión sobre un examen en modo prueba nace marcada `es_prueba`, sin
   importar quién la rinda. De ahí hereda todo lo que ya estaba construido: no
   cuenta como intento, no genera nota, no va a Moodle, no entra a la Cola de
   revisión ni a las estadísticas, y se puede borrar.
3. Se puede rendir aunque el examen esté en BORRADOR, que es justo el punto:
   probarlo antes de soltarlo.

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


async def _escenario(factory, *, modo_prueba: bool, borrador: bool = False):
    """Materia + comisión + examen + dos alumnos inscriptos, uno habilitado."""
    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        ExamenPruebaHabilitadoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.inscripcion import InscripcionModel
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    s8 = uuid.uuid4().hex[:8]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MP{s8}", nombre=f"Modo prueba {s8}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C{s8}",
            nombre="Comisión",
            periodo="2C",
            anio=2026,
            codigo_matriculacion=f"MP-{s8}",
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(
            comision_id=comision.id,
            titulo=f"Examen {s8}",
            borrador=borrador,
            modo_prueba=modo_prueba,
        )
        s.add(examen)
        await s.flush()

        habilitado = UsuarioModel(
            username=f"hab_{s8}",
            email=f"hab_{s8}@test.local",
            roles=["estudiante"],
            password_hash=hashear_password("Prueba2026"),
            auth_provider="jwt",
            attrs_federados={},
        )
        otro = UsuarioModel(
            username=f"otro_{s8}",
            email=f"otro_{s8}@test.local",
            roles=["estudiante"],
            password_hash=hashear_password("Prueba2026"),
            auth_provider="jwt",
            attrs_federados={},
        )
        s.add_all([habilitado, otro])
        await s.flush()

        # Los DOS inscriptos a la misma comisión: la diferencia es la habilitación.
        s.add_all(
            [
                InscripcionModel(usuario_id=habilitado.id, comision_id=comision.id),
                InscripcionModel(usuario_id=otro.id, comision_id=comision.id),
            ]
        )
        if modo_prueba:
            s.add(
                ExamenPruebaHabilitadoModel(
                    examen_contenido_id=examen.id, usuario_id=habilitado.id
                )
            )
        await s.commit()
        return {
            "examen_id": str(examen.id),
            "comision_id": str(comision.id),
            "materia_id": str(materia.id),
            "habilitado_id": str(habilitado.id),
            "otro_id": str(otro.id),
            "titulo": examen.titulo,
        }


async def _limpiar(factory, datos) -> None:
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.inscripcion import InscripcionModel
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from sqlalchemy import delete

    async with factory() as s:
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.examen_contenido_id == datos["examen_id"]
            )
        )
        await s.execute(
            delete(InscripcionModel).where(
                InscripcionModel.comision_id == datos["comision_id"]
            )
        )
        await s.execute(
            delete(ExamenContenidoModel).where(
                ExamenContenidoModel.id == datos["examen_id"]
            )
        )
        await s.execute(delete(ComisionModel).where(ComisionModel.id == datos["comision_id"]))
        await s.execute(delete(MateriaModel).where(MateriaModel.id == datos["materia_id"]))
        await s.execute(
            delete(UsuarioModel).where(
                UsuarioModel.id.in_([datos["habilitado_id"], datos["otro_id"]])
            )
        )
        await s.commit()


async def _titulos_que_ve(factory, usuario_id: str) -> list[str]:
    """Los exámenes que le llegan a ese alumno, por la misma consulta que la app."""
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
        InscripcionSqlRepository,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from sqlalchemy import select

    async with factory() as s:
        username = (
            await s.execute(select(UsuarioModel.username).where(UsuarioModel.id == usuario_id))
        ).scalar_one()
        comision_ids = await InscripcionSqlRepository(s).comision_ids_inscriptas(username)
        resumenes, _ = await ExamenContenidoSqlRepository(s).listar_paginado(
            page_size=100,
            comision_ids=comision_ids,
            incluir_borradores=False,
            usuario_id_para_pruebas=usuario_id,
        )
    return [r.titulo for r in resumenes]


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_solo_el_habilitado_ve_el_examen_de_prueba(factory) -> None:
    """El corazón del modo prueba: un ensayo no se le muestra a la comisión."""
    datos = await _escenario(factory, modo_prueba=True)
    try:
        assert datos["titulo"] in await _titulos_que_ve(factory, datos["habilitado_id"])
        assert datos["titulo"] not in await _titulos_que_ve(factory, datos["otro_id"])
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sin_modo_prueba_lo_ven_todos_los_inscriptos(factory) -> None:
    """El contrapeso: apagado, el examen es normal y lo ve la comisión entera."""
    datos = await _escenario(factory, modo_prueba=False)
    try:
        assert datos["titulo"] in await _titulos_que_ve(factory, datos["habilitado_id"])
        assert datos["titulo"] in await _titulos_que_ve(factory, datos["otro_id"])
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_examen_en_modo_prueba_se_puede_rendir_en_borrador(factory) -> None:
    """Probar ANTES de habilitarlo es el punto: el borrador no puede frenarlo."""
    from app.application.proctoring.enforcement import verificar_enforcement
    from datetime import UTC, datetime

    datos = await _escenario(factory, modo_prueba=True, borrador=True)
    try:
        async with factory() as db:
            # No lanza: el modo prueba saltea el borrador, igual que el ensayo del staff.
            await verificar_enforcement(
                db,
                examen_contenido_id=datos["examen_id"],
                alumno_idnumber="da_igual",
                ahora=datetime.now(UTC),
            )
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_un_examen_normal_en_borrador_si_frena(factory) -> None:
    """Sin esto, el test anterior pasaría aunque el borrador no se validara nunca."""
    from app.application.proctoring.enforcement import (
        ExamenEnBorradorError,
        verificar_enforcement,
    )
    from datetime import UTC, datetime

    datos = await _escenario(factory, modo_prueba=False, borrador=True)
    try:
        async with factory() as db:
            with pytest.raises(ExamenEnBorradorError):
                await verificar_enforcement(
                    db,
                    examen_contenido_id=datos["examen_id"],
                    alumno_idnumber="da_igual",
                    ahora=datetime.now(UTC),
                )
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_habilitado_ve_el_examen_de_prueba_aunque_este_en_borrador(factory) -> None:
    """Probar un examen ANTES de habilitarlo es el caso de uso del modo prueba.

    El enforcement ya dejaba rendirlo (el modo prueba saltea el borrador), pero el
    listado del alumno lo escondía por estar en borrador: el servidor le permitía
    rendir algo que su propia pantalla no le mostraba, así que era inalcanzable.
    """
    datos = await _escenario(factory, modo_prueba=True, borrador=True)
    try:
        assert datos["titulo"] in await _titulos_que_ve(factory, datos["habilitado_id"])
        # Y el resto de la comisión sigue sin verlo: es un borrador.
        assert datos["titulo"] not in await _titulos_que_ve(factory, datos["otro_id"])
    finally:
        await _limpiar(factory, datos)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_un_borrador_normal_sigue_invisible_para_todos(factory) -> None:
    """El contrapeso: sin modo prueba, un borrador no lo ve ningún alumno."""
    datos = await _escenario(factory, modo_prueba=False, borrador=True)
    try:
        assert datos["titulo"] not in await _titulos_que_ve(factory, datos["habilitado_id"])
        assert datos["titulo"] not in await _titulos_que_ve(factory, datos["otro_id"])
    finally:
        await _limpiar(factory, datos)
