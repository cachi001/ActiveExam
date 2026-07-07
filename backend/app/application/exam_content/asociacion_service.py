"""Servicio de asociación examen↔comisión y alta inline de materia/comisión (C-69, D11).

Casos de uso (admin):
- `asociar_examen_a_comision`: liga un examen ya importado a una comisión existente,
  sin reimportar el contenido (solo actualiza la FK NULLABLE comision_id).
- `alta_inline`: da de alta materia + comisión en un paso y, opcionalmente, asocia
  un examen ya importado a la comisión recién creada.

D11: un examen sin comisión es estado válido; asociar es opcional. Si la materia ya
existe (por `codigo`), se reutiliza en vez de duplicarla.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.exam_content.codigo_matriculacion import generar_codigo_libre
from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    ExamenNoEncontradoError,
)
from app.domain.exam_content.entities import Comision, ExamenContenido, Materia


@dataclass
class AltaInlineResult:
    materia: Materia
    comision: Comision
    examen_id: str | None = None


class AsociacionComisionService:
    """Caso de uso: asociar examen↔comisión y alta inline de materia/comisión."""

    def __init__(self, examen_repo, materia_repo, comision_repo) -> None:
        self._examen_repo = examen_repo
        self._materia_repo = materia_repo
        self._comision_repo = comision_repo

    async def asociar_examen_a_comision(
        self, examen_id: str, comision_id: str
    ) -> ExamenContenido:
        """Asocia un examen existente a una comisión existente.

        Raises:
            ComisionNoEncontradaError: si la comisión no existe.
            ExamenNoEncontradoError: si el examen no existe.
        """
        comision = await self._comision_repo.obtener(comision_id)
        if comision is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")

        examen = await self._examen_repo.asociar_comision(examen_id, comision_id)
        if examen is None:
            raise ExamenNoEncontradoError(f"Examen {examen_id!r} no existe.")
        return examen

    async def alta_inline(
        self,
        materia: Materia,
        comision_codigo: str,
        comision_nombre: str,
        periodo: str | None = None,
        anio: int | None = None,
        examen_id: str | None = None,
    ) -> AltaInlineResult:
        """Da de alta materia (o reutiliza si el codigo ya existe) + comisión.

        Si se pasa `examen_id`, asocia ese examen a la comisión creada.

        Raises:
            ExamenNoEncontradoError: si se pasó `examen_id` y no existe.
        """
        existente = await self._materia_repo.obtener_por_codigo(materia.codigo)
        materia_persistida = existente or await self._materia_repo.guardar(materia)

        # C-70: la comisión NO puede persistirse sin codigo_matriculacion (NOT NULL).
        # Se autogenera {materia.codigo}-{sufijo} con reintento ante colisión (23505).
        async def _persistir(cod_matriculacion: str) -> Comision:
            comision = Comision(
                codigo=comision_codigo,
                nombre=comision_nombre,
                materia_id=materia_persistida.id,
                periodo=periodo,
                anio=anio,
                codigo_matriculacion=cod_matriculacion,
            )
            return await self._comision_repo.guardar(comision)

        comision_persistida = await generar_codigo_libre(
            _persistir, materia_persistida.codigo
        )

        examen_asociado: str | None = None
        if examen_id is not None:
            examen = await self._examen_repo.asociar_comision(
                examen_id, comision_persistida.id
            )
            if examen is None:
                raise ExamenNoEncontradoError(f"Examen {examen_id!r} no existe.")
            examen_asociado = examen_id

        return AltaInlineResult(
            materia=materia_persistida,
            comision=comision_persistida,
            examen_id=examen_asociado,
        )
