"""Servicio de write-back de nota a Moodle (C-69, D10, tareas 7.7-7.12).

D10:
- Estado persistido (pendiente/enviado/fallido) ligado a la sesión.
- Idempotente: reintento de nota ya 'enviado' NO duplica el push.
- Reintenable: fallo de red deja el estado como 'fallido' con la nota preservada.
- Si Moodle no responde → la finalización no se bloquea; estado queda 'fallido'.
- Audit log por intento, sin el token.
- Nota académica SÓLO de respuestas correctas (L2.5).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.moodle.identity_mapper import IdentityResolutionError, MoodleIdentityMapper
from app.infrastructure.moodle.client import MoodleGradeWriteError, MoodleRestClient
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
)

logger = logging.getLogger(__name__)


class WritebackEstado(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"


async def _get_estado_for_session(
    db: AsyncSession, session_id: str
) -> MoodleWritebackEstadoModel | None:
    result = await db.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    return result.scalar_one_or_none()


async def persistir_nota_pendiente(
    *,
    db: AsyncSession,
    session_id: str,
    nota: float,
    alumno_idnumber: str,
    alumno_email: str,
    moodle_courseid: int | None = None,
    moodle_cmid: int | None = None,
) -> MoodleWritebackEstadoModel:
    """Crea (o actualiza) el registro de estado en 'pendiente' con la nota calculada.

    Standalone — NO requiere cliente Moodle: sirve cuando el write-back está
    deshabilitado (Moodle sin configurar) pero la nota igual debe persistirse para
    que el admin la vea/sincronice luego (decisión de producto: envío manual).

    Idempotente: si ya existe un estado 'enviado' para esta sesión, lo devuelve tal
    cual (no sobrescribe una nota ya enviada).
    """
    existing = await _get_estado_for_session(db, session_id)

    if existing is not None and existing.estado == WritebackEstado.ENVIADO:
        return existing

    if existing is None:
        estado = MoodleWritebackEstadoModel(
            session_id=session_id,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
            nota=nota,
            estado=WritebackEstado.PENDIENTE,
            intento=0,
            moodle_courseid=moodle_courseid,
            moodle_cmid=moodle_cmid,
        )
        db.add(estado)
        await db.flush()
        return estado

    # Ya existe (fallido o pendiente) — actualizar nota y volver a pendiente
    existing.nota = nota
    existing.alumno_idnumber = alumno_idnumber
    existing.alumno_email = alumno_email
    existing.estado = WritebackEstado.PENDIENTE
    await db.flush()
    return existing


class MoodleWritebackService:
    """Orquesta el write-back de la nota académica a Moodle con idempotencia y auditoría.

    El token NO se almacena ni se loguea — vive sólo en MoodleRestClient.config.
    """

    def __init__(self, moodle_client: MoodleRestClient) -> None:
        self._client = moodle_client
        self._mapper = MoodleIdentityMapper(moodle_client=moodle_client)

    async def iniciar_writeback(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        nota: float,
        alumno_idnumber: str,
        alumno_email: str,
    ) -> MoodleWritebackEstadoModel:
        """Crea (o actualiza) el registro de estado en 'pendiente' con la nota calculada.

        Si ya existe un estado 'enviado' para esta sesión, lo devuelve tal cual
        (idempotente: no sobrescribe una nota ya enviada).
        """
        return await persistir_nota_pendiente(
            db=db,
            session_id=session_id,
            nota=nota,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
            moodle_courseid=self._client._config.courseid,
            moodle_cmid=self._client._config.cmid,
        )

    async def ejecutar_writeback(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        nota: float,
        alumno_idnumber: str,
        alumno_email: str,
    ) -> None:
        """Ejecuta el write-back completo: estado → resolución de identidad → push.

        Idempotente: si ya está 'enviado', no hace nada.
        NO propaga excepciones de Moodle: si falla, persiste el estado 'fallido'
        y audita el error. La finalización del examen NO se bloquea.
        """
        # Paso 1: persistir estado inicial (idempotente)
        estado = await self.iniciar_writeback(
            db=db,
            session_id=session_id,
            nota=nota,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
        )

        if estado.estado == WritebackEstado.ENVIADO:
            return  # ya enviado, no duplicar

        # Paso 2: resolver identidad en Moodle
        moodle_userid: int | None = None
        try:
            moodle_userid = await self._mapper.resolve(
                idnumber=alumno_idnumber,
                email=alumno_email,
            )
        except (IdentityResolutionError, Exception) as exc:
            await self._registrar_fallo(
                db=db,
                estado=estado,
                moodle_userid=None,
                error=str(exc),
            )
            return

        # Paso 3: push de la nota a Moodle
        try:
            await self._client.write_grade(
                moodle_userid=moodle_userid,
                nota=float(estado.nota),
            )
        except MoodleGradeWriteError as exc:
            await self._registrar_fallo(
                db=db,
                estado=estado,
                moodle_userid=moodle_userid,
                error=str(exc),
            )
            return

        # Paso 4: marcar como enviado y auditar éxito
        estado.estado = WritebackEstado.ENVIADO
        estado.moodle_userid = moodle_userid
        estado.intento += 1
        estado.error_detalle = None
        await db.flush()

        await self._auditar(
            db=db,
            session_id=session_id,
            estado=estado,
            moodle_userid=moodle_userid,
            resultado="ok",
            error_detalle=None,
        )

    async def _registrar_fallo(
        self,
        *,
        db: AsyncSession,
        estado: MoodleWritebackEstadoModel,
        moodle_userid: int | None,
        error: str,
    ) -> None:
        """Marca el estado como 'fallido' y audita el intento sin el token."""
        # Limpiar el token del mensaje de error por si acaso
        error_limpio = self._sanitizar_error(error)

        estado.estado = WritebackEstado.FALLIDO
        estado.intento += 1
        estado.moodle_userid = moodle_userid
        estado.error_detalle = error_limpio
        await db.flush()

        await self._auditar(
            db=db,
            session_id=estado.session_id,
            estado=estado,
            moodle_userid=moodle_userid,
            resultado="error",
            error_detalle=error_limpio,
        )

    async def _auditar(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        estado: MoodleWritebackEstadoModel,
        moodle_userid: int | None,
        resultado: str,
        error_detalle: str | None,
    ) -> None:
        """Inserta una entrada en el audit log. El token NUNCA se registra."""
        audit = MoodleWritebackAuditModel(
            session_id=session_id,
            alumno_idnumber=estado.alumno_idnumber,
            nota=estado.nota,
            moodle_courseid=estado.moodle_courseid,
            moodle_cmid=estado.moodle_cmid,
            moodle_userid=moodle_userid,
            resultado=resultado,
            error_detalle=error_detalle,
        )
        db.add(audit)
        await db.flush()

    def _sanitizar_error(self, error: str) -> str:
        """Elimina el token del mensaje de error antes de guardarlo."""
        token = self._client._config.ws_token
        if token and token in error:
            error = error.replace(token, "[REDACTED]")
        return error

    async def _get_estado(
        self, db: AsyncSession, session_id: str
    ) -> MoodleWritebackEstadoModel | None:
        result = await db.execute(
            select(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == session_id
            )
        )
        return result.scalar_one_or_none()
