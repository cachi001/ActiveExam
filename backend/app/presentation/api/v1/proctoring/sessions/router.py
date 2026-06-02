"""Router de sesiones de proctoring slim.

POST /sessions → 201
GET  /sessions → 200
GET  /sessions/{id} → 200/404

Sin auth (D7 — alcance demo). La session_factory y el db_dependency se
inyectan desde el router padre para evitar acoplar este router a SlimSettings.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import session_service
from app.application.proctoring.scoring import calcular_score
from app.presentation.api.v1.proctoring.sessions.schemas import (
    BiometriaDetalle,
    CrearSesionIn,
    CrearSesionOut,
    EventoDetalle,
    SesionDetalle,
    SesionResumen,
)


def create_sessions_router(get_db) -> APIRouter:
    """Factory del router de sesiones. Recibe la dependencia de DB inyectada."""
    router = APIRouter()

    @router.post(
        "/sessions",
        status_code=http_status.HTTP_201_CREATED,
        response_model=CrearSesionOut,
        summary="Crear sesion de proctoring",
    )
    async def crear_sesion(
        body: CrearSesionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> CrearSesionOut:
        """Crea una nueva sesion de proctoring slim."""
        sesion = await session_service.crear_sesion(
            db=db,
            modo=body.modo,
            exam_id=body.exam_id,
            etiqueta=body.etiqueta,
        )
        return CrearSesionOut(id=sesion.id, creada_en=sesion.creada_en)

    @router.get(
        "/sessions",
        response_model=list[SesionResumen],
        summary="Listar sesiones con score y discrepancias",
    )
    async def listar_sesiones(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[SesionResumen]:
        """Lista todas las sesiones con total_eventos, total_discrepancias y score."""
        sesiones = await session_service.listar_sesiones(db)
        return [
            SesionResumen(
                id=s.id,
                modo=s.modo,
                etiqueta=s.etiqueta,
                creada_en=s.creada_en,
                total_eventos=s.total_eventos,
                total_discrepancias=s.total_discrepancias,
                score=s.score,
            )
            for s in sesiones
        ]

    @router.get(
        "/sessions/{session_id}",
        response_model=SesionDetalle,
        summary="Detalle de sesion para revision del proctor",
    )
    async def obtener_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> SesionDetalle:
        """Detalle completo de una sesion con eventos y biometria (vista del proctor)."""
        sesion = await session_service.detalle_sesion(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )

        score = calcular_score(sesion.eventos)

        eventos = [
            EventoDetalle(
                id=e.id,
                tipo=e.tipo,
                severidad=e.severidad,
                ts_cliente=e.ts_cliente,
                ts_backend=e.ts_backend,
                payload=e.payload,
                screenshot_base64=e.screenshot_b64,
                screenshot_sha256=e.screenshot_sha256,
                face_count_cliente=e.face_count_cliente,
                face_count_servidor=e.face_count_servidor,
                veredicto_reinferencia=e.veredicto_reinferencia,
            )
            for e in sesion.eventos
        ]

        biometria = None
        if sesion.biometria is not None:
            bio = sesion.biometria
            biometria = BiometriaDetalle(
                liveness_ok=bio.liveness_ok,
                retos_resueltos=bio.retos_resueltos,
                resultado=bio.resultado,
                registrada_en=bio.registrada_en,
            )

        return SesionDetalle(
            id=sesion.id,
            modo=sesion.modo,
            etiqueta=sesion.etiqueta,
            creada_en=sesion.creada_en,
            finalizada_en=sesion.finalizada_en,
            score=score,
            eventos=eventos,
            biometria=biometria,
        )

    return router
