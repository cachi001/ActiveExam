"""Repositorio de persistencia del modulo activeexam de proctoring.

Operaciones async sobre las tablas proctoring_session, proctoring_event y
proctoring_biometria. El calculo de score y discrepancias se hace aqui (o en
el servicio), NO en el router.

PRODUCCION (L2.5): el backend nunca sanciona ni emite veredicto disciplinario.
El score solo prioriza la cola de revision humana (D5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.proctoring.scoring import (
    PESOS_SEVERIDAD,
    SCORE_CAP,
    desactivados_de_snapshot,
    pesos_de_snapshot,
    umbral_de_snapshot,
)
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
    exam_id: str | None
    etiqueta: str | None
    creada_en: Any
    finalizada_en: Any
    total_eventos: int
    total_discrepancias: int
    score: int
    # Umbral efectivo de ESTA sesion: el de su config_snapshot (foto tomada al
    # crearla) si tiene una, o el umbral VIVO como fallback (sesion pre-migracion
    # 0083 o config no disponible al crear). Nunca el umbral vivo aplicado a
    # ciegas a sesiones viejas — eso es lo que este campo evita.
    umbral_cola_revision_efectivo: int
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
    # Identidad del alumno duenio de la sesion (C-76 tarea 17: columna "Alumno"
    # del Registro de sesiones). alumno_nombre resuelto contra `usuario`; None si
    # no matchea (la UI cae a idnumber/email crudo).
    alumno_idnumber: str | None = None
    alumno_email: str | None = None
    alumno_nombre: str | None = None


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
        config_snapshot: dict | None = None,
    ) -> ProctoringSessionModel:
        """Crea y persiste una nueva sesion de proctoring activeexam.

        ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
        importado de Moodle XML. NULLABLE: una sesion sin contenido sigue siendo
        valida (modo 'test' o examen sin contenido asociado).

        ``alumno_idnumber``/``alumno_email`` (C-69, migration 0033) persisten la
        identidad del alumno al CREAR la sesion (username del JWT). El
        enforcement de intentos cuenta sesiones finalizadas por (alumno, examen).

        ``config_snapshot`` (migration 0083): foto de umbral/pesos de scoring
        vigente al crear la sesion. None = no se pudo resolver la config al
        crear (degradacion) -> el scoring de esta sesion cae a la config viva.
        """
        sesion = ProctoringSessionModel(
            modo=modo,
            exam_id=exam_id,
            etiqueta=etiqueta,
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
            config_snapshot=config_snapshot,
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

    async def contexto_academico_de_examen(
        self, examen_contenido_id: str | None
    ) -> tuple[str | None, str | None, str | None]:
        """Resuelve (examen_titulo, comision_nombre, materia_nombre) de UN examen.

        Wrapper público de ``_contexto_academico`` para el detalle de sesión
        (GET /sessions/{id}), que necesita el mismo join que ya usa el listado
        pero para un solo ``examen_contenido_id``. None si no hay contenido
        vinculado a la sesión.
        """
        if examen_contenido_id is None:
            return (None, None, None)
        mapa = await self._contexto_academico([examen_contenido_id])
        titulo, comision, materia, _docente_id = mapa.get(
            examen_contenido_id, (None, None, None, None)
        )
        return (titulo, comision, materia)

    async def nombre_alumno(
        self, alumno_idnumber: str | None, alumno_email: str | None
    ) -> str | None:
        """Nombre completo del alumno dueño de la sesión, resuelto contra ``usuario``.

        Matchea por ``username == alumno_idnumber`` (JIT LTI/manual usa el username
        como idnumber) con fallback a ``email``. None si no hay identidad persistida
        en la sesión o el usuario no tiene nombre/apellido cargado — el detalle cae
        entonces a mostrar el idnumber/email crudo (ver router).
        """
        from app.infrastructure.persistence.models.transactional import UsuarioModel

        if not alumno_idnumber and not alumno_email:
            return None
        stmt = select(UsuarioModel.nombre, UsuarioModel.apellido)
        if alumno_idnumber and alumno_email:
            stmt = stmt.where(
                (UsuarioModel.username == alumno_idnumber)
                | (UsuarioModel.email == alumno_email)
            )
        elif alumno_idnumber:
            stmt = stmt.where(UsuarioModel.username == alumno_idnumber)
        else:
            stmt = stmt.where(UsuarioModel.email == alumno_email)
        fila = (await self._db.execute(stmt.limit(1))).first()
        if fila is None:
            return None
        nombre, apellido = fila
        completo = " ".join(p for p in (nombre, apellido) if p)
        return completo or None

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
        stmt = select(ProctoringSessionModel).order_by(
            ProctoringSessionModel.creada_en.desc()
        )
        result = await self._db.execute(stmt)
        sesiones = result.scalars().all()
        return await self._armar_resumenes(sesiones)

    async def listar_sesiones_finalizadas(
        self,
        *,
        q: str | None = None,
        exam_id: str | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        materia_id: str | None = None,
        comision_id: str | None = None,
    ) -> list[SesionResumenData]:
        """Sesiones FINALIZADAS (Registro de sesiones, C-76 tarea 17) con filtros SQL.

        - ``q``: busqueda por alumno (idnumber/email/nombre/apellido), SIEMPRE en SQL
          (mismo patron que ``resultados_query._aplicar_filtros``).
        - ``exam_id``: filtra por ``examen_contenido_id`` exacto (el catalogo de
          filtro sale de un endpoint dedicado — nunca hardcodeado en el frontend).
        - ``fecha_desde``/``fecha_hasta``: rango sobre ``finalizada_en``.
        - ``materia_id``/``comision_id`` (C-76 tarea 20.3): filtro en cascada
          Materia -> Comision, mismo join que ya resuelve ``materia_nombre``/
          ``comision_nombre`` (sesion -> examen_contenido -> comision -> materia).

        El nivel de riesgo NO se filtra aca (requiere el score ya calculado, que se
        resuelve en Python sobre TODOS los eventos de la sesion) — lo aplica el
        caller (router/servicio) sobre el resultado de esta funcion, igual que hace
        ``resultados_query`` con ``estado_entrega_filtro``.
        """
        from app.infrastructure.persistence.models.transactional import UsuarioModel

        stmt = (
            select(ProctoringSessionModel)
            .outerjoin(
                UsuarioModel,
                (UsuarioModel.username == ProctoringSessionModel.alumno_idnumber)
                | (UsuarioModel.email == ProctoringSessionModel.alumno_email),
            )
            .where(ProctoringSessionModel.finalizada_en.isnot(None))
        )
        if q:
            from sqlalchemy import or_

            patron = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    ProctoringSessionModel.alumno_idnumber.ilike(patron),
                    ProctoringSessionModel.alumno_email.ilike(patron),
                    UsuarioModel.nombre.ilike(patron),
                    UsuarioModel.apellido.ilike(patron),
                )
            )
        if exam_id:
            stmt = stmt.where(ProctoringSessionModel.examen_contenido_id == exam_id)
        if fecha_desde is not None:
            stmt = stmt.where(ProctoringSessionModel.finalizada_en >= fecha_desde)
        if fecha_hasta is not None:
            stmt = stmt.where(ProctoringSessionModel.finalizada_en <= fecha_hasta)
        if materia_id or comision_id:
            from app.infrastructure.persistence.models.exam_content import (
                ComisionModel,
                ExamenContenidoModel,
            )

            stmt = stmt.join(
                ExamenContenidoModel,
                ExamenContenidoModel.id == ProctoringSessionModel.examen_contenido_id,
            ).join(
                ComisionModel, ComisionModel.id == ExamenContenidoModel.comision_id
            )
            if comision_id:
                stmt = stmt.where(ComisionModel.id == comision_id)
            if materia_id:
                stmt = stmt.where(ComisionModel.materia_id == materia_id)
        stmt = stmt.order_by(ProctoringSessionModel.finalizada_en.desc())

        result = await self._db.execute(stmt)
        sesiones = result.scalars().unique().all()
        return await self._armar_resumenes(sesiones)

    async def catalogo_examenes_con_sesiones(self) -> list[tuple[str, str]]:
        """``[(examen_contenido_id, titulo)]`` de los examenes con AL MENOS una
        sesion FINALIZADA — catalogo del filtro "Examen" del Registro de sesiones
        (C-76 tarea 17.2). El frontend NUNCA hardcodea esta lista; sale de aca.

        Orden alfabetico por titulo (fallback al id si el examen no tiene titulo
        resuelto — no deberia pasar, pero no hay que reventar el select por eso).
        """
        from app.infrastructure.persistence.models.exam_content import (
            ExamenContenidoModel,
        )

        stmt = (
            select(ExamenContenidoModel.id, ExamenContenidoModel.titulo)
            .join(
                ProctoringSessionModel,
                ProctoringSessionModel.examen_contenido_id == ExamenContenidoModel.id,
            )
            .where(ProctoringSessionModel.finalizada_en.isnot(None))
            .distinct()
            .order_by(ExamenContenidoModel.titulo)
        )
        result = await self._db.execute(stmt)
        return [(row.id, row.titulo or row.id) for row in result.all()]

    async def _umbral_vivo(self) -> int:
        """Umbral de cola de revision VIVO (``configuracion_sistema.umbral_cola_revision``).

        Fallback cuando una sesion no tiene ``config_snapshot`` (pre-migracion
        0083 o config no disponible al crearla) — ver ``umbral_de_snapshot``.
        """
        from app.infrastructure.persistence.models.transactional import (
            ConfiguracionSistemaModel,
        )

        try:
            row = await self._db.execute(
                select(ConfiguracionSistemaModel.umbral_cola_revision)
            )
            val = row.scalars().first()
        except Exception:
            return 70
        return int(val) if val is not None else 70

    async def _armar_resumenes(
        self, sesiones: list[ProctoringSessionModel]
    ) -> list[SesionResumenData]:
        """Agrega eventos/discrepancias/score/contexto sobre un set de sesiones YA
        resuelto (filtrado o no). Extraido de ``listar_sesiones`` para que
        ``listar_sesiones_finalizadas`` (C-76 tarea 17) reuse EXACTAMENTE la misma
        formula de score — nunca una copia hardcodeada.

        migration 0083: cada sesion puntua con SU PROPIA foto de config
        (``config_snapshot``, tomada al crearla) en vez de la config viva —
        un cambio de umbral/pesos posterior no debe alterar el score de una
        sesion que ya arranco. Las sesiones sin foto (pre-migracion o
        degradacion al crear) caen a la config viva, igual que antes."""
        pesos_vivos = await self._pesos_vivos_por_tipo()
        desactivados_vivos = await self._tipos_desactivados()
        umbral_vivo = await self._umbral_vivo()

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

        # Pesos/desactivados/umbral EFECTIVOS por sesion: los de su config_snapshot
        # (foto al crearla) si tiene una, o los vivos como fallback (migration 0083).
        pesos_por_sesion: dict[str, dict[str, int]] = {}
        desactivados_por_sesion: dict[str, frozenset[str]] = {}
        umbral_por_sesion: dict[str, int] = {}
        for s in sesiones:
            snap = s.config_snapshot
            pesos_por_sesion[s.id] = pesos_de_snapshot(snap, pesos_vivos=pesos_vivos) or {}
            desactivados_por_sesion[s.id] = desactivados_de_snapshot(
                snap, desactivados_vivos=desactivados_vivos
            )
            umbral_por_sesion[s.id] = umbral_de_snapshot(snap, umbral_vivo=umbral_vivo)

        # Calcular score por sesion. Se agrupa por (sesion, TIPO, severidad) porque
        # el peso se define por tipo de evento; la severidad viaja para poder caer
        # a la red de seguridad cuando el tipo no esta en la config de esa sesion.
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
            if row.tipo in desactivados_por_sesion.get(sid, frozenset()):
                # Apagado por el admin (al momento efectivo de esta sesion): no suma.
                continue
            peso = pesos_por_sesion.get(sid, {}).get(row.tipo)
            if peso is None:
                peso = PESOS_SEVERIDAD.get(row.severidad, 0)
            score_por_sesion[sid] = score_por_sesion.get(sid, 0) + peso * row.cnt
        # Cap 0..100, igual que el detalle y el cliente.
        score_por_sesion = {
            sid: min(SCORE_CAP, total) for sid, total in score_por_sesion.items()
        }

        # Ultimo evento por sesion (max ts_backend): diferencia actividad reciente
        # de calma en la UI (ultimo_evento_en del DTO). NO se usa para finalizar
        # nada — una sesion sin eventos de proctoring por un rato (alumno leyendo
        # una consigna larga, nada sospechoso que reportar) es NORMAL en un examen
        # largo; finalizarla de oficio le bloqueaba el envio de respuestas (409)
        # a mitad de un examen legitimo. La sesion sale de "en vivo" SOLO por las
        # vias explicitas: entrega del alumno, vencimiento del plazo del examen,
        # o cierre administrativo.
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

        # Contexto academico por examen_contenido_id (examen_contenido -> comision ->
        # materia). Resuelto server-side para que la Cola de revision NO dependa de
        # catalogos mock del frontend (bug "Sin examen asociado" en todos lados).
        ctx_por_contenido = await self._contexto_academico(
            [s.examen_contenido_id for s in sesiones if s.examen_contenido_id]
        )
        # Identidad del alumno (C-76 tarea 17: columna "Alumno" del Registro de
        # sesiones). Resuelta en LOTE (no una query por sesion) contra `usuario`.
        nombres_por_sesion = await self._nombres_alumnos(sesiones)

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
                umbral_cola_revision_efectivo=umbral_por_sesion.get(s.id, umbral_vivo),
                ultimo_evento_en=ultimo_por_sesion.get(s.id) or s.creada_en,
                examen_contenido_id=s.examen_contenido_id,
                examen_titulo=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[0],
                comision_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[1],
                materia_nombre=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[2],
                docente_id=ctx_por_contenido.get(s.examen_contenido_id, (None, None, None, None))[3],
                alumno_idnumber=s.alumno_idnumber,
                alumno_email=s.alumno_email,
                alumno_nombre=nombres_por_sesion.get(s.id),
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

    async def _nombres_alumnos(
        self, sesiones: list[ProctoringSessionModel]
    ) -> dict[str, str | None]:
        """Mapea ``session.id -> nombre completo del alumno`` (C-76 tarea 17).

        Resuelto en UNA consulta por lote (no una query por sesion, que no
        escalaria con la paginacion): junta los ``alumno_idnumber``/``alumno_email``
        distintos del set y los matchea contra ``usuario.username``/``usuario.email``,
        mismo criterio que ``nombre_alumno()`` (single) y ``resultados_query``.
        None si la sesion no tiene identidad persistida o no matchea ningun usuario
        (la UI cae al idnumber/email crudo).
        """
        from app.infrastructure.persistence.models.transactional import UsuarioModel

        idnumbers = {s.alumno_idnumber for s in sesiones if s.alumno_idnumber}
        emails = {s.alumno_email for s in sesiones if s.alumno_email}
        if not idnumbers and not emails:
            return {}

        from sqlalchemy import or_

        condiciones = []
        if idnumbers:
            condiciones.append(UsuarioModel.username.in_(idnumbers))
        if emails:
            condiciones.append(UsuarioModel.email.in_(emails))

        stmt = select(
            UsuarioModel.username, UsuarioModel.email, UsuarioModel.nombre, UsuarioModel.apellido
        ).where(or_(*condiciones))
        rows = (await self._db.execute(stmt)).all()

        por_username: dict[str, str] = {}
        por_email: dict[str, str] = {}
        for row in rows:
            completo = " ".join(p for p in (row.nombre, row.apellido) if p)
            if not completo:
                continue
            if row.username:
                por_username[row.username] = completo
            if row.email:
                por_email[row.email] = completo

        resultado: dict[str, str | None] = {}
        for s in sesiones:
            nombre = None
            if s.alumno_idnumber and s.alumno_idnumber in por_username:
                nombre = por_username[s.alumno_idnumber]
            elif s.alumno_email and s.alumno_email in por_email:
                nombre = por_email[s.alumno_email]
            resultado[s.id] = nombre
        return resultado

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

    async def eliminar_sesion_test(self, session_id: str) -> str:
        """Elimina una sesion SOLO si ``modo == 'test'`` (C-76 tarea 20.1).

        Las sesiones ``modo='test'`` son diagnostico de camara/mic SIN examen
        real vinculado — no son evidencia academica. Las ``modo='examen'``
        quedan PERMANENTEMENTE protegidas (regla dura #6/#7, cadena de
        custodia — tarea 16): esta funcion las rechaza categoricamente, sin
        excepciones (ni siquiera admin).

        Devuelve ``'eliminada'`` | ``'no_encontrada'`` | ``'modo_examen'``. El
        cascade de eventos/biometria lo resuelve el ``ON DELETE CASCADE`` de
        las FKs (y el ``cascade="all, delete-orphan"`` del ORM).
        """
        sesion = await self._db.get(ProctoringSessionModel, session_id)
        if sesion is None:
            return "no_encontrada"
        if sesion.modo != "test":
            return "modo_examen"
        await self._db.delete(sesion)
        await self._db.commit()
        return "eliminada"

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
        worm_object_key: str | None = None,
        worm_uri: str | None = None,
        worm_retain_until: datetime | None = None,
        id: str | None = None,
    ) -> ProctoringEventModel:
        """Persiste un evento con todos los campos de re-inferencia e integridad.

        ``worm_*`` (c-77): referencia al deposito WORM adicional en MinIO. NULL
        cuando MinIO no esta configurado (Render hoy) — el screenshot en Postgres
        sigue siendo la fuente de verdad, sin cambios.

        ``id``: opcional. Si el caller ya deposito en el bucket WORM (c-77) usando
        un ``object_key`` derivado del id del evento, lo pasa explicito para que
        coincida con el id que se persiste aca. Si es None, la columna usa su
        ``server_default`` (``gen_random_uuid()``), igual que siempre.
        """
        campos: dict = dict(
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
            worm_object_key=worm_object_key,
            worm_uri=worm_uri,
            worm_retain_until=worm_retain_until,
        )
        if id is not None:
            # Explicito SOLO si el caller ya derivo el object_key WORM del id
            # (c-77): si es None, se deja que server_default (gen_random_uuid())
            # genere el id como siempre.
            campos["id"] = id
        evento = ProctoringEventModel(**campos)
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
