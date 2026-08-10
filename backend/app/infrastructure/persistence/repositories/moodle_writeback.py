"""Repositorio para respuestas del alumno (C-69, sección 7)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.moodle_writeback import (
    RespuestaAlumnoClozeModel,
    RespuestaAlumnoModel,
)


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

    async def guardar_respuestas_cloze(
        self,
        session_id: str,
        respuestas: list[dict],
    ) -> int:
        """Guarda respuestas de blanks cloze/ddwtos (upsert por session_id+blank_id).

        Cada item: {"pregunta_id": ..., "blank_id": ..., "valor": ...}. ``valor`` es
        el id de la opción elegida (blank MULTICHOICE) o el texto libre (SHORTANSWER).
        """
        if not respuestas:
            return 0

        count = 0
        for resp in respuestas:
            stmt = (
                insert(RespuestaAlumnoClozeModel)
                .values(
                    session_id=session_id,
                    pregunta_id=resp["pregunta_id"],
                    blank_id=resp["blank_id"],
                    valor=resp["valor"],
                )
                .on_conflict_do_update(
                    constraint="uq_respuesta_alumno_cloze_sesion_blank",
                    set_={"valor": resp["valor"]},
                )
            )
            await self._db.execute(stmt)
            count += 1

        await self._db.flush()
        return count

    async def listar_cloze_por_sesion(self, session_id: str) -> list[RespuestaAlumnoClozeModel]:
        result = await self._db.execute(
            select(RespuestaAlumnoClozeModel).where(
                RespuestaAlumnoClozeModel.session_id == session_id
            )
        )
        return list(result.scalars().all())
