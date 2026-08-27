"""Repositorio SQLAlchemy para CategoriaPregunta (C-74)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exam_content.entities import CategoriaPregunta
from app.infrastructure.persistence.models.exam_content import CategoriaPreguntaModel


class CategoriaNoEncontradaError(Exception):
    """La categoría (origen o destino) no existe."""


class CicloCategoriaError(Exception):
    """Mover la categoría bajo el destino crearía un ciclo (a sí misma o a un descendiente)."""


class MateriaDistintaError(Exception):
    """El destino pertenece a otra materia — no se puede anidar entre materias."""


class CategoriaPreguntaSqlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def crear(
        self,
        cat: CategoriaPregunta,
        *,
        moodle_nombre_origen: str | None = None,
    ) -> CategoriaPregunta:
        row = CategoriaPreguntaModel(
            materia_id=cat.materia_id,
            nombre=cat.nombre,
            categoria_padre_id=cat.categoria_padre_id,
            moodle_nombre_origen=moodle_nombre_origen,
        )
        self._session.add(row)
        await self._session.flush()
        return self._row_to_entity(row)

    async def listar_por_materia(
        self, materia_id: str, *, estado: str = "activa"
    ) -> list[CategoriaPregunta]:
        """Categorías de la materia. ``estado``: 'activa' (default) | 'eliminada'
        (la papelera) | 'todas'."""
        stmt = select(CategoriaPreguntaModel).where(
            CategoriaPreguntaModel.materia_id == materia_id
        )
        if estado == "activa":
            stmt = stmt.where(CategoriaPreguntaModel.eliminada_en.is_(None))
        elif estado == "eliminada":
            stmt = stmt.where(CategoriaPreguntaModel.eliminada_en.is_not(None))
        result = await self._session.execute(stmt)
        return [self._row_to_entity(r) for r in result.scalars()]

    async def obtener(self, categoria_id: str) -> CategoriaPregunta | None:
        row = await self._session.get(CategoriaPreguntaModel, categoria_id)
        return self._row_to_entity(row) if row else None

    async def _ids_de_la_rama(self, categoria_id: str) -> list[str]:
        """La categoría y TODOS sus descendientes.

        La baja tiene que alcanzar a la rama entera: si solo se marcara el padre,
        sus subcategorías quedarían colgando de una categoría invisible y el árbol
        las mostraría como si fueran raíces. Se recorre en memoria (un banco tiene
        decenas de categorías, no miles) sobre las de la misma materia.
        """
        raiz = await self._session.get(CategoriaPreguntaModel, categoria_id)
        if raiz is None:
            return []
        result = await self._session.execute(
            select(
                CategoriaPreguntaModel.id, CategoriaPreguntaModel.categoria_padre_id
            ).where(CategoriaPreguntaModel.materia_id == raiz.materia_id)
        )
        hijos_de: dict[str | None, list[str]] = {}
        for cid, padre in result:
            hijos_de.setdefault(padre, []).append(cid)
        rama: list[str] = []
        pendientes = [categoria_id]
        while pendientes:
            actual = pendientes.pop()
            rama.append(actual)
            pendientes.extend(hijos_de.get(actual, []))
        return rama

    async def dar_de_baja(self, categoria_id: str, cuando: datetime) -> list[str]:
        """Baja LÓGICA de la categoría y su rama. Devuelve los ids afectados.

        Antes esto era un DELETE físico: el ON DELETE CASCADE borraba las
        subcategorías y el SET NULL mandaba las preguntas a "Sin clasificar",
        perdiendo la organización del banco sin posibilidad de deshacerlo.
        """
        ids = await self._ids_de_la_rama(categoria_id)
        if not ids:
            return []
        await self._session.execute(
            update(CategoriaPreguntaModel)
            .where(CategoriaPreguntaModel.id.in_(ids))
            .values(eliminada_en=cuando)
        )
        return ids

    async def reactivar(self, categoria_id: str) -> list[str]:
        """Devuelve al árbol la categoría y su rama. Devuelve los ids afectados."""
        ids = await self._ids_de_la_rama(categoria_id)
        if not ids:
            return []
        await self._session.execute(
            update(CategoriaPreguntaModel)
            .where(CategoriaPreguntaModel.id.in_(ids))
            .values(eliminada_en=None)
        )
        return ids

    async def borrar(self, categoria_id: str) -> None:
        """Borrado FÍSICO. Ya no lo usa la API (ver `dar_de_baja`): se conserva
        porque el import de Moodle reconcilia categorías y puede necesitar
        eliminar una que nunca llegó a tener contenido."""
        await self._session.execute(
            delete(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.id == categoria_id
            )
        )

    async def mover(
        self, categoria_id: str, nuevo_padre_id: str | None
    ) -> CategoriaPregunta:
        """Re-anida ``categoria_id`` bajo ``nuevo_padre_id`` (o a raíz si es None).

        Guarda de ciclos: el nuevo padre no puede ser la propia categoría ni
        ninguno de sus descendientes (moverla ahí desprendería un subárbol y
        crearía una referencia circular). El destino debe ser de la misma materia.
        """
        cat = await self._session.get(CategoriaPreguntaModel, categoria_id)
        if cat is None:
            raise CategoriaNoEncontradaError(categoria_id)

        if nuevo_padre_id is not None:
            if nuevo_padre_id == categoria_id:
                raise CicloCategoriaError(categoria_id)
            padre = await self._session.get(CategoriaPreguntaModel, nuevo_padre_id)
            if padre is None:
                raise CategoriaNoEncontradaError(nuevo_padre_id)
            if padre.materia_id != cat.materia_id:
                raise MateriaDistintaError(nuevo_padre_id)
            descendientes = await self._descendientes(cat.materia_id, categoria_id)
            if nuevo_padre_id in descendientes:
                raise CicloCategoriaError(nuevo_padre_id)

        cat.categoria_padre_id = nuevo_padre_id
        await self._session.flush()
        return self._row_to_entity(cat)

    async def _descendientes(self, materia_id: str, categoria_id: str) -> set[str]:
        """IDs de todas las categorías que cuelgan (a cualquier profundidad) de ``categoria_id``."""
        result = await self._session.execute(
            select(
                CategoriaPreguntaModel.id, CategoriaPreguntaModel.categoria_padre_id
            ).where(CategoriaPreguntaModel.materia_id == materia_id)
        )
        hijos_por_padre: dict[str, list[str]] = {}
        for cid, padre_id in result.all():
            if padre_id is not None:
                hijos_por_padre.setdefault(padre_id, []).append(cid)

        descendientes: set[str] = set()
        pila = list(hijos_por_padre.get(categoria_id, []))
        while pila:
            actual = pila.pop()
            if actual in descendientes:
                continue
            descendientes.add(actual)
            pila.extend(hijos_por_padre.get(actual, []))
        return descendientes

    async def resolver_o_crear(
        self, materia_id: str, nombre: str, padre_id: str | None
    ) -> CategoriaPregunta:
        """Resuelve la categoría que Moodle llama ``nombre`` bajo ``padre_id``.

        ``nombre`` es el nombre que trae el XML de Moodle, NO necesariamente el
        que ve el docente: si lo renombró, el nombre local difiere. Por eso el
        match es, en orden (0058):

        1. ``moodle_nombre_origen == nombre`` — la reconoce aunque esté renombrada.
        2. ``nombre == nombre`` con origen sin sellar — categoría preexistente o
           creada a mano que coincide; se le sella el origen para futuras pasadas.
        3. No existe → se crea, sellando el origen.

        El nombre local NUNCA se pisa: resolver es de solo lectura sobre ``nombre``.
        Memoización del import: la misma ruta repetida en un XML no crea duplicados.
        """
        # 1. Por nombre de origen — sobrevive al rename local.
        result = await self._session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id,
                CategoriaPreguntaModel.moodle_nombre_origen == nombre,
                CategoriaPreguntaModel.categoria_padre_id == padre_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return self._row_to_entity(existing)

        # 2. Por nombre local, solo si todavía no tiene origen sellado.
        result = await self._session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id,
                CategoriaPreguntaModel.nombre == nombre,
                CategoriaPreguntaModel.categoria_padre_id == padre_id,
                CategoriaPreguntaModel.moodle_nombre_origen.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.moodle_nombre_origen = nombre
            await self._session.flush()
            return self._row_to_entity(existing)

        # 3. Nueva.
        return await self.crear(
            CategoriaPregunta(nombre=nombre, materia_id=materia_id, categoria_padre_id=padre_id),
            moodle_nombre_origen=nombre,
        )

    @staticmethod
    def _row_to_entity(row: CategoriaPreguntaModel) -> CategoriaPregunta:
        return CategoriaPregunta(
            id=row.id,
            nombre=row.nombre,
            materia_id=row.materia_id,
            categoria_padre_id=row.categoria_padre_id,
            creada_en=row.creada_en,
            eliminada_en=row.eliminada_en,
        )
