"""Routers de exam_content (FastAPI, C-69).

Este módulo agrega los sub-routers de exam_content tras partir el god-file:
- `create_periodos_router` / `create_exam_content_router` (catálogo admin) — acá.
- `create_exam_taking_router` (rendición del alumno) — en ./taking_router, re-exportado.
- Helpers compartidos (gate staff / mapeo de resumen) — en ./_shared.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
)

from app.presentation.api.v1.exam_content.catalog_router import create_exam_content_router
from app.presentation.api.v1.exam_content.schemas import (
    PeriodoEnum,
)
from app.presentation.api.v1.exam_content.taking_router import create_exam_taking_router

__all__ = [
    "create_exam_content_router",
    "create_exam_taking_router",
    "create_periodos_router",
]


def create_periodos_router() -> APIRouter:
    """Router público (sin auth) que expone los valores válidos de período."""
    router = APIRouter()

    @router.get("/periodos", response_model=list[dict], tags=["exam-content"])
    async def listar_periodos():
        """Devuelve los períodos académicos válidos para una comisión."""
        return [
            {"value": PeriodoEnum.primer_cuatrimestre, "label": "1er cuatrimestre"},
            {"value": PeriodoEnum.segundo_cuatrimestre, "label": "2do cuatrimestre"},
        ]

    return router
