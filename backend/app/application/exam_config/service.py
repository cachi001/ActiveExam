"""Casos de uso de configuracion de examen (aplicacion, C-07).

Mapea la superficie admin sobre la entidad ``Examen`` (C-05) sin reabrir el modelo:
- ventana temporal y estado -> ``Examen.ventana`` (``inicio``/``fin``/``estado``).
- umbrales por detector -> ``Examen.parametros["umbrales_detector"]``.
- estudiantes habilitados -> ``Examen.parametros["estudiantes_habilitados"]``.
- referencias biometricas -> ``Examen.parametros["referencias"]`` (metadata: cada
  estudiante tiene ``{uri, hash, precomputada}``; el binario nunca transita el
  backend, sube por URL firmada — D2).

La VALIDACION de parametros (D4) la hace el dominio (``exam_config.validation``)
antes de persistir; aqui se orquesta. Depende de PUERTOS (``ExamRepository``,
``AssignmentRepository``) — no del adaptador SQLAlchemy (Hexagonal).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.entities.assignment import Asignacion
from app.domain.entities.exam import Examen
from app.domain.exam_config.validation import validar_config_examen
from app.domain.repositories.ports import AssignmentRepository, ExamRepository


@dataclass(frozen=True, slots=True)
class ExamConfigInput:
    """Parametros de configuracion de un examen (entrada del caso de uso)."""

    nombre: str
    inicio: str
    fin: str
    umbral_score: float
    detectores: tuple[str, ...]
    umbrales_detector: dict[str, float] = field(default_factory=dict)
    politica_retencion: str = "estandar"
    exige_biometria: bool = True


class ExamConfigService:
    """Casos de uso de configuracion de examen (admin)."""

    def __init__(self, exams: ExamRepository, assignments: AssignmentRepository) -> None:
        self._exams = exams
        self._assignments = assignments

    # --- CRUD ----------------------------------------------------------------

    async def create_exam(self, data: ExamConfigInput) -> Examen:
        """Valida y crea un examen (RN-EX-01). 422 -> InvalidExamConfigError."""
        validar_config_examen(
            inicio=data.inicio,
            fin=data.fin,
            umbral_score=data.umbral_score,
            detectores=data.detectores,
            umbrales_detector=data.umbrales_detector,
            politica_retencion=data.politica_retencion,
        )
        examen = Examen(
            nombre=data.nombre,
            umbral_score=data.umbral_score,
            detectores=data.detectores,
            ventana={"inicio": data.inicio, "fin": data.fin, "estado": "programado"},
            retencion={"politica": data.politica_retencion},
            parametros={
                "umbrales_detector": {k: str(v) for k, v in data.umbrales_detector.items()},
                "estudiantes_habilitados": [],
                "referencias": {},
                "exige_biometria": "true" if data.exige_biometria else "false",
            },
        )
        return await self._exams.add(examen)

    async def get_exam(self, exam_id: str) -> Examen | None:
        return await self._exams.get(exam_id)

    async def update_exam(self, exam_id: str, data: ExamConfigInput) -> Examen | None:
        """Actualiza parametros validados, preservando habilitados/referencias."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return None
        validar_config_examen(
            inicio=data.inicio,
            fin=data.fin,
            umbral_score=data.umbral_score,
            detectores=data.detectores,
            umbrales_detector=data.umbrales_detector,
            politica_retencion=data.politica_retencion,
        )
        parametros = dict(actual.parametros)
        parametros["umbrales_detector"] = {
            k: str(v) for k, v in data.umbrales_detector.items()
        }
        parametros["exige_biometria"] = "true" if data.exige_biometria else "false"
        ventana = dict(actual.ventana)
        ventana.update({"inicio": data.inicio, "fin": data.fin})
        actualizado = Examen(
            id=actual.id,
            nombre=data.nombre,
            umbral_score=data.umbral_score,
            detectores=data.detectores,
            ventana=ventana,
            retencion={"politica": data.politica_retencion},
            parametros=parametros,
        )
        return await self._exams.update(actualizado)

    async def delete_exam(self, exam_id: str) -> bool:
        """Baja de un examen. Devuelve ``True`` si existia.

        La baja real (drop de fila) la decide el adaptador; aqui marca el estado y
        delega. Como C-07 no introduce un metodo ``delete`` en el puerto mutable de
        Examen (no estaba en C-05), la baja se modela como transicion de estado a
        ``baja`` (reversible, sin migracion destructiva — Rollback del design)."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return False
        ventana = dict(actual.ventana)
        ventana["estado"] = "baja"
        await self._exams.update(
            Examen(
                id=actual.id,
                nombre=actual.nombre,
                umbral_score=actual.umbral_score,
                detectores=actual.detectores,
                ventana=ventana,
                retencion=actual.retencion,
                parametros=actual.parametros,
            )
        )
        return True

    # --- Calendarizacion -----------------------------------------------------

    async def list_for_operations(
        self,
        *,
        desde: str | None = None,
        hasta: str | None = None,
        estado: str | None = None,
    ) -> list[Examen]:
        """Lista exámenes filtrando por ventana (inicio en [desde,hasta]) y estado
        (RN-EX-02). El filtro es lexicografico sobre ISO-8601 (orden cronologico)."""
        todos = await self._exams.list()
        resultado = []
        for ex in todos:
            inicio = ex.ventana.get("inicio", "")
            if desde and inicio < desde:
                continue
            if hasta and inicio > hasta:
                continue
            if estado and ex.ventana.get("estado") != estado:
                continue
            resultado.append(ex)
        return resultado

    # --- Estudiantes habilitados (RN-EX-03) ----------------------------------

    async def set_enabled_students(
        self, exam_id: str, estudiantes: list[str]
    ) -> Examen | None:
        """Fija la lista de habilitados (solo ellos pueden iniciar, RN-EX-03)."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return None
        parametros = dict(actual.parametros)
        # set para deduplicar; lista ordenada para persistencia determinista.
        parametros["estudiantes_habilitados"] = sorted(set(estudiantes))
        return await self._exams.update(_con_parametros(actual, parametros))

    async def get_enabled_students(self, exam_id: str) -> list[str] | None:
        actual = await self._exams.get(exam_id)
        if actual is None:
            return None
        return list(actual.parametros.get("estudiantes_habilitados", []))

    async def is_student_enabled(self, exam_id: str, estudiante_id: str) -> bool:
        """Gate de habilitacion consumible por C-09/C-10 (RN-EX-03)."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return False
        return estudiante_id in actual.parametros.get("estudiantes_habilitados", [])

    # --- Asignacion de proctores (RN-AU-07) ----------------------------------

    async def assign_proctors(
        self, exam_id: str, proctores: list[str]
    ) -> list[Asignacion]:
        """Crea las asignaciones proctor↔examen (C-06 las consume para el RBAC)."""
        existentes = {
            a.proctor_id for a in await self._assignments.list() if a.exam_id == exam_id
        }
        creadas: list[Asignacion] = []
        for proctor_id in proctores:
            if proctor_id in existentes:
                continue
            creadas.append(
                await self._assignments.add(
                    Asignacion(proctor_id=proctor_id, exam_id=exam_id)
                )
            )
        return creadas

    # --- Foto de referencia (D2, dato biometrico sensible) -------------------

    async def register_reference(
        self,
        exam_id: str,
        estudiante_id: str,
        *,
        uri: str | None,
        hash_binario: str | None,
        precomputada: bool,
    ) -> Examen | None:
        """Registra la METADATA de la referencia (uri/hash o precomputada).

        El binario NO transita el backend (sube por URL firmada, D2); aqui solo se
        persiste la referencia. La marca ``precomputada`` evita exigir la carga
        cuando la institucion ya provee el embedding (SU-01)."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return None
        parametros = dict(actual.parametros)
        referencias = dict(parametros.get("referencias", {}))
        referencias[estudiante_id] = {
            "uri": uri or "",
            "hash": hash_binario or "",
            "precomputada": "true" if precomputada else "false",
        }
        parametros["referencias"] = referencias
        return await self._exams.update(_con_parametros(actual, parametros))

    async def reference_missing(self, exam_id: str, estudiante_id: str) -> bool:
        """``True`` si el examen exige biometria y falta la referencia del
        estudiante (prerrequisito de la 1:1 de C-09)."""
        actual = await self._exams.get(exam_id)
        if actual is None:
            return True
        if actual.parametros.get("exige_biometria") != "true":
            return False
        ref = actual.parametros.get("referencias", {}).get(estudiante_id)
        if not ref:
            return True
        return not (ref.get("uri") or ref.get("precomputada") == "true")


def _con_parametros(examen: Examen, parametros: dict) -> Examen:
    """Copia el examen reemplazando solo ``parametros`` (resto inmutable)."""
    return Examen(
        id=examen.id,
        nombre=examen.nombre,
        umbral_score=examen.umbral_score,
        detectores=examen.detectores,
        ventana=examen.ventana,
        retencion=examen.retencion,
        parametros=parametros,
    )
