"""Tests del ExamConfigService con repositorios EN MEMORIA (C-07).

Cubre CRUD, calendarizacion, habilitados (RN-EX-03), asignacion de proctores
(RN-AU-07) y registro de referencia (D2). Los repos en memoria implementan los
puertos reales de C-05 (sin mock de DB). El adaptador SQLAlchemy se prueba con la
base real en ``@requires_stack``.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.exam_config.service import ExamConfigInput, ExamConfigService
from app.domain.entities.assignment import Asignacion
from app.domain.entities.exam import Examen
from app.domain.exam_config.errors import InvalidExamConfigError
from app.domain.repositories.ports import AssignmentRepository, ExamRepository


class InMemoryExamRepo(ExamRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, Examen] = {}
        self._seq = 0

    async def add(self, entity: Examen) -> Examen:
        self._seq += 1
        e = Examen(
            id=str(self._seq),
            nombre=entity.nombre,
            umbral_score=entity.umbral_score,
            parametros=entity.parametros,
            detectores=entity.detectores,
            ventana=entity.ventana,
            retencion=entity.retencion,
        )
        self._by_id[e.id] = e
        return e

    async def get(self, entity_id: str) -> Examen | None:
        return self._by_id.get(entity_id)

    async def list(self) -> list[Examen]:
        return list(self._by_id.values())

    async def update(self, entity: Examen) -> Examen:
        assert entity.id is not None
        self._by_id[entity.id] = entity
        return entity


class InMemoryAssignmentRepo(AssignmentRepository):
    def __init__(self) -> None:
        self._items: list[Asignacion] = []
        self._seq = 0

    async def add(self, entity: Asignacion) -> Asignacion:
        self._seq += 1
        a = Asignacion(id=str(self._seq), proctor_id=entity.proctor_id, exam_id=entity.exam_id)
        self._items.append(a)
        return a

    async def get(self, entity_id: str) -> Asignacion | None:
        return next((a for a in self._items if a.id == entity_id), None)

    async def list(self) -> list[Asignacion]:
        return list(self._items)

    async def update(self, entity: Asignacion) -> Asignacion:
        return entity


def _service() -> tuple[ExamConfigService, InMemoryExamRepo, InMemoryAssignmentRepo]:
    exams = InMemoryExamRepo()
    asgs = InMemoryAssignmentRepo()
    return ExamConfigService(exams, asgs), exams, asgs


_INPUT = ExamConfigInput(
    nombre="Algebra Final",
    inicio="2026-06-01T09:00:00Z",
    fin="2026-06-01T11:00:00Z",
    umbral_score=0.7,
    detectores=("face_detection", "face_mesh"),
    umbrales_detector={"face_detection": 0.5},
    politica_retencion="estandar",
)


def test_create_exam_persiste_y_devuelve_id() -> None:
    async def run() -> None:
        svc, exams, _ = _service()
        examen = await svc.create_exam(_INPUT)
        assert examen.id is not None
        assert examen.ventana["estado"] == "programado"
        assert len(await exams.list()) == 1

    asyncio.run(run())


def test_create_exam_invalido_no_persiste() -> None:
    async def run() -> None:
        svc, exams, _ = _service()
        with pytest.raises(InvalidExamConfigError):
            await svc.create_exam(
                ExamConfigInput(
                    nombre="x",
                    inicio="2026-06-01T11:00:00Z",
                    fin="2026-06-01T09:00:00Z",  # incoherente
                    umbral_score=0.5,
                    detectores=("face_mesh",),
                )
            )
        assert await exams.list() == []

    asyncio.run(run())


def test_update_exam_preserva_habilitados() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        examen = await svc.create_exam(_INPUT)
        await svc.set_enabled_students(examen.id, ["alu-1", "alu-2"])
        actualizado = await svc.update_exam(
            examen.id,
            ExamConfigInput(
                nombre="Algebra Final v2",
                inicio="2026-06-01T09:00:00Z",
                fin="2026-06-01T12:00:00Z",
                umbral_score=0.8,
                detectores=("face_detection",),
            ),
        )
        assert actualizado.umbral_score == 0.8
        # Habilitados preservados tras el update de parametros.
        assert set(actualizado.parametros["estudiantes_habilitados"]) == {"alu-1", "alu-2"}

    asyncio.run(run())


def test_delete_exam_marca_baja() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        examen = await svc.create_exam(_INPUT)
        assert await svc.delete_exam(examen.id) is True
        post = await svc.get_exam(examen.id)
        assert post.ventana["estado"] == "baja"

    asyncio.run(run())


def test_calendarizacion_filtra_por_rango_y_estado() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        await svc.create_exam(_INPUT)  # inicio 2026-06-01
        await svc.create_exam(
            ExamConfigInput(
                nombre="Fisica",
                inicio="2026-07-01T09:00:00Z",
                fin="2026-07-01T11:00:00Z",
                umbral_score=0.6,
                detectores=("face_detection",),
            )
        )
        en_junio = await svc.list_for_operations(
            desde="2026-06-01T00:00:00Z", hasta="2026-06-30T23:59:59Z"
        )
        assert [e.nombre for e in en_junio] == ["Algebra Final"]
        programados = await svc.list_for_operations(estado="programado")
        assert len(programados) == 2

    asyncio.run(run())


def test_habilitados_set_get_y_gate() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        examen = await svc.create_exam(_INPUT)
        await svc.set_enabled_students(examen.id, ["alu-1", "alu-1", "alu-2"])
        habilitados = await svc.get_enabled_students(examen.id)
        assert habilitados == ["alu-1", "alu-2"]  # dedup + orden
        assert await svc.is_student_enabled(examen.id, "alu-1") is True
        assert await svc.is_student_enabled(examen.id, "alu-99") is False

    asyncio.run(run())


def test_asignar_proctores_crea_asignaciones_sin_duplicar() -> None:
    async def run() -> None:
        svc, _, asgs = _service()
        examen = await svc.create_exam(_INPUT)
        await svc.assign_proctors(examen.id, ["p1", "p2"])
        await svc.assign_proctors(examen.id, ["p2", "p3"])  # p2 ya existia
        todas = [a for a in await asgs.list() if a.exam_id == examen.id]
        assert {a.proctor_id for a in todas} == {"p1", "p2", "p3"}

    asyncio.run(run())


def test_referencia_precomputada_no_falta() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        examen = await svc.create_exam(_INPUT)
        # Sin referencia: falta (examen exige biometria por defecto).
        assert await svc.reference_missing(examen.id, "alu-1") is True
        await svc.register_reference(
            examen.id, "alu-1", uri=None, hash_binario=None, precomputada=True
        )
        assert await svc.reference_missing(examen.id, "alu-1") is False

    asyncio.run(run())


def test_referencia_por_uri_no_falta() -> None:
    async def run() -> None:
        svc, _, _ = _service()
        examen = await svc.create_exam(_INPUT)
        await svc.register_reference(
            examen.id,
            "alu-2",
            uri="http://minio/evidence/ref/alu-2",
            hash_binario="abc",
            precomputada=False,
        )
        assert await svc.reference_missing(examen.id, "alu-2") is False

    asyncio.run(run())
