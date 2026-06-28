"""Repositorio para respuestas del alumno (C-69, sección 7)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.moodle_writeback import RespuestaAlumnoModel


class RespuestaAlumnoRepository:
    """Persiste y recupera las respuestas del alumno por sesión."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def guardar_respuestas(
        self,
        session_id: str,
        respuestas: list[dict],
    ) -> int:
        """Guarda respuestas (upsert por session_id+pregunta_id). Devuelve N guardadas."""
        if not respuestas:
            return 0

        count = 0
        for resp in respuestas:
            stmt = (
                insert(RespuestaAlumnoModel)
                .values(
                    session_id=session_id,
                    pregunta_id=resp["pregunta_id"],
                    opcion_elegida_id=resp["opcion_elegida_id"],
                )
                .on_conflict_do_update(
                    constraint="uq_respuesta_alumno_sesion_pregunta",
                    set_={"opcion_elegida_id": resp["opcion_elegida_id"]},
                )
            )
            await self._db.execute(stmt)
            count += 1

        await self._db.flush()
        return count

    async def listar_por_sesion(self, session_id: str) -> list[RespuestaAlumnoModel]:
        result = await self._db.execute(
            select(RespuestaAlumnoModel).where(
                RespuestaAlumnoModel.session_id == session_id
            )
        )
        return list(result.scalars().all())
