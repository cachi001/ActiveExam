"""Repositorio SQLAlchemy para CategoriaPregunta (C-74)."""

from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exam_content.entities import CategoriaPregunta
from app.infrastructure.persistence.models.exam_content import CategoriaPreguntaModel


class CategoriaPreguntaSqlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def crear(self, cat: CategoriaPregunta) -> CategoriaPregunta:
        row = CategoriaPreguntaModel(
            materia_id=cat.materia_id,
            nombre=cat.nombre,
            categoria_padre_id=cat.categoria_padre_id,
        )
        self._session.add(row)
        await self._session.flush()
        return self._row_to_entity(row)

    async def listar_por_materia(self, materia_id: str) -> list[CategoriaPregunta]:
        result = await self._session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id
            )
        )
        return [self._row_to_entity(r) for r in result.scalars()]

    async def obtener(self, categoria_id: str) -> CategoriaPregunta | None:
        row = await self._session.get(CategoriaPreguntaModel, categoria_id)
        return self._row_to_entity(row) if row else None

    async def borrar(self, categoria_id: str) -> None:
        await self._session.execute(
            delete(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.id == categoria_id
            )
        )

    async def resolver_o_crear(
        self, materia_id: str, nombre: str, padre_id: str | None
    ) -> CategoriaPregunta:
        """Busca la categoría por (materia_id, nombre, padre_id); si no existe la crea.

        Memoización del import: la misma ruta repetida en un XML no crea duplicados.
        """
        result = await self._session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id,
                CategoriaPreguntaModel.nombre == nombre,
                CategoriaPreguntaModel.categoria_padre_id == padre_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return self._row_to_entity(existing)
        return await self.crear(
            CategoriaPregunta(nombre=nombre, materia_id=materia_id, categoria_padre_id=padre_id)
        )

    @staticmethod
    def _row_to_entity(row: CategoriaPreguntaModel) -> CategoriaPregunta:
        return CategoriaPregunta(
            id=row.id,
            nombre=row.nombre,
            materia_id=row.materia_id,
            categoria_padre_id=row.categoria_padre_id,
            creada_en=row.creada_en,
        )
