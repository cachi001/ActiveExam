"""Catálogos de dominio: los valores, etiquetas y colores que muestra la UI.

POR QUÉ ESTÁN APARTE. Son CONSTANTES de dominio, no datos de nadie: los estados
que puede tener una entrega, los resultados que puede tener una nota y los
motivos por los que una nota queda retenida. No hay nada que proteger acá, y en
cambio los necesitan pantallas de TODOS los roles — incluido el alumno, que ve
su propia nota.

Vivían dentro del router de exam_content, que exige `gestionar_academico`: el
alumno recibía 403 y sus pantallas terminaban con las etiquetas escritas a mano,
que es exactamente lo que estos catálogos vinieron a evitar. Cuando el docente
veía "En revisión" sobre una nota, la pantalla del alumno seguía diciendo
"Aprobado" sobre la misma.

Sólo pide estar autenticado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.auth.dependencies import get_current_principal
from app.application.stats.labels import decisiones_para_ui
from app.domain.exam_content.estado_entrega import estados_para_ui
from app.domain.exam_content.resultado_nota import (
    resultados_para_ui,
    retenciones_para_ui,
)


def create_catalogos_router() -> APIRouter:
    router = APIRouter()

    @router.get("/resultados-nota", summary="Resultados posibles de una nota")
    async def listar_resultados(
        _: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[dict[str, str]]:
        return resultados_para_ui()

    @router.get("/estados-entrega", summary="Estados posibles de la entrega")
    async def listar_estados(
        _: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[dict[str, str]]:
        return estados_para_ui()

    @router.get("/decisiones", summary="Veredictos de revisión, con etiqueta y color")
    async def listar_decisiones(
        _: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[dict[str, str]]:
        return decisiones_para_ui()

    @router.get("/retenciones", summary="Motivos por los que una nota no se entrega")
    async def listar_retenciones(
        _: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[dict[str, str]]:
        return retenciones_para_ui()

    return router
