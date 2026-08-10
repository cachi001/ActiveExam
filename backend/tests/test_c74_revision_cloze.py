"""C-74: la revision post-examen debe leer respuestas cloze de su tabla propia.

Bug real (reportado en vivo): obtener_revision() intentaba json.loads() un blob
en respuesta_alumno.opcion_elegida_id para preguntas cloze, pero las respuestas
cloze se persisten en respuesta_alumno_cloze (una fila por blank) desde que esa
tabla se separo de respuesta_alumno (ver RespuestaAlumnoClozeModel). El resultado
visible: la nota calculada aparecia bien (viene de moodle_writeback_estado, no de
esta query), pero el detalle de revision marcaba TODO como "sin responder" y
0 correctas, contradiciendo la nota mostrada arriba.

No usa DROP TABLE ni toca el esquema — inserta filas propias (sesion +
respuestas cloze) sobre datos ya existentes del seed/fixtures del proyecto y
las borra al final. Evita el patron destructivo de otros tests de este repo
(ver memoria "shared_dev_db_test_wipes").
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.moodle.revision_query import obtener_revision
from app.infrastructure.persistence.models.exam_content import (
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionClozeBlancoModel,
    PreguntaBancoModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    RespuestaAlumnoClozeModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


@pytest_asyncio.fixture
async def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _crear_examen_cloze_minimo(db: AsyncSession) -> dict:
    """Crea el arbol minimo: materia -> comision -> examen -> pregunta cloze
    con 2 blanks MULTICHOICE, uno correcto y otro incorrecto en la respuesta."""
    materia = MateriaModel(codigo="C74REV", nombre="Test revision cloze")
    db.add(materia)
    await db.flush()

    comision = ComisionModel(
        materia_id=materia.id,
        codigo="C74REV-C1",
        nombre="Comision test revision",
        codigo_matriculacion="C74REVMAT01",
    )
    db.add(comision)
    await db.flush()

    examen = ExamenContenidoModel(
        titulo="Test revision cloze",
        comision_id=comision.id,
        nota_maxima=100,
        nota_aprobacion=60,
        mostrar_nota="inmediata",
        revision_habilitada=True,
    )
    db.add(examen)
    await db.flush()

    categoria = CategoriaPreguntaModel(materia_id=materia.id, nombre="Test")
    db.add(categoria)
    await db.flush()

    banco = PreguntaBancoModel(
        materia_id=materia.id,
        categoria_id=categoria.id,
        tipo="cloze",
        enunciado="x = {1:MULTICHOICE:=correcto~incorrecto} y = {1:MULTICHOICE:correcto~=otro_correcto}",
    )
    db.add(banco)
    await db.flush()

    pregunta = PreguntaExamenModel(
        examen_id=examen.id,
        pregunta_banco_id=banco.id,
        tipo="cloze",
        enunciado=banco.enunciado,
        orden=0,
        seleccionada=True,
    )
    db.add(pregunta)
    await db.flush()

    blank1 = PreguntaClozeBlankModel(
        pregunta_id=pregunta.id, orden=0, tipo="multichoice", texto_antes="x = ", texto_despues=" y"
    )
    blank2 = PreguntaClozeBlankModel(
        pregunta_id=pregunta.id, orden=1, tipo="multichoice", texto_antes=" = ", texto_despues=""
    )
    db.add_all([blank1, blank2])
    await db.flush()

    op1_correcta = OpcionClozeBlancoModel(blank_id=blank1.id, texto="correcto", es_correcta=True)
    op1_incorrecta = OpcionClozeBlancoModel(blank_id=blank1.id, texto="incorrecto", es_correcta=False)
    op2_correcta = OpcionClozeBlancoModel(blank_id=blank2.id, texto="otro_correcto", es_correcta=True)
    op2_incorrecta = OpcionClozeBlancoModel(blank_id=blank2.id, texto="correcto", es_correcta=False)
    db.add_all([op1_correcta, op1_incorrecta, op2_correcta, op2_incorrecta])
    await db.flush()

    return {
        "examen_id": examen.id,
        "pregunta_id": pregunta.id,
        "blank1_id": blank1.id,
        "blank2_id": blank2.id,
        "op1_correcta_id": op1_correcta.id,
        "op2_correcta_id": op2_correcta.id,
        "op2_incorrecta_id": op2_incorrecta.id,
        "materia_id": materia.id,
        "comision_id": comision.id,
        "categoria_id": categoria.id,
        "banco_id": banco.id,
    }


async def _limpiar(db: AsyncSession, ids: dict) -> None:
    await db.execute(delete(ExamenContenidoModel).where(ExamenContenidoModel.id == ids["examen_id"]))
    await db.execute(delete(PreguntaBancoModel).where(PreguntaBancoModel.id == ids["banco_id"]))
    await db.execute(delete(CategoriaPreguntaModel).where(CategoriaPreguntaModel.id == ids["categoria_id"]))
    await db.execute(delete(ComisionModel).where(ComisionModel.id == ids["comision_id"]))
    await db.execute(delete(MateriaModel).where(MateriaModel.id == ids["materia_id"]))
    await db.commit()


@pytest.mark.asyncio
async def test_revision_lee_respuestas_cloze_de_su_tabla_propia(db: AsyncSession):
    """RED->GREEN: una respuesta cloze correcta debe contar como correcta y
    'respondida' en la revision, no como 'sin responder'."""
    ids = await _crear_examen_cloze_minimo(db)
    try:
        sesion = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-001",
            alumno_email="test-rev@activeexam.local",
            finalizada_en=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        db.add(sesion)
        await db.flush()

        db.add_all(
            [
                RespuestaAlumnoClozeModel(
                    session_id=sesion.id, pregunta_id=ids["pregunta_id"],
                    blank_id=ids["blank1_id"], valor=ids["op1_correcta_id"],
                ),
                RespuestaAlumnoClozeModel(
                    session_id=sesion.id, pregunta_id=ids["pregunta_id"],
                    blank_id=ids["blank2_id"], valor=ids["op2_incorrecta_id"],
                ),
            ]
        )
        await db.commit()

        rev = await obtener_revision(
            db=db,
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-001",
            alumno_email="test-rev@activeexam.local",
        )

        assert rev is not None
        assert rev.total_preguntas == 1
        assert rev.sin_responder == 0, "la pregunta fue respondida, no debe contar como sin responder"
        pregunta_revisada = rev.preguntas[0]
        assert pregunta_revisada.respondida is True
        assert pregunta_revisada.tipo == "cloze"
        assert len(pregunta_revisada.blanks_revisados) == 2

        blank1_rev = next(b for b in pregunta_revisada.blanks_revisados if b.orden == 0)
        blank2_rev = next(b for b in pregunta_revisada.blanks_revisados if b.orden == 1)
        assert blank1_rev.respuesta_alumno == "correcto"
        assert blank1_rev.es_correcta is True
        assert blank2_rev.respuesta_alumno == "correcto"
        assert blank2_rev.es_correcta is False

        await db.execute(delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sesion.id))
        await db.commit()
    finally:
        await _limpiar(db, ids)


@pytest.mark.asyncio
async def test_revision_cloze_sin_responder_sigue_marcando_sin_responder(db: AsyncSession):
    """TRIANGULATE: si el alumno no toco ningun blank, sigue contando como
    sin_responder (no queda todo en falso silencioso por la nueva query)."""
    ids = await _crear_examen_cloze_minimo(db)
    try:
        sesion = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-002",
            alumno_email="test-rev2@activeexam.local",
            finalizada_en=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        db.add(sesion)
        await db.commit()

        rev = await obtener_revision(
            db=db,
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-002",
            alumno_email="test-rev2@activeexam.local",
        )

        assert rev is not None
        assert rev.sin_responder == 1
        assert rev.preguntas[0].respondida is False

        await db.execute(delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sesion.id))
        await db.commit()
    finally:
        await _limpiar(db, ids)
