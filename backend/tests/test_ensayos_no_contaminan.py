"""Un ensayo del docente no puede ensuciar los números ni trabar el examen.

El sistema ya excluía las sesiones de prueba de los resultados y del write-back a
Moodle, pero se habían olvidado dos lugares (relevado el 29/8/2026):

- **Estadísticas**: cada ensayo sumaba a las sesiones iniciadas y a la
  distribución de riesgo institucional.
- **Volver a borrador**: un ensayo contaba como "ya lo rindieron" y dejaba el
  examen trabado en habilitado. El endpoint hermano (cambiar el sorteo) sí lo
  excluía: la misma regla aplicada en un lado y olvidada en el otro.

Sin mocks de DB (regla dura de código): lo que se prueba es qué cuenta la query.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

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


_JWT_SECRET = os.environ.get("JWT_OWN_SECRET", "test-jwt-own-secret-min-32bytes-activeexam")
_EMBEDDING_KEY = os.environ.get(
    "EMBEDDING_ENCRYPTION_KEY",
    "dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0cy1vbmx5LTMyYnl0ZXM=",
)
_ADMIN_PASS = "EnsayosAdmin2026"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    import importlib

    import app.config_activeexam as config_activeexam_module
    from fastapi.testclient import TestClient

    config_activeexam_module.get_activeexam_settings.cache_clear()
    for k, v in {
        "DATABASE_URL": _DB_URL,
        "FRONTEND_ORIGIN": "http://localhost:5173",
        "JWT_OWN_SECRET": _JWT_SECRET,
        "EMBEDDING_ENCRYPTION_KEY": _EMBEDDING_KEY,
    }.items():
        monkeypatch.setenv(k, v)

    import app.main_activeexam as main_activeexam_module

    importlib.reload(main_activeexam_module)
    app_instance = main_activeexam_module.create_activeexam_app()
    with TestClient(app_instance) as c:
        yield c
    config_activeexam_module.get_activeexam_settings.cache_clear()


@pytest.fixture
def admin_tok(client):
    """Admin recién creado: el token sale del login real, no de un JWT armado a mano."""
    import asyncio

    from app.infrastructure.auth.hashing import hashear_password
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )
    from sqlalchemy import delete

    async def _crear():
        engine = create_activeexam_engine(_url_async(_DB_URL))
        f = create_activeexam_session_factory(engine)
        async with f() as s:
            await s.execute(
                delete(UsuarioModel).where(UsuarioModel.username == "admin_ensayos")
            )
            await s.commit()
            s.add(
                UsuarioModel(
                    username="admin_ensayos",
                    email="admin_ensayos@test.local",
                    roles=["admin_sistema"],
                    password_hash=hashear_password(_ADMIN_PASS),
                    auth_provider="jwt",
                    attrs_federados={},
                )
            )
            await s.commit()
        await engine.dispose()

    async def _borrar():
        engine = create_activeexam_engine(_url_async(_DB_URL))
        f = create_activeexam_session_factory(engine)
        async with f() as s:
            await s.execute(
                delete(UsuarioModel).where(UsuarioModel.username == "admin_ensayos")
            )
            await s.commit()
        await engine.dispose()

    asyncio.run(_crear())
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "admin_ensayos", "password": _ADMIN_PASS},
    )
    assert r.status_code == 200, r.text
    yield r.json()["access_token"]
    asyncio.run(_borrar())


@pytest_asyncio.fixture
async def factory():
    from app.infrastructure.persistence.session_activeexam import (
        create_activeexam_engine,
        create_activeexam_session_factory,
    )

    engine = create_activeexam_engine(_url_async(_DB_URL))
    yield create_activeexam_session_factory(engine)
    await engine.dispose()


async def _armar_escenario(factory, *, con_sesion_real: bool):
    """Materia + comisión + examen, con un ensayo y (opcional) una rendición real.

    Devuelve el id del examen. Los scores van altos a propósito: si el ensayo
    contaminara, se vería en la distribución de riesgo.
    """
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        materia = MateriaModel(codigo=f"TST{sufijo}", nombre=f"Test {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C{sufijo}",
            nombre="Comisión de test",
            periodo="1C",
            anio=2026,
            codigo_matriculacion=f"TST-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(
            comision_id=comision.id,
            titulo=f"Examen {sufijo}",
            borrador=False,
        )
        s.add(examen)
        await s.flush()

        ahora = datetime.now(UTC)
        s.add(
            ProctoringSessionModel(
                modo="examen",
                examen_contenido_id=examen.id,
                alumno_idnumber="docente_ensayo",
                es_prueba=True,
                finalizada_en=ahora,
            )
        )
        if con_sesion_real:
            s.add(
                ProctoringSessionModel(
                    modo="examen",
                    examen_contenido_id=examen.id,
                    alumno_idnumber="alumno_real",
                    es_prueba=False,
                    finalizada_en=ahora,
                )
            )
        await s.commit()
        return str(examen.id)


async def _limpiar(factory, examen_id: str) -> None:
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
    from sqlalchemy import delete, select

    async with factory() as s:
        comision_id = (
            await s.execute(
                select(ExamenContenidoModel.comision_id).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one_or_none()
        await s.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.examen_contenido_id == examen_id
            )
        )
        await s.execute(
            delete(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
        )
        if comision_id:
            materia_id = (
                await s.execute(
                    select(ComisionModel.materia_id).where(
                        ComisionModel.id == comision_id
                    )
                )
            ).scalar_one_or_none()
            await s.execute(delete(ComisionModel).where(ComisionModel.id == comision_id))
            if materia_id:
                await s.execute(delete(MateriaModel).where(MateriaModel.id == materia_id))
        await s.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_las_estadisticas_no_cuentan_los_ensayos(factory) -> None:
    """Filtrando por el examen: la única sesión que cuenta es la real."""
    from app.application.stats.resumen_service import FiltrosStats, obtener_resumen

    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        async with factory() as db:
            resumen = await obtener_resumen(
                db, FiltrosStats(examen_contenido_id=examen_id)
            )
        assert resumen.total_sesiones == 1, (
            f"el ensayo está contando: total_sesiones={resumen.total_sesiones}"
        )
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_un_examen_solo_con_ensayos_no_suma_sesiones(factory) -> None:
    """Segundo caso: si SOLO hubo ensayos, el examen figura con cero actividad."""
    from app.application.stats.resumen_service import FiltrosStats, obtener_resumen

    examen_id = await _armar_escenario(factory, con_sesion_real=False)
    try:
        async with factory() as db:
            resumen = await obtener_resumen(
                db, FiltrosStats(examen_contenido_id=examen_id)
            )
        assert resumen.total_sesiones == 0
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_los_ensayos_no_traban_el_volver_a_borrador(factory, client, admin_tok) -> None:
    """Ensayar el examen no puede dejarlo habilitado para siempre.

    Contra el ENDPOINT real: repetir en el test la condición que usa el endpoint
    probaría la consulta del test, no el código que corre en producción.
    """
    examen_id = await _armar_escenario(factory, con_sesion_real=False)
    try:
        r = client.post(
            f"/api/v1/exam-content/{examen_id}/volver-a-borrador",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 204, r.text  # 204 No Content: volvió a borrador
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_una_rendicion_real_si_traba_el_volver_a_borrador(
    factory, client, admin_tok
) -> None:
    """El contrapeso: con un alumno que ya rindió, el examen queda trabado.

    Sin este caso, el arreglo anterior pasaría igual si alguien borrara la
    condición entera.
    """
    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        r = client.post(
            f"/api/v1/exam-content/{examen_id}/volver-a-borrador",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 409, r.text
        assert "examen_con_intentos" in r.text
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_registro_oculta_los_ensayos_por_defecto(factory, client, admin_tok) -> None:
    """Criterio de baja lógica: no se ven, pero se pueden pedir.

    El Registro los mostraba mezclados con las rendiciones reales (con un chip,
    pero mezclados). Quien audita una comisión no tiene por qué separar a ojo los
    ensayos del docente de lo que rindieron los alumnos.
    """
    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        r = client.get(
            f"/api/v1/proctoring/sessions/registro?exam_id={examen_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        alumnos = [i["alumno_idnumber"] for i in r.json()["items"]]
        assert alumnos == ["alumno_real"], f"se coló un ensayo: {alumnos}"
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_registro_los_muestra_si_se_piden(factory, client, admin_tok) -> None:
    """La contracara: ocultar sin forma de mostrar sería esconder."""
    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        r = client.get(
            f"/api/v1/proctoring/sessions/registro?exam_id={examen_id}&incluir_pruebas=true",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        alumnos = sorted(i["alumno_idnumber"] for i in r.json()["items"])
        assert alumnos == ["alumno_real", "docente_ensayo"], alumnos
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_contador_de_intentos_por_comision_ignora_los_ensayos(
    factory, client, admin_tok
) -> None:
    """El cartel del detalle decía "2 intentos rendidos" con un solo alumno.

    Ese número no es cosmético: es el que decide si la comisión se puede quitar
    del examen. Mostrar uno y aplicar otro deja al docente sin entender por qué
    el sistema lo frena.
    """
    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        r = client.get(
            f"/api/v1/exam-content/{examen_id}/comisiones",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        datos = r.json()
        items = datos if isinstance(datos, list) else datos.get("items", [])
        assert items, r.text
        assert items[0]["total_intentos"] == 1, items
    finally:
        await _limpiar(factory, examen_id)


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_el_listado_de_sesiones_expone_si_es_ensayo(factory, client, admin_tok) -> None:
    """GET /proctoring/sessions tiene que decir cuáles son ensayos.

    Este test existe por un bug real: el filtro de la Cola de revisión vive en el
    frontend y decide con este campo, pero el endpoint no lo devolvía. El test
    unitario del filtro pasaba porque le pasábamos el dato a mano, y en pantalla
    la cola seguía mostrando los ensayos. Sin el campo, aquel arreglo no existe.
    """
    examen_id = await _armar_escenario(factory, con_sesion_real=True)
    try:
        r = client.get(
            "/api/v1/proctoring/sessions",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        delExamen = [s for s in r.json() if s.get("examen_contenido_id") == examen_id]
        assert len(delExamen) == 2, delExamen
        assert sorted(bool(s["es_prueba"]) for s in delExamen) == [False, True]
    finally:
        await _limpiar(factory, examen_id)
