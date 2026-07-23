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
    moodle_component: str | None = None,
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
            moodle_component=moodle_component,
        )
        db.add(estado)
        await db.flush()
        return estado

    # Ya existe (fallido o pendiente) — actualizar nota y volver a pendiente
    # NO tocar el destino (courseid/cmid/component): se fija en la CREATE (al finalizar
    # la sesión) y se preserva. ejecutar_writeback re-llama iniciar sin destino, y no
    # debe pisar el component por-examen con el global. Igual que courseid/cmid.
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

    async def _nota_maxima_del_examen(
        self, db: AsyncSession, session_id: str
    ) -> float | None:
        """Escala sobre la que ActiveExam califico esta sesion (``nota_maxima``).

        Viaja al cliente para convertir la nota a la escala del item de Moodle: sin
        ella, un 8 sobre 10 se escribia como 8 sobre 100. Se resuelve por la sesion
        porque `moodle_writeback_estado` guarda la nota pero no su escala.

        None si no se puede determinar — el cliente entonces envia sin convertir
        (comportamiento previo), que es lo correcto para una sesion sin examen
        asociado (no hay escala de origen que convertir).
        """
        from app.infrastructure.persistence.models.exam_content import (
            ExamenContenidoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        try:
            result = await db.execute(
                select(ExamenContenidoModel.nota_maxima)
                .join(
                    ProctoringSessionModel,
                    ProctoringSessionModel.examen_contenido_id == ExamenContenidoModel.id,
                )
                .where(ProctoringSessionModel.id == session_id)
            )
            nota_maxima = result.scalar_one_or_none()
        except Exception:  # noqa: BLE001 — sin escala se envia sin convertir
            return None
        return float(nota_maxima) if nota_maxima else None

    async def iniciar_writeback(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        nota: float,
        alumno_idnumber: str,
        alumno_email: str,
        moodle_courseid: int | None = None,
        moodle_cmid: int | None = None,
        moodle_component: str | None = None,
    ) -> MoodleWritebackEstadoModel:
        """Crea (o actualiza) el registro de estado en 'pendiente' con la nota calculada.

        D12 (parte B): moodle_courseid/cmid son el destino POR EXAMEN (autoritativo).
        Si vienen None, se cae al global del cliente (compat con exámenes sin destino).
        C-73: moodle_component ('mod_assign'|'mod_quiz') idem — None cae al global.

        Si ya existe un estado 'enviado' para esta sesión, lo devuelve tal cual
        (idempotente: no sobrescribe una nota ya enviada).
        """
        target_courseid = (
            moodle_courseid if moodle_courseid is not None else self._client._config.courseid
        )
        target_cmid = (
            moodle_cmid if moodle_cmid is not None else self._client._config.cmid
        )
        target_component = (
            moodle_component if moodle_component is not None else self._client._config.component
        )
        return await persistir_nota_pendiente(
            db=db,
            session_id=session_id,
            nota=nota,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
            moodle_courseid=target_courseid,
            moodle_cmid=target_cmid,
            moodle_component=target_component,
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

        # Paso 3: push de la nota a Moodle. Destino POR EXAMEN persistido en el estado
        # (D12); si está NULL, write_grade cae al global de config.
        try:
            await self._client.write_grade(
                moodle_userid=moodle_userid,
                nota=float(estado.nota),
                courseid=estado.moodle_courseid,
                cmid=estado.moodle_cmid,
                component=estado.moodle_component,
                # Escala de ORIGEN: el cliente la usa para convertir a la del item
                # de Moodle (que suele ser 100). Sin esto un 8/10 iba como 8/100.
                nota_maxima=await self._nota_maxima_del_examen(db, session_id),
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

    async def anular_nota(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        actor: str,
        motivo: str,
    ) -> bool:
        """Escribe **0** en Moodle como efecto de una anulacion por fraude (hook c-18).

        Es el acto COMPENSATORIO de la resolucion `anulado_por_fraude`: sin esto la
        anulacion queda en ActiveExam y el alumno conserva en la libreta de Moodle la
        nota que ya se le habia sincronizado.

        A diferencia de ``ejecutar_writeback``, este metodo NO respeta el corte por
        'enviado' — al contrario, su caso normal es pisar una nota ya enviada. Por eso
        es un metodo aparte y no un parametro: forzar un reenvio no puede quedar al
        alcance del camino normal, donde la idempotencia es justamente la proteccion.

        APPEND-ONLY donde importa: la fila de `moodle_writeback_estado` refleja el
        estado VIGENTE (nota 0), y el historial completo (la nota original, este acto
        y su resultado) queda en `moodle_writeback_audit`, que solo acumula.

        Nunca propaga excepciones: la resolucion humana ya esta registrada y es
        inmutable; si Moodle no responde, se persiste 'fallido' con el detalle y el
        admin puede reintentar desde la pantalla de sincronizacion.

        Returns:
            True si Moodle confirmo el 0; False si no habia nota que anular o fallo.
        """
        estado = await self._get_estado(db, session_id)
        if estado is None:
            # Nunca hubo nota sincronizada para esta sesion: no hay nada que anular.
            return False

        nota_previa = float(estado.nota)
        estado.nota = 0
        estado.estado = WritebackEstado.PENDIENTE
        await db.flush()

        try:
            moodle_userid = await self._mapper.resolve(
                idnumber=estado.alumno_idnumber,
                email=estado.alumno_email,
            )
        except Exception as exc:  # noqa: BLE001 — identidad no resoluble: queda fallido
            await self._registrar_fallo(
                db=db, estado=estado, moodle_userid=None, error=str(exc)
            )
            return False

        try:
            # 0 es 0 en cualquier escala, pero se pasa igual para que la anulacion
            # recorra EXACTAMENTE el mismo camino que un envio normal: si mañana la
            # nota de anulacion deja de ser 0, no hay que acordarse de este detalle.
            await self._client.write_grade(
                moodle_userid=moodle_userid,
                nota=0.0,
                courseid=estado.moodle_courseid,
                cmid=estado.moodle_cmid,
                component=estado.moodle_component,
                nota_maxima=await self._nota_maxima_del_examen(db, session_id),
            )
        except MoodleGradeWriteError as exc:
            await self._registrar_fallo(
                db=db, estado=estado, moodle_userid=moodle_userid, error=str(exc)
            )
            return False

        estado.estado = WritebackEstado.ENVIADO
        estado.moodle_userid = moodle_userid
        estado.intento += 1
        estado.error_detalle = None
        await db.flush()

        # El resultado deja rastro de QUE se anulo, QUIEN y POR QUE: sin la nota
        # previa el registro no permitiria reconstruir el efecto del acto.
        await self._auditar(
            db=db,
            session_id=session_id,
            estado=estado,
            moodle_userid=moodle_userid,
            resultado="anulado",
            error_detalle=(
                f"Anulacion por fraude: nota {nota_previa:g} -> 0. "
                f"actor={actor} | motivo={motivo}"
            ),
        )
        return True

    async def restituir_nota(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        actor: str,
        motivo: str,
    ) -> float | None:
        """Devuelve a Moodle la nota REAL de un examen cuya anulación se revirtió.

        Es el espejo de ``anular_nota``: si la anulación no llegaba a la libreta el
        alumno conservaba una nota que ya no le correspondía, y si la restitución no
        llega, se queda con un 0 que tampoco le corresponde — con el agravante de
        que acá ya se le dio la razón.

        La nota se RECALCULA desde las respuestas persistidas en vez de leerla del
        historial: el cálculo es la fuente de verdad y no depende de parsear el
        texto de una entrada de auditoría. Si el examen se recorrigió mientras
        tanto, restituye la nota vigente, que es la correcta.

        Como en la anulación, no propaga excepciones: el acto compensatorio ya
        quedó asentado en el audit log y es lo que define el estado efectivo de la
        nota; si Moodle falla, queda 'fallido' y se reintenta desde la pantalla de
        sincronización.

        Returns:
            La nota restituida, o None si no había nada que restituir o falló.
        """
        from app.application.moodle.grade_calculator import (
            RespuestaAlumno,
            calcular_nota_academica,
        )
        from app.infrastructure.persistence.models.moodle_writeback import (
            RespuestaAlumnoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        estado = await self._get_estado(db, session_id)
        if estado is None:
            return None

        sesion = await db.get(ProctoringSessionModel, session_id)
        if sesion is None or not sesion.examen_contenido_id:
            return None

        respuestas = [
            RespuestaAlumno(
                pregunta_id=r.pregunta_id, opcion_elegida_id=r.opcion_elegida_id
            )
            for r in (
                await db.execute(
                    select(RespuestaAlumnoModel).where(
                        RespuestaAlumnoModel.session_id == session_id
                    )
                )
            )
            .scalars()
            .all()
        ]
        nota = await calcular_nota_academica(
            db=db,
            examen_contenido_id=sesion.examen_contenido_id,
            respuestas=respuestas,
        )

        nota_anulada = float(estado.nota)
        estado.nota = nota
        estado.estado = WritebackEstado.PENDIENTE
        await db.flush()

        try:
            moodle_userid = await self._mapper.resolve(
                idnumber=estado.alumno_idnumber,
                email=estado.alumno_email,
            )
        except Exception as exc:  # noqa: BLE001
            await self._registrar_fallo(
                db=db, estado=estado, moodle_userid=None, error=str(exc)
            )
            return None

        try:
            await self._client.write_grade(
                moodle_userid=moodle_userid,
                nota=nota,
                courseid=estado.moodle_courseid,
                cmid=estado.moodle_cmid,
                component=estado.moodle_component,
                nota_maxima=await self._nota_maxima_del_examen(db, session_id),
            )
        except MoodleGradeWriteError as exc:
            await self._registrar_fallo(
                db=db, estado=estado, moodle_userid=moodle_userid, error=str(exc)
            )
            return None

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
            resultado="restituido",
            error_detalle=(
                f"Restitucion tras revertir la anulacion: nota {nota_anulada:g} -> "
                f"{nota:g}. actor={actor} | motivo={motivo}"
            ),
        )
        return nota

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
