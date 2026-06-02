"""Repositorio de persistencia del modulo slim de proctoring.

Operaciones async sobre las tablas proctoring_session, proctoring_event y
proctoring_biometria. El calculo de score y discrepancias se hace aqui (o en
el servicio), NO en el router.

PRODUCCION (L2.5): el backend nunca sanciona ni emite veredicto disciplinario.
El score solo prioriza la cola de revision humana (D5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models.proctoring import (
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)


@dataclass
class SesionResumenData:
    """Datos de resumen de sesion para listar (con conteos calculados)."""

    id: str
    modo: str
    etiqueta: str | None
    creada_en: Any
    total_eventos: int
    total_discrepancias: int
    score: int


class ProctoringRepository:
    """CRUD async para las 3 tablas slim de proctoring."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -------------------------------------------------------------------------
    # Sessions
    # -------------------------------------------------------------------------

    async def crear_sesion(
        self,
        modo: str,
        exam_id: str | None = None,
        etiqueta: str | None = None,
    ) -> ProctoringSessionModel:
        """Crea y persiste una nueva sesion de proctoring slim."""
        sesion = ProctoringSessionModel(
            modo=modo,
            exam_id=exam_id,
            etiqueta=etiqueta,
        )
        self._db.add(sesion)
        await self._db.commit()
        await self._db.refresh(sesion)
        return sesion

    async def obtener_sesion(self, session_id: str) -> ProctoringSessionModel | None:
        """Obtiene una sesion por ID con sus eventos y biometria (eager load)."""
        stmt = (
            select(ProctoringSessionModel)
            .where(ProctoringSessionModel.id == session_id)
            .options(
                selectinload(ProctoringSessionModel.eventos),
                selectinload(ProctoringSessionModel.biometria),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def listar_sesiones(self) -> list[SesionResumenData]:
        """Lista todas las sesiones con total_eventos, total_discrepancias y score.

        El score se calcula con pesos por severidad (D5, alineado con riskWeights
        del frontend): critico=100, alto=50, medio=20, bajo=5. L2.5: solo prioriza.
        """
        pesos = {"critico": 100, "alto": 50, "medio": 20, "bajo": 5}

        # Subquery: eventos agrupados por session_id
        stmt = select(ProctoringSessionModel).order_by(
            ProctoringSessionModel.creada_en.desc()
        )
        result = await self._db.execute(stmt)
        sesiones = result.scalars().all()

        if not sesiones:
            return []

        session_ids = [s.id for s in sesiones]

        # Contar eventos por sesion
        count_stmt = (
            select(
                ProctoringEventModel.session_id,
                func.count(ProctoringEventModel.id).label("total"),
            )
            .where(ProctoringEventModel.session_id.in_(session_ids))
            .group_by(ProctoringEventModel.session_id)
        )
        count_result = await self._db.execute(count_stmt)
        total_por_sesion: dict[str, int] = {
            row.session_id: row.total for row in count_result
        }

        # Contar discrepancias por sesion
        disc_stmt = (
            select(
                ProctoringEventModel.session_id,
                func.count(ProctoringEventModel.id).label("discrepancias"),
            )
            .where(
                ProctoringEventModel.session_id.in_(session_ids),
                ProctoringEventModel.veredicto_reinferencia == "discrepancia",
            )
            .group_by(ProctoringEventModel.session_id)
        )
        disc_result = await self._db.execute(disc_stmt)
        disc_por_sesion: dict[str, int] = {
            row.session_id: row.discrepancias for row in disc_result
        }

        # Calcular score por sesion (SUM pesos por severidad)
        score_stmt = (
            select(
                ProctoringEventModel.session_id,
                ProctoringEventModel.severidad,
                func.count(ProctoringEventModel.id).label("cnt"),
            )
            .where(ProctoringEventModel.session_id.in_(session_ids))
            .group_by(ProctoringEventModel.session_id, ProctoringEventModel.severidad)
        )
        score_result = await self._db.execute(score_stmt)
        score_por_sesion: dict[str, int] = {}
        for row in score_result:
            sid = row.session_id
            peso = pesos.get(row.severidad, 0)
            score_por_sesion[sid] = score_por_sesion.get(sid, 0) + peso * row.cnt

        return [
            SesionResumenData(
                id=s.id,
                modo=s.modo,
                etiqueta=s.etiqueta,
                creada_en=s.creada_en,
                total_eventos=total_por_sesion.get(s.id, 0),
                total_discrepancias=disc_por_sesion.get(s.id, 0),
                score=score_por_sesion.get(s.id, 0),
            )
            for s in sesiones
        ]

    async def eliminar_sesion(self, session_id: str) -> bool:
        """Elimina una sesion por ID. Los eventos y biometria se borran por FK CASCADE.

        Devuelve True si existia y se elimino, False si no existia.
        """
        sesion = await self._db.get(ProctoringSessionModel, session_id)
        if sesion is None:
            return False
        await self._db.delete(sesion)
        await self._db.commit()
        return True

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    async def crear_evento(
        self,
        session_id: str,
        tipo: str,
        severidad: str,
        ts_cliente: datetime,
        payload: dict | None = None,
        screenshot_b64: str | None = None,
        screenshot_sha256: str | None = None,
        face_count_cliente: int | None = None,
        face_count_servidor: int | None = None,
        veredicto_reinferencia: str = "no_evaluado",
    ) -> ProctoringEventModel:
        """Persiste un evento con todos los campos de re-inferencia e integridad."""
        evento = ProctoringEventModel(
            session_id=session_id,
            tipo=tipo,
            severidad=severidad,
            ts_cliente=ts_cliente,
            payload=payload,
            screenshot_b64=screenshot_b64,
            screenshot_sha256=screenshot_sha256,  # integridad liviana (D9)
            face_count_cliente=face_count_cliente,
            face_count_servidor=face_count_servidor,
            veredicto_reinferencia=veredicto_reinferencia,
        )
        self._db.add(evento)
        await self._db.commit()
        await self._db.refresh(evento)
        return evento

    # -------------------------------------------------------------------------
    # Biometria
    # -------------------------------------------------------------------------

    async def guardar_biometria(
        self,
        session_id: str,
        liveness_ok: bool,
        retos_resueltos: list,
        resultado: str,
        embedding: str | None = None,
    ) -> ProctoringBiometriaModel:
        """Persiste el resultado biometrico de una sesion."""
        bio = ProctoringBiometriaModel(
            session_id=session_id,
            liveness_ok=liveness_ok,
            retos_resueltos=retos_resueltos,
            resultado=resultado,
            embedding=embedding,
        )
        self._db.add(bio)
        await self._db.commit()
        await self._db.refresh(bio)
        return bio
