"""C-78: la revisión post-examen debe resolver blanks tipo="matching" por id
(igual que multichoice), no como texto libre.

Antes de este fix, revision_query.obtener_revision() solo trataba
blank.tipo == "multichoice" como "elige por id" — un blank "matching" caía en
la rama de texto libre, comparando el UUID crudo de la opción elegida contra
el TEXTO de las opciones correctas (nunca iba a matchear) y mostrando el UUID
crudo como "respuesta_alumno" en vez del texto de la opción elegida.

No usa DROP TABLE — inserta filas propias sobre datos existentes y las borra
al final (mismo patrón que test_c74_revision_cloze.py).
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
from app.infrastructure.persistence.models.moodle_writeback import RespuestaAlumnoClozeModel
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


async def _crear_examen_matching_minimo(db: AsyncSession) -> dict:
    """materia -> comision -> examen -> pregunta cloze con 2 blanks 'matching'."""
    materia = MateriaModel(codigo="C78REV", nombre="Test revision matching")
    db.add(materia)
    await db.flush()

    comision = ComisionModel(
        materia_id=materia.id,
        codigo="C78REV-C1",
        nombre="Comision test revision matching",
        codigo_matriculacion="C78REVMAT01",
    )
    db.add(comision)
    await db.flush()

    examen = ExamenContenidoModel(
        titulo="Test revision matching",
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
        enunciado="Une cada lenguaje con su paradigma",
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
        pregunta_id=pregunta.id, orden=0, tipo="matching", texto_antes="Python:  ", texto_despues=""
    )
    blank2 = PreguntaClozeBlankModel(
        pregunta_id=pregunta.id, orden=1, tipo="matching", texto_antes="Haskell:  ", texto_despues=""
    )
    db.add_all([blank1, blank2])
    await db.flush()

    # Pool completo en AMBOS blanks (como matching real) — una correcta por blank.
    b1_correcta = OpcionClozeBlancoModel(blank_id=blank1.id, texto="Multiparadigma", es_correcta=True)
    b1_incorrecta = OpcionClozeBlancoModel(blank_id=blank1.id, texto="Funcional", es_correcta=False)
    b2_correcta = OpcionClozeBlancoModel(blank_id=blank2.id, texto="Funcional", es_correcta=True)
    b2_incorrecta = OpcionClozeBlancoModel(blank_id=blank2.id, texto="Multiparadigma", es_correcta=False)
    db.add_all([b1_correcta, b1_incorrecta, b2_correcta, b2_incorrecta])
    await db.flush()

    return {
        "examen_id": examen.id,
        "pregunta_id": pregunta.id,
        "blank1_id": blank1.id,
        "blank2_id": blank2.id,
        "b1_correcta_id": b1_correcta.id,
        "b2_correcta_id": b2_correcta.id,
        "b2_incorrecta_id": b2_incorrecta.id,
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
async def test_revision_matching_resuelve_por_id_no_por_texto_crudo(db: AsyncSession):
    """RED→GREEN: blank 'matching' se resuelve como multichoice — el id elegido
    se traduce al TEXTO de la opción, y es_correcta refleja la opción elegida
    (no el UUID crudo comparado como si fuera texto libre)."""
    ids = await _crear_examen_matching_minimo(db)
    try:
        sesion = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-MATCH-001",
            alumno_email="test-rev-match@activeexam.local",
            finalizada_en=datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        db.add(sesion)
        await db.flush()

        db.add_all(
            [
                RespuestaAlumnoClozeModel(
                    session_id=sesion.id, pregunta_id=ids["pregunta_id"],
                    blank_id=ids["blank1_id"], valor=ids["b1_correcta_id"],
                ),
                RespuestaAlumnoClozeModel(
                    session_id=sesion.id, pregunta_id=ids["pregunta_id"],
                    blank_id=ids["blank2_id"], valor=ids["b2_incorrecta_id"],
                ),
            ]
        )
        await db.commit()

        rev = await obtener_revision(
            db=db,
            examen_contenido_id=ids["examen_id"],
            alumno_idnumber="TEST-REV-MATCH-001",
            alumno_email="test-rev-match@activeexam.local",
        )

        assert rev is not None
        pregunta_revisada = rev.preguntas[0]
        assert pregunta_revisada.respondida is True
        blank1_rev = next(b for b in pregunta_revisada.blanks_revisados if b.orden == 0)
        blank2_rev = next(b for b in pregunta_revisada.blanks_revisados if b.orden == 1)

        # El texto mostrado es el de la OPCIÓN elegida, no el UUID crudo.
        assert blank1_rev.respuesta_alumno == "Multiparadigma"
        assert blank1_rev.es_correcta is True
        assert blank2_rev.respuesta_alumno == "Multiparadigma"  # eligió la incorrecta a propósito
        assert blank2_rev.es_correcta is False

        await db.execute(delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sesion.id))
        await db.commit()
    finally:
        await _limpiar(db, ids)
