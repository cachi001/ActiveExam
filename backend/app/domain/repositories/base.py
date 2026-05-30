"""Puerto de repositorio generico (PURO).

Contrato CRUD minimo, parametrizado por el tipo de entidad de dominio. Los
puertos especificos (audit log, consentimiento) restringen este contrato para
codificar invariantes (solo-append, sin update). Sin SQLAlchemy (dominio puro).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Puerto generico de persistencia para una entidad de dominio ``T``."""

    @abstractmethod
    async def add(self, entity: T) -> T:
        """Persiste una entidad nueva y devuelve su version persistida (con id)."""

    @abstractmethod
    async def get(self, entity_id: str) -> T | None:
        """Recupera una entidad por id, o ``None`` si no existe."""

    @abstractmethod
    async def list(self) -> list[T]:
        """Lista las entidades del repositorio."""


class MutableRepository(Repository[T]):
    """Puerto para entidades que admiten actualizacion (NO el audit log ni el
    Consentimiento, que son inmutables)."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Actualiza una entidad existente."""


class AppendOnlyRepository(ABC, Generic[T]):
    """Puerto SOLO-APPEND: solo inserta y lee, sin update ni delete.

    Coherente con la invariante de motor del audit log (trigger que rechaza
    UPDATE/DELETE, DD-07): el puerto NO expone esas operaciones, de modo que la
    inmutabilidad se respeta tanto en el contrato como en la base.
    """

    @abstractmethod
    async def append(self, entity: T) -> T:
        """Inserta una entrada nueva (unica operacion de escritura)."""

    @abstractmethod
    async def get(self, entity_id: str) -> T | None:
        """Recupera una entrada por id."""

    @abstractmethod
    async def list(self) -> list[T]:
        """Lista las entradas en orden de insercion."""
