"""c-78 — UNA SOLA COMISIÓN POR MATERIA (decisión del dueño, 26/8/2026).

El problema
-----------
El código de matriculación lo comparte el docente y no es secreto. Un alumno de
Comisión 1 podía conseguir el de Comisión 2 de la MISMA materia y quedar en las
dos. Medido antes de esta regla: nada lo impedía.

Y lo que arrastra es serio. Bajo el modelo REPLICADO (§14.1) cada comisión tiene
su **propia copia** del mismo parcial: un alumno en dos comisiones veía DOS
exámenes que son el mismo y podía rendir los dos. Peor, las réplicas comparten
``moodle_courseid``/``cmid`` (en el campus hay UNA aula por materia y las
comisiones son grupos dentro), así que las dos notas se escriben en el MISMO
destino para el MISMO alumno: la segunda pisa a la primera.

Decisión del dueño: **"no tiene sentido que esté en dos comisiones de la misma
materia"**. Se rechaza. Cambiar de comisión lo hace un admin, que primero da de
baja la inscripción anterior.

La regla vale en los TRES caminos por los que alguien queda inscripto, porque si
uno solo la puede violar el problema sigue existiendo:
  1. el alumno con el código de matriculación
  2. el alta manual del admin
  3. la matriculación automática al entrar por LTI

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.errors import YaInscriptoEnLaMateriaError
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel  # noqa: F401
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401

_TABLES = [
    "inscripcion",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                MateriaCoordinadorModel.__table__,
                ComisionModel.__table__,
                ComisionTutorModel.__table__,
                ExamenContenidoModel.__table__,
                InscripcionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class _Arbol:
    """Materia con dos comisiones, y los códigos con los que uno se matricula."""

    def __init__(self, materia_id, c1, c2, cod1, cod2):
        self.materia_id = materia_id
        self.c1 = c1
        self.c2 = c2
        self.cod1 = cod1
        self.cod2 = cod2


async def _materia_con_dos_comisiones(factory) -> _Arbol:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        c1 = ComisionModel(
            materia_id=materia.id, codigo=f"C1-{sufijo}", nombre="Comisión 1",
            codigo_matriculacion=f"K1-{sufijo}",
        )
        c2 = ComisionModel(
            materia_id=materia.id, codigo=f"C2-{sufijo}", nombre="Comisión 2",
            codigo_matriculacion=f"K2-{sufijo}",
        )
        s.add_all([c1, c2])
        await s.flush()
        arbol = _Arbol(
            materia.id, c1.id, c2.id, c1.codigo_matriculacion, c2.codigo_matriculacion
        )
        await s.commit()
    return arbol


async def _otra_materia_con_comision(factory) -> tuple[str, str]:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"OTRA-{sufijo}", nombre=f"Otra {sufijo}")
        s.add(materia)
        await s.flush()
        c = ComisionModel(
            materia_id=materia.id, codigo=f"CX-{sufijo}", nombre="Comisión X",
            codigo_matriculacion=f"KX-{sufijo}",
        )
        s.add(c)
        await s.flush()
        ids = (c.id, c.codigo_matriculacion)
        await s.commit()
    return ids


async def _alumno(factory) -> str:
    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"alu-{sufijo}",
            email=f"alu-{sufijo}@test.local",
            roles=["estudiante"],
            password_hash="!sin-password",
            nombre="Alumno",
            apellido="Doble",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _inscribir_directo(factory, usuario_id: str, comision_id: str) -> None:
    async with factory() as s:
        s.add(InscripcionModel(usuario_id=usuario_id, comision_id=comision_id))
        await s.commit()


async def _comisiones_de(factory, usuario_id: str) -> list[str]:
    async with factory() as s:
        filas = (
            await s.execute(
                text("SELECT comision_id FROM inscripcion WHERE usuario_id = :u"),
                {"u": usuario_id},
            )
        ).all()
    return [str(f[0]) for f in filas]


class _PerfilSiempreCompleto:
    """El gate de perfil (C-71) no es lo que se prueba acá: se da por cumplido.

    Sin esto, todos los tests morirían en `PerfilIncompletoError` antes de llegar
    a la regla de una comisión por materia, que es lo que se quiere ejercitar.
    """

    async def obtener_vigente(self, *_a, **_k):
        class _C:
            estado = "otorgado"
            vigente = True
        return _C()

    async def obtener(self, *_a, **_k):
        return self.obtener_vigente()


def _servicio_alumno(session):
    """`AutoMatriculacionService`: el camino del alumno con el código."""
    from app.application.exam_content.inscripcion_service import AutoMatriculacionService
    from app.infrastructure.persistence.repositories.exam_content import (
        ComisionSqlRepository,
        InscripcionSqlRepository,
        MateriaSqlRepository,
    )

    svc = AutoMatriculacionService(
        comision_repo=ComisionSqlRepository(session),
        materia_repo=MateriaSqlRepository(session),
        inscripcion_repo=InscripcionSqlRepository(session),
        consent_repo=None,
        embedding_repo=None,
        foto_repo=None,
    )
    # El gate de perfil se neutraliza: lo que se prueba es la regla de comisión.
    async def _ok(_usuario_id):
        return None

    svc._asegurar_perfil_completo = _ok  # type: ignore[method-assign]
    return svc


def _servicio_admin(session):
    """`InscripcionService`: el alta manual del admin."""
    from app.application.exam_content.inscripcion_service import InscripcionService
    from app.infrastructure.persistence.repositories.exam_content import (
        ComisionSqlRepository,
        InscripcionSqlRepository,
    )

    return InscripcionService(
        inscripcion_repo=InscripcionSqlRepository(session),
        comision_repo=ComisionSqlRepository(session),
        consent_repo=None,
        embedding_repo=None,
    )


# ---------------------------------------------------------------------------
# 1. El alumno, con el código de matriculación
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_codigo_de_otra_comision_de_la_misma_materia_se_rechaza(factory):
    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    async with factory() as s:
        with pytest.raises(YaInscriptoEnLaMateriaError):
            await _servicio_alumno(s).inscribir_por_codigo(arbol.cod2, alumno)

    assert await _comisiones_de(factory, alumno) == [arbol.c1], (
        "el rechazo no puede haber dejado una inscripción a medias"
    )


@pytest.mark.asyncio
async def test_el_mensaje_dice_en_que_comision_ya_esta(factory):
    """Sin el nombre, el alumno no sabe qué hacer con el error."""
    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    async with factory() as s:
        with pytest.raises(YaInscriptoEnLaMateriaError) as exc:
            await _servicio_alumno(s).inscribir_por_codigo(arbol.cod2, alumno)

    assert "Comisión 1" in str(exc.value)


@pytest.mark.asyncio
async def test_re_usar_el_codigo_de_SU_comision_sigue_siendo_idempotente(factory):
    """Triangulación: la regla es "otra comisión", no "cualquier comisión".

    Volver a pegar su propio código no es un error: responde amistoso, como antes.
    """
    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    async with factory() as s:
        res = await _servicio_alumno(s).inscribir_por_codigo(arbol.cod1, alumno)

    assert res.ya_inscripto is True
    assert await _comisiones_de(factory, alumno) == [arbol.c1]


@pytest.mark.asyncio
async def test_otra_MATERIA_no_se_bloquea(factory):
    """La regla es por materia. Un alumno cursa muchas materias a la vez."""
    arbol = await _materia_con_dos_comisiones(factory)
    otra_comision, otro_codigo = await _otra_materia_con_comision(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    async with factory() as s:
        res = await _servicio_alumno(s).inscribir_por_codigo(otro_codigo, alumno)
        await s.commit()  # el commit lo hace el router, no el servicio

    assert res.ya_inscripto is False
    assert set(await _comisiones_de(factory, alumno)) == {arbol.c1, otra_comision}


# ---------------------------------------------------------------------------
# 2. El alta manual del admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_admin_tampoco_puede_dejarlo_en_dos_comisiones(factory):
    """Si el admin la puede violar, la regla no existe.

    Para cambiar de comisión hay que dar de baja la anterior primero, que además
    es la operación que tiene la guarda de "ya rindió".
    """
    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    async with factory() as s:
        with pytest.raises(YaInscriptoEnLaMateriaError):
            await _servicio_admin(s).inscribir(arbol.c2, alumno)

    assert await _comisiones_de(factory, alumno) == [arbol.c1]


@pytest.mark.asyncio
async def test_el_admin_puede_inscribir_normalmente_a_una_materia_nueva(factory):
    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)

    async with factory() as s:
        await _servicio_admin(s).inscribir(arbol.c1, alumno)
        await s.commit()  # el commit lo hace el router, no el servicio

    assert await _comisiones_de(factory, alumno) == [arbol.c1]


# ---------------------------------------------------------------------------
# 3. La matriculación automática de LTI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lti_no_agrega_una_segunda_comision_de_la_misma_materia(factory):
    """Entrar por el link de OTRA comisión no puede duplicar la matrícula.

    Acá no se rechaza el launch: cortarle el ingreso al alumno por esto sería
    peor que el problema. Simplemente no se lo matricula de nuevo, y conserva la
    comisión que ya tenía.
    """
    from app.application.lti.jit_provisioning import _asegurar_matricula

    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)
    await _inscribir_directo(factory, alumno, arbol.c1)

    class _Deployment:
        comision_id = arbol.c2

    class _Usuario:
        id = alumno

    async with factory() as s:
        await _asegurar_matricula(s, usuario=_Usuario(), deployment=_Deployment())
        await s.commit()

    assert await _comisiones_de(factory, alumno) == [arbol.c1], (
        "LTI dejó al alumno en dos comisiones de la misma materia"
    )


@pytest.mark.asyncio
async def test_lti_sigue_matriculando_cuando_no_hay_conflicto(factory):
    from app.application.lti.jit_provisioning import _asegurar_matricula

    arbol = await _materia_con_dos_comisiones(factory)
    alumno = await _alumno(factory)

    class _Deployment:
        comision_id = arbol.c1

    class _Usuario:
        id = alumno

    async with factory() as s:
        await _asegurar_matricula(s, usuario=_Usuario(), deployment=_Deployment())
        await s.commit()

    assert await _comisiones_de(factory, alumno) == [arbol.c1]
