"""Servicio CRUD de Materias y Comisiones (C-69, D11).

Gestión de materias/comisiones INDEPENDIENTE del import de examen: crear y editar
sin tocar el contenido. Mantiene la capa router→service→repo y reusa tanto la
validación de dominio (entidades ``Materia``/``Comision``) como los errores ya
existentes (duplicado, no-encontrada, validación). No hay DELETE (riesgo de FK con
exámenes/comisiones); el codigo es inmutable (identidad académica de la entidad).
"""

from __future__ import annotations

from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    MateriaNoEncontradaError,
)
from app.domain.exam_content.entities import Comision, Materia


class MateriaComisionService:
    """Casos de uso (admin): CRUD de materias y comisiones, sin reimportar examen."""

    def __init__(self, materia_repo, comision_repo) -> None:
        self._materia_repo = materia_repo
        self._comision_repo = comision_repo

    # -- Materia -----------------------------------------------------------

    async def crear_materia(self, codigo: str, nombre: str) -> Materia:
        """Crea una materia nueva.

        Raises:
            MateriaInvalidaError: codigo/nombre vacíos (validación de dominio).
            MateriaDuplicadaError: ya existe una materia con ese codigo.
        """
        materia = Materia(codigo=codigo, nombre=nombre)  # valida dominio
        return await self._materia_repo.guardar(materia)

    async def actualizar_materia(self, materia_id: str, nombre: str) -> Materia:
        """Actualiza el nombre de una materia (el codigo es inmutable).

        Raises:
            MateriaNoEncontradaError: la materia no existe.
            MateriaInvalidaError: nombre vacío (validación de dominio).
        """
        actual = await self._materia_repo.obtener(materia_id)
        if actual is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")
        # Reusa la validación de dominio (nombre no vacío); el codigo se preserva.
        Materia(codigo=actual.codigo, nombre=nombre)
        actualizada = await self._materia_repo.actualizar(materia_id, nombre=nombre)
        assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada

    # -- Comisión ----------------------------------------------------------

    async def crear_comision(
        self,
        materia_id: str,
        codigo: str,
        nombre: str,
        periodo: str | None = None,
        anio: int | None = None,
    ) -> Comision:
        """Crea una comisión dentro de una materia existente.

        Raises:
            MateriaNoEncontradaError: la materia no existe.
            ComisionInvalidaError: codigo/nombre vacíos (validación de dominio).
            ComisionDuplicadaError: ya existe (materia_id, codigo).
        """
        materia = await self._materia_repo.obtener(materia_id)
        if materia is None:
            raise MateriaNoEncontradaError(f"Materia {materia_id!r} no existe.")
        comision = Comision(
            codigo=codigo,
            nombre=nombre,
            materia_id=materia_id,
            periodo=periodo,
            anio=anio,
        )  # valida dominio
        return await self._comision_repo.guardar(comision)

    async def actualizar_comision(
        self,
        comision_id: str,
        nombre: str,
        periodo: str | None = None,
        anio: int | None = None,
    ) -> Comision:
        """Actualiza nombre/periodo/anio de una comisión (codigo y materia inmutables).

        Raises:
            ComisionNoEncontradaError: la comisión no existe.
            ComisionInvalidaError: nombre vacío (validación de dominio).
        """
        actual = await self._comision_repo.obtener(comision_id)
        if actual is None:
            raise ComisionNoEncontradaError(f"Comisión {comision_id!r} no existe.")
        # Reusa la validación de dominio; codigo y materia_id se preservan.
        Comision(
            codigo=actual.codigo,
            nombre=nombre,
            materia_id=actual.materia_id,
            periodo=periodo,
            anio=anio,
        )
        actualizada = await self._comision_repo.actualizar(
            comision_id, nombre=nombre, periodo=periodo, anio=anio
        )
        assert actualizada is not None  # existía: lo verificamos arriba
        return actualizada
