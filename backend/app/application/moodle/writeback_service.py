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

from app.application.moodle.credencial_docente_service import ESTADO_ACTIVA
from app.application.moodle.identity_mapper import IdentityResolutionError, MoodleIdentityMapper
from app.infrastructure.moodle.client import MoodleGradeWriteError, MoodleRestClient
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
)

logger = logging.getLogger(__name__)

#: Por que `_credencial_para` no trajo un token, y que decirle al docente en cada
#: caso (C-73 §12). Los tres primeros ya existian implicitos en el mensaje unico
#: de antes; `caida` y `vencida` se separan porque el remedio es el mismo (volver
#: a conectar) pero la CAUSA no: una la tumbo Moodle, la otra vencio por tiempo
#: sin que nadie la haya rechazado.
MENSAJE_POR_MOTIVO_BLOQUEO: dict[str, str] = {
    "sin_docente": (
        "sin_credencial_docente: la comisión no tiene docente a cargo con "
        "su cuenta del campus conectada. La nota no se envía para que no "
        "quede en la libreta sin responsable."
    ),
    "sin_credencial_docente": (
        "sin_credencial_docente: la comisión no tiene docente a cargo con "
        "su cuenta del campus conectada. La nota no se envía para que no "
        "quede en la libreta sin responsable."
    ),
    "caida": (
        "credencial_caida: el campus dejó de aceptar la conexión del docente. "
        "Volvé a conectarte en Configuración → Campus (Moodle) para reintentar."
    ),
    "vencida": (
        "credencial_vencida: pasaron 30 días desde que el docente conectó su "
        "cuenta del campus. Por seguridad, tiene que volver a cargar su "
        "contraseña en Configuración → Campus (Moodle) — no fue el campus quien "
        "rechazó la conexión, venció por tiempo."
    ),
}


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


def _es_token_invalido(exc: Exception) -> bool:
    """``True`` si Moodle rechazó la CREDENCIAL (no el dato).

    Se mira el texto porque el cliente ya normaliza el error de Moodle a
    ``MoodleGradeWriteError``. Distinguirlo importa: un token inválido se arregla
    recargando la credencial, mientras que un destino mal configurado no.
    """
    texto = str(exc).lower()
    # `invalidtoken` es el errorcode; el resto son los textos que devuelve Moodle
    # segun el idioma del campus. El de campustest (es_AR) es "Ficha (token) no
    # valida - ficha no encontrada": mirar solo el errorcode en ingles no alcanza.
    marcas = (
        "invalidtoken",
        "accessexception",
        "ficha (token)",
        "token no",
        "invalid token",
    )
    return any(m in texto for m in marcas)


