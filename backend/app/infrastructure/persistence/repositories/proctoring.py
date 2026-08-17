"""Repositorio de persistencia del modulo activeexam de proctoring.

Operaciones async sobre las tablas proctoring_session, proctoring_event y
proctoring_biometria. El calculo de score y discrepancias se hace aqui (o en
el servicio), NO en el router.

PRODUCCION (L2.5): el backend nunca sanciona ni emite veredicto disciplinario.
El score solo prioriza la cola de revision humana (D5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.proctoring.scoring import PESOS_SEVERIDAD, SCORE_CAP
from app.infrastructure.persistence.models.proctoring import (
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)

# Una sesion "en vivo" sin actividad por mas de este lapso se considera
# abandonada y se auto-finaliza al primer listado (ver listar_sesiones). Asi la
# supervision en vivo deja de mostrarla y queda solo en "Sesiones grabadas".
# Para evitar cerrar sesiones legitimas que solo estan calmas (sin eventos), el
# umbral se mide contra el ultimo evento o, en ausencia de eventos, contra la
# creacion. 15 min cubre lapsos de calma normales en un examen.
IDLE_TIMEOUT_MIN = 15


@dataclass
class SesionResumenData:
    """Datos de resumen de sesion para listar (con conteos calculados)."""

    id: str
    modo: str
    exam_id: str | None
    etiqueta: str | None
    creada_en: Any
    finalizada_en: Any
    total_eventos: int
    total_discrepancias: int
    score: int
    ultimo_evento_en: Any
    # Contexto academico resuelto server-side desde examen_contenido_id
    # (examen_contenido -> comision -> materia). NULL si la sesion no tiene contenido
    # vinculado o si el examen no esta asociado a una comision/materia. La Cola de
    # revision los usa para agrupar SIN depender de catalogos mock del frontend.
    examen_contenido_id: str | None = None
    examen_titulo: str | None = None
    comision_nombre: str | None = None
    materia_nombre: str | None = None
    # C-76 bloque 8: docente a cargo de la comision (comision.docente_id), para
    # acotar la supervision en vivo del TUTOR por pertenencia (D2 design c-76).
    docente_id: str | None = None


class ProctoringRepository:
    """CRUD async para las 3 tablas activeexam de proctoring."""

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
        examen_contenido_id: str | None = None,
        alumno_idnumber: str | None = None,
        alumno_email: str | None = None,
    ) -> ProctoringSessionModel:
        """Crea y persiste una nueva sesion de proctoring activeexam.

        ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
        importado de Moodle XML. NULLABLE: una sesion sin contenido sigue siendo
        valida (modo 'test' o examen sin contenido asociado).

        ``alumno_idnumber``/``alumno_email`` (C-69, migration 0033) persisten la
        identidad del alumno al CREAR la sesion (username del JWT). El
        enforcement de intentos cuenta sesiones finalizadas por (alumno, examen).
        """
        sesion = ProctoringSessionModel(
            modo=modo,
            exam_id=exam_id,
            etiqueta=etiqueta,
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
        )
        self._db.add(sesion)
        await self._db.commit()
        await self._db.refresh(sesion)
        return sesion

    async def obtener_sesion_activa(
        self, alumno_idnumber: str, examen_contenido_id: str
    ) -> ProctoringSessionModel | None:
        """Sesion ACTIVA (finalizada_en IS NULL) del alumno para ese examen_contenido.

        Anti-zombie (recarga de pagina durante la rendicion): antes de CREAR una
        sesion nueva, el caller consulta esto — si existe, se REUSA (misma id y
        misma creada_en) en vez de crear una fila nueva. Sin este chequeo, cada F5
        durante el examen creaba una sesion de proctoring nueva y dejaba la
        anterior "zombie" (en vivo para siempre, sin contar como intento porque el
        enforcement de intentos solo cuenta finalizadas) — timer reseteado,
        respuestas perdidas e intentos efectivamente infinitos.

        Si hay mas de una activa (no deberia, pero no lo garantiza un UNIQUE
        constraint), se toma la MAS VIEJA (primera creada): es la que el alumno
        viene rindiendo desde el principio; sus respuestas ya guardadas son las
        que hay que preservar.
        """
        stmt = (
            select(ProctoringSessionModel)
            .where(
                ProctoringSessionModel.alumno_idnumber == alumno_idnumber,
                ProctoringSessionModel.examen_contenido_id == examen_contenido_id,
                ProctoringSessionModel.finalizada_en.is_(None),
            )
            .order_by(ProctoringSessionModel.creada_en.asc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def docente_id_de_sesion(self, session_id: str) -> str | None:
        """Docente a cargo de la comision de la sesion (C-76 bloque 8, D2).

        Derivacion sesion -> examen_contenido -> comision -> docente_id. None si la
        sesion no existe, no tiene examen vinculado (modo 'test'), el examen no
        tiene comision, o la comision no tiene docente asignado — todos significan
        lo mismo para el caller: sin dueño identificable (solo pasan roles
        institucionales, ver ``autorizar_supervision_vivo_sobre_sesion``)."""
        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
        )

        stmt = (
            select(ComisionModel.docente_id)
            .select_from(ProctoringSessionModel)
            .join(
                ExamenContenidoModel,
                ExamenContenidoModel.id == ProctoringSessionModel.examen_contenido_id,
            )
            .join(
                ComisionModel, ComisionModel.id == ExamenContenidoModel.comision_id
            )
            .where(ProctoringSessionModel.id == session_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

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

    async def _pesos_vivos_por_tipo(self) -> dict[str, int]:
        """Peso vivo por tipo de evento desde ``evento_score_config`` (solo activos).

        Misma fuente que consume el endpoint del detalle de sesion: es lo que hace
        que lista y detalle den el MISMO numero. Si la tabla no esta disponible
        devuelve ``{}`` y el llamador cae a la red de seguridad por severidad
        (degradacion graceful, RN-GLB-03) — nunca rompe el listado.
        """
        from app.infrastructure.persistence.models.transactional import (
            EventoScoreConfigModel,
        )

        try:
            filas = await self._db.execute(
                select(
                    EventoScoreConfigModel.tipo_evento,
                    EventoScoreConfigModel.peso,
                ).where(EventoScoreConfigModel.activo.is_(True))
            )
        except Exception:
            return {}
        return {tipo: int(peso) for tipo, peso in filas.all()}

    async def _tipos_desactivados(self) -> frozenset[str]:
        """Tipos con fila en ``evento_score_config`` pero ``activo=False``: pesan 0.

        Apagado != desconocido. El apagado lo decidio el admin y no debe sumar; el
        tipo SIN fila (detector nuevo) sigue cayendo a la red de seguridad por
        severidad (RN-GLB-03). Antes ambos se veian igual —ausentes del mapa de
        pesos— y desactivar un detector lo dejaba sumando su peso por severidad.
        """
        from app.infrastructure.persistence.models.transactional import (
            EventoScoreConfigModel,
        )

        try:
            filas = await self._db.execute(
                select(EventoScoreConfigModel.tipo_evento).where(
                    EventoScoreConfigModel.activo.is_(False)
                )
            )
        except Exception:
            return frozenset()
        return frozenset(filas.scalars().all())

    async def listar_sesiones(self) -> list[SesionResumenData]:
        """Lista todas las sesiones con total_eventos, total_discrepancias y score.

        El score usa la MISMA fuente que el detalle de sesion: peso vivo por TIPO
        desde ``evento_score_config``, y si el tipo no esta configurado, la red de
        seguridad por severidad (``PESOS_SEVERIDAD``). L2.5: solo prioriza.

        Antes esta funcion tenia su propia tabla de pesos escrita a mano, indexada
        por severidades en MASCULINO ("alto"/"medio"/"bajo") que no existen: el
        vocabulario canonico es femenino (enum ``Severidad``). Ningun evento
        matcheaba, el ``.get(..., 0)`` devolvia 0 y TODA sesion listaba score 0 —
        con lo cual la cola de revision, que filtra por ``score >= umbral`` sobre
        esta lista, nunca se poblaba y ninguna sesion llegaba a revision humana.
        El detalle, que si usaba la fuente comun, mostraba el score correcto: la
        misma sesion daba 75 en el detalle y 0 en la lista.
        """
        pesos_por_tipo = await self._pesos_vivos_por_tipo()
        desactivados = await self._tipos_desactivados()

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

        # Calcular score por sesion. Se agrupa por (sesion, TIPO, severidad) porque
        # el peso vivo se define por tipo de evento; la severidad viaja para poder
        # caer a la red de seguridad cuando el tipo no esta en la config.
        score_stmt = (
            select(
                ProctoringEventModel.session_id,
                ProctoringEventModel.tipo,
                ProctoringEventModel.severidad,
                func.count(ProctoringEventModel.id).label("cnt"),
            )
            .where(ProctoringEventModel.session_id.in_(session_ids))
            .group_by(
                ProctoringEventModel.session_id,
                ProctoringEventModel.tipo,
                ProctoringEventModel.severidad,
            )
        )
        score_result = await self._db.execute(score_stmt)
        score_por_sesion: dict[str, int] = {}
        for row in score_result:
            sid = row.session_id
            if row.tipo in desactivados:
                # Apagado por el admin: no suma (y no cae al fallback).
                continue
            peso = pesos_por_tipo.get(row.tipo)
            if peso is None:
                peso = PESOS_SEVERIDAD.get(row.severidad, 0)
            score_por_sesion[sid] = score_por_sesion.get(sid, 0) + peso * row.cnt
        # Cap 0..100, igual que el detalle y el cliente.
        score_por_sesion = {
            sid: min(SCORE_CAP, total) for sid, total in score_por_sesion.items()
        }

        # Ultimo evento por sesion (max ts_backend). Permite (a) diferenciar
        # actividad reciente de calma en la UI y (b) auto-finalizar sesiones
        # abandonadas. Sin eventos, cae a creada_en al armar el DTO.
        last_stmt = (
            select(
                ProctoringEventModel.session_id,
                func.max(ProctoringEventModel.ts_backend).label("ultimo"),
            )
            .where(ProctoringEventModel.session_id.in_(session_ids))
            .group_by(ProctoringEventModel.session_id)
        )
        last_result = await self._db.execute(last_stmt)
        ultimo_por_sesion: dict[str, datetime] = {
            row.session_id: row.ultimo for row in last_result
        }

        # Auto-finalizar las que llevan IDLE_TIMEOUT_MIN sin actividad: la UI en
        # vivo solo debe mostrar sesiones realmente activas (decision UX). La
        # idempotencia la garantiza el guard `finalizada_en is None`.
        now_utc = datetime.now(tz=timezone.utc)
        cutoff = now_utc - timedelta(minutes=IDLE_TIMEOUT_MIN)
        cambios = False
        for s in sesiones:
            if s.finalizada_en is not None:
                continue
            actividad = ultimo_por_sesion.get(s.id) or s.creada_en
            if actividad is None:
                continue
            # Aseguramos timezone-aware antes de comparar (SQLite/PG pueden
            # devolver naive en algunos drivers).
            if actividad.tzinfo is None:
                actividad = actividad.replace(tzinfo=timezone.utc)
            if actividad < cutoff:
                s.finalizada_en = actividad
                cambios = True
        if cambios:
            await self._db.commit()

        # Contexto academico por examen_contenido_id (examen_contenido -> comision ->
        # materia). Resuelto server-side para que la Cola de revision NO dependa de
        # catalogos mock del frontend (bug "Sin examen asociado" en todos lados).
        ctx_por_contenido = await self._contexto_academico(
            [s.examen_contenido_id for s in sesiones if s.examen_contenido_id]
        )

        return [
            SesionResumenData(
                id=s.id,
                modo=s.modo,
                exam_id=s.exam_id,
                etiqueta=s.etiqueta,
                creada_en=s.creada_en,
                finalizada_en=s.finalizada_en,
                total_eventos=total_por_sesion.get(s.id, 0),
                total_discrepancias=disc_por_sesion.get(s.id, 0),
                # Cap a 100 (igual que el detalle y el cliente): el score es 0..100.
                score=min(100, score_por_sesion.get(s.id, 0)),
                ultimo_evento_en=ultimo_por_sesion.get(s.id) or s.creada_en,
                examen_contenido_id=s.examen_contenido_id,
                examen_titulo=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[0],
                comision_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[1],
                materia_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[2],
                docente_id=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[3],
            )
            for s in sesiones
        ]

    async def _contexto_academico(
        self, contenido_ids: list[str]
    ) -> dict[str, tuple[str | None, str | None, str | None, str | None]]:
        """Mapea examen_contenido_id -> (examen_titulo, comision_nombre, materia_nombre,
        docente_id).

        LEFT JOIN a comision y materia: un examen sin comision asociada (comision_id
        NULL) resuelve el titulo del examen pero deja comision/materia/docente en
        None. ``docente_id`` (C-76 bloque 8) es ``comision.docente_id`` — lo consume
        el router para acotar la supervision en vivo del TUTOR por pertenencia.
        """
        if not contenido_ids:
            return {}

        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
            MateriaModel,
        )

        stmt = (
            select(
                ExamenContenidoModel.id,
                ExamenContenidoModel.titulo,
                ComisionModel.nombre.label("comision_nombre"),
                MateriaModel.nombre.label("materia_nombre"),
                ComisionModel.docente_id,
            )
            .select_from(ExamenContenidoModel)
            .outerjoin(
                ComisionModel, ComisionModel.id == ExamenContenidoModel.comision_id
            )
            .outerjoin(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
            .where(ExamenContenidoModel.id.in_(set(contenido_ids)))
        )
        rows = await self._db.execute(stmt)
        return {
            row.id: (row.titulo, row.comision_nombre, row.materia_nombre, row.docente_id)
            for row in rows
        }

    async def finalizar_sesion(self, session_id: str) -> ProctoringSessionModel | None:
        """Setea finalizada_en = now() si y solo si es NULL.

        Idempotente: si ya estaba finalizada, devuelve la sesion sin modificar.
        Devuelve None si la sesion no existe.
        """
        sesion = await self._db.get(ProctoringSessionModel, session_id)
        if sesion is None:
            return None
        if sesion.finalizada_en is None:
            sesion.finalizada_en = datetime.now(tz=timezone.utc)
            await self._db.commit()
            await self._db.refresh(sesion)
        return sesion

    async def cerrar_forzado(
        self,
        session_id: str,
        motivo: str,
        tutor_actor: str | None = None,
    ) -> ProctoringSessionModel | None:
        """Cierre FORZADO de la sesion por el proctor (C-15 3.3). Operativo, NO disciplinario.

        Setea ``cierre_forzado_en/por/motivo`` (audit trail persistente en la propia
        fila) y, si la sesion no estaba finalizada, tambien ``finalizada_en``. NO toca
        ``decision`` (eso es el veredicto HUMANO de C-16 — regla dura #5: el sistema
        nunca sanciona).

        Idempotente: si la sesion YA fue cerrada de forma forzada, devuelve la fila
        sin modificar (el audit del primer cierre es inmutable). None si no existe.
        """
        sesion = await self._db.get(ProctoringSessionModel, session_id)
        if sesion is None:
            return None
        if sesion.cierre_forzado_en is None:
            ahora = datetime.now(tz=timezone.utc)
            sesion.cierre_forzado_en = ahora
            sesion.cierre_forzado_por = tutor_actor
            sesion.cierre_forzado_motivo = motivo
            if sesion.finalizada_en is None:
                sesion.finalizada_en = ahora
            await self._db.commit()
            await self._db.refresh(sesion)
        return sesion

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

    async def ultimo_evento_ts_backend(self, session_id: str) -> datetime | None:
        """ts_backend del ÚLTIMO evento de la sesión (hora del servidor), o None si
        no hay eventos. C-72 sección 5: mide la ausencia (now - último evento) para
        clasificar la reanudación. Server-side, nunca hora del cliente (regla #6)."""
        return (
            await self._db.execute(
                select(func.max(ProctoringEventModel.ts_backend)).where(
                    ProctoringEventModel.session_id == session_id
                )
            )
        ).scalar_one_or_none()

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
        """Persiste el resultado biometrico de una sesion (UPSERT: el último gana).

        Si el alumno falló un intento y reintentó con éxito, vale el resultado MÁS
        RECIENTE. Antes se insertaba siempre una fila nueva y la relación one-to-one
        devolvía la primera (la fallada) — por eso quedaba el resultado viejo.
        """
        previas = await self._db.execute(
            select(ProctoringBiometriaModel).where(
                ProctoringBiometriaModel.session_id == session_id
            )
        )
        for prev in previas.scalars().all():
            await self._db.delete(prev)

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
