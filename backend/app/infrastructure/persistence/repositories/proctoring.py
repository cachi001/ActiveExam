"""Repositorio de persistencia del modulo slim de proctoring.

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
        examen_contenido_id: str | None = None,
        alumno_idnumber: str | None = None,
        alumno_email: str | None = None,
    ) -> ProctoringSessionModel:
        """Crea y persiste una nueva sesion de proctoring slim.

        ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
        importado de Moodle XML. NULLABLE: una sesion sin contenido sigue siendo
        valida (modo 'test' o examen sin contenido asociado).

        ``alumno_idnumber``/``alumno_email`` (C-69, migration 0033) persisten la
        identidad del alumno al CREAR la sesion (id_institucional del JWT). El
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
                examen_titulo=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None))[0],
                comision_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None))[1],
                materia_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None))[2],
            )
            for s in sesiones
        ]

    async def _contexto_academico(
        self, contenido_ids: list[str]
    ) -> dict[str, tuple[str | None, str | None, str | None]]:
        """Mapea examen_contenido_id -> (examen_titulo, comision_nombre, materia_nombre).

        LEFT JOIN a comision y materia: un examen sin comision asociada (comision_id
        NULL) resuelve el titulo del examen pero deja comision/materia en None.
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
            row.id: (row.titulo, row.comision_nombre, row.materia_nombre)
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
        proctor_actor: str | None = None,
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
            sesion.cierre_forzado_por = proctor_actor
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