class MoodleWritebackService:
    """Orquesta el write-back de la nota académica a Moodle con idempotencia y auditoría.

    El token NO se almacena ni se loguea — vive sólo en MoodleRestClient.config.
    """

    def __init__(
        self,
        moodle_client: MoodleRestClient,
        credencial_docente=None,
    ) -> None:
        self._client = moodle_client
        self._mapper = MoodleIdentityMapper(moodle_client=moodle_client)
        # C-73 §10.4: CredencialDocenteService. Sin él, `ejecutar_writeback` no puede
        # identificar al docente y retiene la nota en vez de mandarla sin dueño.
        # La anulación por fraude (`anular_nota`) SÍ sigue usando la institucional: la
        # decide un revisor, no el docente, y firmarla con la credencial del profesor
        # atribuiría a otra persona una sanción que no tomó.
        self._cred_docente = credencial_docente

    async def _credencial_para(
        self, db: AsyncSession, session_id: str
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Credencial del DOCENTE con la que se devuelve ESTA nota (C-73 §10.4).

        Deriva sesion -> examen -> comision -> TUTORES (tabla puente
        `comision_tutor`, N:M desde c-79) y devuelve
        ``(token, docente_id, nombre_visible, motivo_bloqueo)``. ``motivo_bloqueo``
        es ``None`` cuando hay token; si no, una de
        ``"sin_docente"|"sin_credencial_docente"|"caida"|"vencida"`` (C-73 §12) —
        indexa a `MENSAJE_POR_MOTIVO_BLOQUEO` para el mensaje que ve el docente.

        ``nombre_visible`` es "Nombre Apellido" — es lo que termina en la columna
        *Fuente* de la libreta de Moodle, y ahi lo lee una PERSONA. Un legajo obliga a
        ir a buscar de quien es; el nombre se entiende solo. Cae al legajo unicamente
        si el usuario no tiene nombre cargado.

        NO HAY RESPALDO INSTITUCIONAL PARA ESTE CAMINO. Si el docente no tiene
        credencial usable, la nota NO se manda: sin identidad del docente, la nota
        llega a la libreta sin dueno y eso es exactamente el problema que este cambio
        vino a resolver. Peor aun, saldria en silencio: el docente creeria que la
        mando el. Se retiene y se muestra por que (motivo `sin_credencial_docente`),
        que es un bloqueo visible en vez de una firma equivocada.
        """
        if self._cred_docente is None:
            return None, None, None, "sin_docente"

        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
            ProctoringSessionModel,
        )

        from app.infrastructure.persistence.models.transactional import UsuarioModel

        from app.infrastructure.persistence.models.comision_tutor import (
            ComisionTutorModel,
        )

        # c-78 (deuda c-79): los tutores salen de la tabla puente, NO de
        # `comision.docente_id`. Esa columna quedó congelada en la migración 0086 y
        # ningún endpoint la escribe desde entonces, así que leerla dejaba sin nota
        # a toda comisión creada o gestionada desde la UI actual.
        #
        # Orden: el primero que quedó a cargo, con desempate por `tutor_id`.
        # DETERMINÍSTICO a propósito — dos sincronizaciones seguidas de la misma
        # nota tienen que salir firmadas por la misma persona, si no la columna
        # *Fuente* de la libreta de Moodle cambiaría sola.
        tutores = (
            await db.execute(
                select(
                    ComisionTutorModel.tutor_id,
                    UsuarioModel.username,
                    UsuarioModel.nombre,
                    UsuarioModel.apellido,
                )
                .select_from(ProctoringSessionModel)
                .join(
                    ExamenContenidoModel,
                    # OJO: la columna es `examen_contenido_id`, no `examen_id`.
                    ExamenContenidoModel.id
                    == ProctoringSessionModel.examen_contenido_id,
                )
                .join(
                    ComisionModel,
                    ComisionModel.id == ExamenContenidoModel.comision_id,
                )
                .join(
                    ComisionTutorModel,
                    ComisionTutorModel.comision_id == ComisionModel.id,
                )
                .outerjoin(UsuarioModel, UsuarioModel.id == ComisionTutorModel.tutor_id)
                .where(ProctoringSessionModel.id == session_id)
                .order_by(ComisionTutorModel.created_at, ComisionTutorModel.tutor_id)
            )
        ).all()

        if not tutores:
            return None, None, None, "sin_docente"

        def _visible(legajo, nombre, apellido) -> str:
            # "Nombre Apellido"; si el usuario no los tiene cargados, el legajo.
            return " ".join(p for p in (nombre, apellido) if p).strip() or legajo

        # El modelo de pertenencia es SIMÉTRICO: cualquier tutor de la comisión está
        # igual de habilitado (mismo criterio que el sistema de referencia, cuya
        # tabla puente tampoco tiene tutor "principal"). Por eso, que el primero no
        # haya conectado su cuenta no puede retener la nota si otro sí la tiene.
        primer_motivo: str | None = None
        primer_docente: str | None = None
        primer_visible: str | None = None

        for tutor_id, legajo, nombre, apellido in tutores:
            visible = _visible(legajo, nombre, apellido)
            cred_estado = await self._cred_docente.estado(tutor_id)
            if not cred_estado.configurada:
                motivo = "sin_credencial_docente"
            elif cred_estado.estado != ESTADO_ACTIVA:
                # `caida` o `vencida` (C-73 §12) — motivo distinto, remedio igual
                # (reconectar), pero el mensaje tiene que decir la causa correcta.
                motivo = cred_estado.estado
            else:
                token = await self._cred_docente.token_de(tutor_id)
                if token:
                    return token, tutor_id, visible, None
                motivo = "sin_credencial_docente"

            # Se recuerda el motivo del PRIMER tutor: es el que se le muestra al
            # docente si ninguno termina teniendo credencial usable. El primero es
            # el más probable responsable, así que es a quien hay que ir a buscar.
            if primer_motivo is None:
                primer_motivo, primer_docente, primer_visible = (
                    motivo,
                    tutor_id,
                    visible,
                )

        return None, primer_docente, primer_visible, primer_motivo

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
        # Destino: SOLO el del examen. No hay fallback a un destino global — no
        # existe un curso "por defecto" correcto para todos los examenes, y caer a
        # uno escribia la nota en la libreta de otra materia sin avisar. Sin destino
        # la nota se persiste igual (queda 'pendiente' y visible), pero no se manda.
        target_courseid = moodle_courseid
        target_cmid = moodle_cmid
        # `component` SI tiene un default institucional razonable (con que tipo de
        # actividad trabaja la institucion); el examen puede sobreescribirlo.
        cfg = await self._client._resolver_config()
        target_component = (
            moodle_component if moodle_component is not None else cfg.component
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

        # Paso 2: credencial del DOCENTE a cargo de la comision.
        #
        # C-73 §10.4: la nota SIEMPRE sale con la credencial del docente. No hay
        # respaldo institucional para este camino, y es a proposito: una nota escrita
        # con la cuenta de servicio llega a la libreta sin dueno identificable —el
        # problema que este cambio vino a resolver— y ademas sale en silencio, con el
        # docente creyendo que la mando el.
        #
        # VA ANTES DEL MAPEO DE IDENTIDAD (C-73 Fase 2) por dos razones: el mapeo
        # ahora se hace CON este token, y si no hay credencial no tiene sentido
        # molestar a Moodle para despues retener la nota igual.
        token_docente, docente_id, docente_nombre, motivo_bloqueo = (
            await self._credencial_para(db, session_id)
        )

        if not token_docente:
            # Bloqueo VISIBLE en vez de firma equivocada. La nota queda pendiente y
            # la pantalla de resultados explica por que — el motivo correcto, no
            # siempre "nunca conectó" (C-73 §12: puede haberse caído o vencido).
            # Se destraba sola en cuanto el docente (re)conecta su cuenta.
            await self._registrar_fallo(
                db=db,
                estado=estado,
                moodle_userid=None,
                error=MENSAJE_POR_MOTIVO_BLOQUEO.get(
                    motivo_bloqueo or "sin_credencial_docente",
                    MENSAJE_POR_MOTIVO_BLOQUEO["sin_credencial_docente"],
                ),
            )
            return

        # Paso 3: resolver la identidad del alumno en Moodle.
        #
        # C-73 Fase 2: con el curso del examen y el token del docente, la resolucion
        # se hace entre los MATRICULADOS del curso — sin credencial institucional (que
        # en campustest esta muerta) y con el alcance que impone Moodle: el docente no
        # ve cursos donde no da clase.
        moodle_userid: int | None = None
        try:
            moodle_userid = await self._mapper.resolve(
                idnumber=alumno_idnumber,
                email=alumno_email,
                courseid=estado.moodle_courseid,
                ws_token=token_docente,
            )
        except (IdentityResolutionError, Exception) as exc:
            await self._registrar_fallo(
                db=db,
                estado=estado,
                moodle_userid=None,
                error=str(exc),
            )
            return

        nota_maxima = await self._nota_maxima_del_examen(db, session_id)
        # C-73 §10.6: la atribucion nombra al DOCENTE. Va con NOMBRE Y APELLIDO porque
        # la columna *Fuente* del historial de calificaciones la lee una persona: un
        # legajo obliga a ir a buscar de quien es.
        source = f"activeexam:{docente_nombre}" if docente_nombre else "activeexam"

        try:
            # C-73 Fase 1: `escribir_nota` rutea segun el component. Para una TAREA usa
            # `mod_assign_save_grade` (servicio movil de fabrica): el docente escribe
            # con SU token y la columna *Calificador* de la libreta dice su nombre, sin
            # que nadie configure nada en el campus. Verificado E2E en campustest.
            await self._client.escribir_nota(
                moodle_userid=moodle_userid,
                nota=float(estado.nota),
                courseid=estado.moodle_courseid,
                cmid=estado.moodle_cmid,
                component=estado.moodle_component,
                # Escala de ORIGEN: el cliente la usa para convertir a la del item
                # de Moodle (que suele ser 100). Sin esto un 8/10 iba como 8/100.
                nota_maxima=nota_maxima,
                ws_token=token_docente,
                source=source,
            )
        except MoodleGradeWriteError as exc:
            # C-73 §10.5: token revocado o vencido. Se marca la credencial como CAIDA
            # para poder avisarle al docente, y la nota queda pendiente: NO se
            # reintenta con la institucional, porque eso la firmaria con otra
            # identidad sin que nadie se entere.
            if _es_token_invalido(exc) and self._cred_docente and docente_id:
                await self._cred_docente.marcar_caida(docente_id)
            await self._registrar_fallo(
                db=db,
                estado=estado,
                moodle_userid=moodle_userid,
                error=str(exc),
            )
            return

        # Sello de uso exitoso: permite diagnosticar "hace meses que no sincroniza"
        # sin leer logs.
        if self._cred_docente and docente_id:
            await self._cred_docente.marcar_uso(docente_id)

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

        Es el acto COMPENSATORIO de la decision `anulado` (modelo de un solo
        paso): sin esto la anulacion queda en ActiveExam y el alumno conserva
        en la libreta de Moodle la nota que ya se le habia sincronizado.

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
            # Sin `ws_token`: el 0 por fraude lo firma la INSTITUCION a proposito — lo
            # decide un revisor, no el docente.
            await self._client.escribir_nota(
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
            # c-78 E-07: con sorteo por intento el denominador es el set de ESTE
            # alumno, no el pool del examen.
            session_id=sesion.id,
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
            # Como la anulacion: la restitucion la resuelve un revisor, no el docente,
            # asi que va con la credencial institucional (sin `ws_token`).
            await self._client.escribir_nota(
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
        error_limpio = await self._sanitizar_error(error)

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

    async def _sanitizar_error(self, error: str) -> str:
        """Elimina el token del mensaje de error antes de guardarlo.

        Resuelve el token VIGENTE (puede venir de la base y haber rotado): con la
        config estatica, tras una rotacion se redactaba el token viejo y el nuevo
        se escribia tal cual en el audit log.
        """
        try:
            cfg = await self._client._resolver_config()
            token = cfg.ws_token
        except Exception:  # noqa: BLE001 — redactar nunca puede romper el guardado
            token = ""
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
