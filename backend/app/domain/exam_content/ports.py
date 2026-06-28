"""Puerto (Protocol) del repositorio de contenido de examen."""

from __future__ import annotations

from typing import Protocol

from app.domain.exam_content.entities import ExamenContenido


class AbstractExamenContenidoRepository(Protocol):
    """Contrato que el repositorio de contenido de examen debe cumplir."""

    async def guardar(self, examen: ExamenContenido) -> ExamenContenido:
        """Persiste el examen y devuelve la entidad con id asignado."""
        ...

    async def obtener(self, examen_id: str) -> ExamenContenido | None:
        """Recupera un examen por id (con preguntas y opciones)."""
        ...
