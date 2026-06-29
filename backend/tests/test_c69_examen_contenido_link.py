"""C-69 link: vínculo examen de proctoring (config) ↔ examen de contenido (Moodle).

Resuelve la pregunta abierta del design (línea 110): cómo se asocia el examen de
contenido importado con el examen-config que el alumno rinde. Se modela como una
REFERENCIA por id (`examen_contenido_id`, opcional/NULLABLE) que la entidad de
dominio ``Examen``, el ``ExamConfigService`` y los schemas/router de la API
transportan de punta a punta — sin mock de DB (repos en memoria que implementan los
puertos reales de C-05).

Reglas duras: Pydantic ``extra='forbid'``; snake_case; el vínculo es NULLABLE (un
examen sin contenido sigue siendo válido).
"""

from __future__ import annotations

import pytest

from app.application.exam_config.service import ExamConfigInput, ExamConfigService
from app.domain.entities.exam import Examen
from app.presentation.api.v1.exams.router import _input, _to_response
from app.presentation.api.v1.exams.schemas import ExamCreateRequest, ExamResponse
from tests.test_exam_config_service import InMemoryAssignmentRepo, InMemoryExamRepo

_CONTENIDO_ID = "11111111-1111-1111-1111-111111111111"


def _service() -> tuple[ExamConfigService, InMemoryExamRepo]:
    exams = InMemoryExamRepo()
    return ExamConfigService(exams, InMemoryAssignmentRepo()), exams


_INPUT_BASE = dict(
    nombre="Algebra Final",
    inicio="2026-06-01T09:00:00Z",
    fin="2026-06-01T11:00:00Z",
    umbral_score=0.7,
    detectores=("face_detection",),
    umbrales_detector={"face_detection": 0.5},
    politica_retencion="estandar",
)


# ---------------------------------------------------------------------------
# Dominio
# ---------------------------------------------------------------------------


def test_examen_dataclass_acepta_examen_contenido_id() -> None:
    ex = Examen(nombre="x", umbral_score=0.5, examen_contenido_id=_CONTENIDO_ID)
    assert ex.examen_contenido_id == _CONTENIDO_ID


def test_examen_dataclass_default_none() -> None:
    ex = Examen(nombre="x", umbral_score=0.5)
    assert ex.examen_contenido_id is None


# ---------------------------------------------------------------------------
# Servicio (create / update threads the reference; NULLABLE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_exam_persiste_examen_contenido_id() -> None:
    svc, exams = _service()
    examen = await svc.create_exam(
        ExamConfigInput(**_INPUT_BASE, examen_contenido_id=_CONTENIDO_ID)
    )
    assert examen.examen_contenido_id == _CONTENIDO_ID
    persistido = await exams.get(examen.id)
    assert persistido.examen_contenido_id == _CONTENIDO_ID


@pytest.mark.asyncio
async def test_create_exam_sin_contenido_es_none() -> None:
    svc, _ = _service()
    examen = await svc.create_exam(ExamConfigInput(**_INPUT_BASE))
    assert examen.examen_contenido_id is None


@pytest.mark.asyncio
async def test_update_exam_asocia_contenido_a_examen_existente() -> None:
    svc, _ = _service()
    examen = await svc.create_exam(ExamConfigInput(**_INPUT_BASE))
    assert examen.examen_contenido_id is None
    actualizado = await svc.update_exam(
        examen.id,
        ExamConfigInput(**_INPUT_BASE, examen_contenido_id=_CONTENIDO_ID),
    )
    assert actualizado.examen_contenido_id == _CONTENIDO_ID


@pytest.mark.asyncio
async def test_update_exam_sin_contenido_lo_desasocia() -> None:
    svc, _ = _service()
    examen = await svc.create_exam(
        ExamConfigInput(**_INPUT_BASE, examen_contenido_id=_CONTENIDO_ID)
    )
    actualizado = await svc.update_exam(examen.id, ExamConfigInput(**_INPUT_BASE))
    assert actualizado.examen_contenido_id is None


@pytest.mark.asyncio
async def test_set_enabled_students_preserva_examen_contenido_id() -> None:
    svc, _ = _service()
    examen = await svc.create_exam(
        ExamConfigInput(**_INPUT_BASE, examen_contenido_id=_CONTENIDO_ID)
    )
    tras = await svc.set_enabled_students(examen.id, ["alu-1"])
    assert tras.examen_contenido_id == _CONTENIDO_ID


# ---------------------------------------------------------------------------
# Schemas Pydantic (extra='forbid')
# ---------------------------------------------------------------------------


def test_request_acepta_examen_contenido_id() -> None:
    req = ExamCreateRequest(
        nombre="x",
        inicio="2026-06-01T09:00:00Z",
        fin="2026-06-01T11:00:00Z",
        umbral_score=0.7,
        examen_contenido_id=_CONTENIDO_ID,
    )
    assert req.examen_contenido_id == _CONTENIDO_ID


def test_request_default_none() -> None:
    req = ExamCreateRequest(
        nombre="x",
        inicio="2026-06-01T09:00:00Z",
        fin="2026-06-01T11:00:00Z",
        umbral_score=0.7,
    )
    assert req.examen_contenido_id is None


def test_request_extra_forbid_sigue_activo() -> None:
    with pytest.raises(Exception):
        ExamCreateRequest(
            nombre="x",
            inicio="2026-06-01T09:00:00Z",
            fin="2026-06-01T11:00:00Z",
            umbral_score=0.7,
            campo_raro=1,
        )


def test_response_incluye_examen_contenido_id() -> None:
    resp = ExamResponse(
        id="e1",
        nombre="x",
        umbral_score=0.7,
        detectores=[],
        ventana={},
        retencion={},
        parametros={},
        examen_contenido_id=_CONTENIDO_ID,
    )
    assert resp.examen_contenido_id == _CONTENIDO_ID


# ---------------------------------------------------------------------------
# Helpers del router (mapeo body<->input<->response)
# ---------------------------------------------------------------------------


def test_input_threads_examen_contenido_id() -> None:
    body = ExamCreateRequest(
        nombre="x",
        inicio="2026-06-01T09:00:00Z",
        fin="2026-06-01T11:00:00Z",
        umbral_score=0.7,
        examen_contenido_id=_CONTENIDO_ID,
    )
    inp = _input(body)
    assert inp.examen_contenido_id == _CONTENIDO_ID


def test_to_response_incluye_examen_contenido_id() -> None:
    examen = Examen(
        id="e1", nombre="x", umbral_score=0.7, examen_contenido_id=_CONTENIDO_ID
    )
    resp = _to_response(examen)
    assert resp.examen_contenido_id == _CONTENIDO_ID
