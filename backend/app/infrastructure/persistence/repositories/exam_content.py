"""Repositorio SQLAlchemy para ExamenContenido (C-69)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.domain.exam_content.entities import (
    BlankCloze,
    Comision,
    ExamenContenido,
    ExamenContenidoResumen,
    Materia,
    OpcionBlankCloze,
    OpcionRespuesta,
    Pregunta,
    PreguntaSeleccionItem,
)
from app.application.exam_content.errors import SorteoInsuficienteError
from app.domain.exam_content.errors import (
    CodigoMatriculacionDuplicadoError,
    ComisionDuplicadaError,
    InscripcionDuplicadaError,
    MateriaDuplicadaError,
    SeleccionInvalidaError,
)
from app.infrastructure.persistence.models.exam_content import (
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.comision_tutor import (
    ComisionTutorModel,
    MateriaCoordinadorModel,
    MateriaProfesorModel,
)
from app.infrastructure.persistence.models.inscripcion import InscripcionModel
from app.infrastructure.persistence.models.transactional import UsuarioModel

# SQLSTATE de Postgres para "unique_violation". Otras violaciones de integridad
# (p. ej. foreign_key_violation 23503) NO se mapean a "duplicado": se re-elevan.
_PG_UNIQUE_VIOLATION = "23505"


def _es_uuid(valor: str | None) -> bool:
    """True si el valor puede compararse contra una columna UUID.

    Las columnas de id son UUID en Postgres, así que comparar contra un `sub` de
    token que NO sea un UUID (identidad federada con formato propio, token
    malformado) revienta con un DataError de asyncpg — o sea, un 500 en la cara
    del usuario donde correspondía un 403 limpio. Un id que no puede existir en la
    tabla simplemente NO tiene pertenencia: se responde False sin ir a la base.
    """
    if not valor:
        return False
    try:
        uuid.UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return False
    return True

# --- Orden alfabético en castellano, independiente del contenedor ------------
# `ORDER BY <texto>` usa la colación de la base, que depende de la libc de la
# IMAGEN: dev corre postgres:16-alpine (musl, sin locales reales → orden por bytes,
# "Álgebra" cae DESPUÉS de "Zoología") y prod corre timescaledb sobre glibc (orden
# correcto). O sea: el mismo listado se ordena distinto según dónde corra.
#
# Se normaliza el texto en SQL antes de ordenar: minúsculas + tildes plegadas. Es
# SQL portable puro (sin extensión `unaccent` ni colaciones ICU, que pueden no
# existir en una imagen dada), así que el resultado es IDÉNTICO en cualquier motor
# Postgres. La ñ se pliega a n: acepta el orden n < ñ < o de la RAE con una
# diferencia solo entre palabras que difieran ÚNICAMENTE por la ñ.
_ACENTOS = "áàäâãéèëêíìïîóòöôõúùüûñçÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ"
_SIN_ACENTOS = "aaaaaeeeeiiiiooooouuuuncAAAAAEEEEIIIIOOOOOUUUUNC"


def _orden_alfabetico(columna):
    """Clave de ordenamiento alfabético estable para nombres/títulos en castellano."""
    return func.lower(func.translate(columna, _ACENTOS, _SIN_ACENTOS))


def _es_violacion_unicidad(exc: IntegrityError) -> bool:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) == _PG_UNIQUE_VIOLATION


def _nombre_constraint(exc: IntegrityError) -> str | None:
    """Nombre del constraint violado (asyncpg lo expone en constraint_name).

    SQLAlchemy envuelve el error de asyncpg: la excepción original de asyncpg
    (con ``constraint_name``) suele quedar en ``exc.orig.__cause__``. Se consulta
    de forma defensiva para distinguir CUÁL unique se violó (materia+codigo vs.
    codigo_matriculacion) sin acoplarse a la estructura exacta del driver.
    """
    orig = getattr(exc, "orig", None)
    causa = getattr(orig, "__cause__", None)
    return (
        getattr(causa, "constraint_name", None)
        or getattr(orig, "constraint_name", None)
    )


class ExamenContenidoSqlRepository:
    """CRUD async para examen_contenido, pregunta_examen, opcion_respuesta."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def guardar(self, examen: ExamenContenido) -> ExamenContenido:
        """Persiste el examen con sus preguntas y opciones; devuelve entidad con id."""
        model = ExamenContenidoModel(
            titulo=examen.titulo,
            comision_id=examen.comision_id,
            moodle_courseid=examen.moodle_courseid,
            moodle_cmid=examen.moodle_cmid,
            moodle_component=examen.moodle_component,
            tiempo_limite_min=examen.tiempo_limite_min,
            intentos_permitidos=examen.intentos_permitidos,
            apertura=examen.apertura,
            cierre=examen.cierre,
            nota_maxima=examen.nota_maxima,
            nota_aprobacion=examen.nota_aprobacion,
            mezclar_preguntas=examen.mezclar_preguntas,
            limite_preguntas=examen.limite_preguntas,
            mostrar_nota=examen.mostrar_nota,
            revision_habilitada=examen.revision_habilitada,
            mostrar_eventos_alumno=examen.mostrar_eventos_alumno,
        )
        for i, pregunta in enumerate(examen.preguntas):
            p_model = PreguntaExamenModel(
                enunciado=pregunta.enunciado,
                tipo=pregunta.tipo,
                orden=pregunta.orden if pregunta.orden else i,
                seleccionada=pregunta.seleccionada,
                categoria_id=pregunta.categoria_id,
            )
            for j, opcion in enumerate(pregunta.opciones):
                o_model = OpcionRespuestaModel(
                    texto=opcion.texto,
                    es_correcta=opcion.es_correcta,
                    orden=opcion.orden if opcion.orden else j,
                )
                p_model.opciones.append(o_model)
            model.preguntas.append(p_model)

        self._db.add(model)
        await self._db.flush()

        # async NO soporta lazy-load de relaciones: re-leemos con eager load
        # (selectinload via obtener) en vez de refresh(), que expira las
        # relaciones y dispararia MissingGreenlet al construir la entidad.
        entidad = await self.obtener(model.id)
        assert entidad is not None  # recien insertado en esta misma transaccion
        return entidad

    def _stmt_resumen(self):
        """Statement base del read-model de resumen, enriquecido con comisión+materia.

        LEFT JOIN a comisión y materia (D11): un examen sin comisión deja esos
        campos en NULL. Se agrupa por las columnas no agregadas para contar preguntas.

        Opción B (pool de preguntas): cantidad_preguntas cuenta SOLO las preguntas
        seleccionadas (FILTER por seleccionada=true), para que el catálogo y el
        encabezado muestren el tamaño REAL del examen, no el del pool importado.
        """
        return (
            select(
                ExamenContenidoModel.id,
                ExamenContenidoModel.titulo,
                func.count(PreguntaExamenModel.id)
                .filter(PreguntaExamenModel.seleccionada.is_(True))
                .label("cantidad_preguntas"),
                ExamenContenidoModel.comision_id,
                ComisionModel.nombre.label("comision_nombre"),
                ComisionModel.codigo.label("comision_codigo"),
                MateriaModel.nombre.label("materia_nombre"),
                MateriaModel.codigo.label("materia_codigo"),
                ExamenContenidoModel.apertura,
                ExamenContenidoModel.cierre,
                ExamenContenidoModel.tiempo_limite_min,
                ExamenContenidoModel.intentos_permitidos,
                ExamenContenidoModel.eliminado_en,
                # c-78 E-07: el catálogo del staff marca los que no se habilitaron
                # y los que sortean por intento.
                ExamenContenidoModel.borrador,
                ExamenContenidoModel.modo_preguntas,
            )
            .outerjoin(
                PreguntaExamenModel,
                PreguntaExamenModel.examen_id == ExamenContenidoModel.id,
            )
            .outerjoin(
                ComisionModel,
                ComisionModel.id == ExamenContenidoModel.comision_id,
            )
            .outerjoin(
                MateriaModel,
                MateriaModel.id == ComisionModel.materia_id,
            )
            .group_by(
                ExamenContenidoModel.id,
                ExamenContenidoModel.titulo,
                ExamenContenidoModel.comision_id,
                ComisionModel.nombre,
                ComisionModel.codigo,
                MateriaModel.nombre,
                MateriaModel.codigo,
                ExamenContenidoModel.apertura,
                ExamenContenidoModel.cierre,
                ExamenContenidoModel.tiempo_limite_min,
                ExamenContenidoModel.intentos_permitidos,
                ExamenContenidoModel.eliminado_en,
                ExamenContenidoModel.borrador,
                ExamenContenidoModel.modo_preguntas,
            )
        )

    @staticmethod
    def _row_to_resumen(row) -> ExamenContenidoResumen:
        return ExamenContenidoResumen(
            id=row.id,
            titulo=row.titulo,
            cantidad_preguntas=row.cantidad_preguntas,
            comision_id=row.comision_id,
            comision_nombre=row.comision_nombre,
            comision_codigo=row.comision_codigo,
            materia_nombre=row.materia_nombre,
            materia_codigo=row.materia_codigo,
            apertura=row.apertura,
            cierre=row.cierre,
            tiempo_limite_min=row.tiempo_limite_min,
            intentos_permitidos=row.intentos_permitidos,
            eliminado_en=row.eliminado_en,
            borrador=row.borrador,
            modo_preguntas=row.modo_preguntas,
        )

    async def listar(self) -> list[ExamenContenidoResumen]:
        """Lista todos los exámenes con id, titulo, cantidad de preguntas y, si tienen
        comisión asociada, comision_id/comision_nombre/materia_nombre (D11, NULLABLE).

        Read-model liviano para el catálogo del alumno/admin: sin preguntas ni opciones.
        Orden estable: alfabético ascendente por titulo.
        D3: es_correcta no expuesta (solo metadatos del examen).
        """
        stmt = self._stmt_resumen().order_by(_orden_alfabetico(ExamenContenidoModel.titulo))
        result = await self._db.execute(stmt)
        return [self._row_to_resumen(row) for row in result.all()]

    @staticmethod
    def _filtro_estado(stmt, estado: str | None):
        """Aplica el filtro de baja lógica (c-78 D1) sobre ``eliminado_en``.

        ``"activo"`` (default de todos los llamadores) = solo ``IS NULL``;
        ``"inactivo"`` = solo dados de baja; ``"todos"`` = sin filtro. Cualquier
        otro valor se trata como ``"activo"``: la validación del conjunto la hace
        el router (422), acá nunca se abre el catálogo por un valor raro.
        """
        if estado == "todos":
            return stmt
        if estado == "inactivo":
            return stmt.where(ExamenContenidoModel.eliminado_en.is_not(None))
        return stmt.where(ExamenContenidoModel.eliminado_en.is_(None))

    def _filtro_q(self, stmt, q: str | None):
        """Aplica búsqueda serverside por título / materia / comisión (ILIKE)."""
        if not q:
            return stmt
        patron = f"%{q.strip()}%"
        return stmt.where(
            or_(
                ExamenContenidoModel.titulo.ilike(patron),
                ComisionModel.nombre.ilike(patron),
                MateriaModel.nombre.ilike(patron),
            )
        )

    async def listar_paginado(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 1000,
        comision_ids: list[str] | None = None,
        filtro_materia_id: str | None = None,
        filtro_comision_id: str | None = None,
        estado: str = "activo",
        incluir_borradores: bool = True,
    ) -> tuple[list[ExamenContenidoResumen], int]:
        """Lista paginada + búsqueda serverside del catálogo (tarea 4, admin-sync).

        Filtra por título/materia/comisión (q, ILIKE) SIEMPRE en SQL. Orden estable
        alfabético por título. Devuelve (items_de_la_pagina, total_global_filtrado).
        El total cuenta los exámenes que matchean el filtro, no solo la página.

        Gate de inscripción (C-71): ``comision_ids`` restringe el catálogo a esas
        comisiones (alumno → sus comisiones inscriptas). ``None`` = sin restricción
        (admin ve todo). Lista vacía = alumno sin inscripciones → catálogo vacío.

        Baja lógica (c-78 D1): ``estado`` es ``"activo"`` (default, solo
        ``eliminado_en IS NULL``) | ``"inactivo"`` (solo dados de baja) | ``"todos"``.
        El filtro se resuelve EN SQL sobre la misma subconsulta que produce el
        ``total``, así que el total corresponde siempre al conjunto filtrado.

        Borrador (c-78 E-07): ``incluir_borradores=False`` saca del listado los
        exámenes que todavía no se habilitaron. Lo usa la vista del ALUMNO. El
        staff los ve, porque los tiene que poder abrir para probarlos y habilitarlos.
        """
        page = max(1, page)
        page_size = max(1, page_size)

        # Alumno sin inscripciones: catálogo vacío (no ve ningún examen).
        if comision_ids is not None and not comision_ids:
            return [], 0

        base = self._filtro_q(self._stmt_resumen(), q)
        base = self._filtro_estado(base, estado)
        if not incluir_borradores:
            base = base.where(ExamenContenidoModel.borrador.is_(False))
        if comision_ids is not None:
            base = base.where(ExamenContenidoModel.comision_id.in_(comision_ids))
        if filtro_materia_id is not None:
            base = base.where(ComisionModel.materia_id == filtro_materia_id)
        if filtro_comision_id is not None:
            base = base.where(ExamenContenidoModel.comision_id == filtro_comision_id)

        # total = cantidad de grupos (exámenes) que matchean el filtro
        total_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._db.execute(total_stmt)).scalar_one()

        page_stmt = (
            base.order_by(_orden_alfabetico(ExamenContenidoModel.titulo))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._db.execute(page_stmt)
        items = [self._row_to_resumen(row) for row in result.all()]
        return items, int(total)

    async def obtener_resumen(self, examen_id: str) -> ExamenContenidoResumen | None:
        """Resumen (metadatos) de UN examen para el encabezado del detalle.

        Reusa el read-model de resumen (count de preguntas + LEFT JOIN comisión/
        materia, D11). Devuelve None si el examen no existe. D3: sin preguntas ni
        es_correcta — solo metadatos.
        """
        stmt = self._stmt_resumen().where(ExamenContenidoModel.id == examen_id)
        result = await self._db.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return self._row_to_resumen(row)

    async def listar_por_comision(
        self, comision_id: str, *, estado: str = "activo"
    ) -> list[ExamenContenidoResumen]:
        """Lista los exámenes asociados a una comisión (orden alfabético por titulo).

        Alimenta el picker de Notas, así que respeta la baja lógica (c-78 D1): por
        default solo los activos. Un examen dado de baja no se ofrece para cargar
        notas, aunque sus resultados ya cargados sigan consultables por id (D2).
        """
        stmt = (
            self._filtro_estado(self._stmt_resumen(), estado)
            .where(ExamenContenidoModel.comision_id == comision_id)
            .order_by(_orden_alfabetico(ExamenContenidoModel.titulo))
        )
        result = await self._db.execute(stmt)
        return [self._row_to_resumen(row) for row in result.all()]

    async def asociar_comision(
        self, examen_id: str, comision_id: str | None
    ) -> ExamenContenido | None:
        """Asocia (o desasocia con None) un examen a una comisión.

        Devuelve el examen actualizado, o None si el examen no existe. No
        reimporta el contenido (D11): solo actualiza la FK comision_id.
        """
        result = await self._db.execute(
            update(ExamenContenidoModel)
            .where(ExamenContenidoModel.id == examen_id)
            .values(comision_id=comision_id)
            .returning(ExamenContenidoModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(examen_id)

    async def set_moodle_target(
        self,
        examen_id: str,
        moodle_courseid: int | None,
        moodle_cmid: int | None,
    ) -> ExamenContenido | None:
        """Fija (o limpia con None) el destino de write-back a Moodle del examen (D12).

        Devuelve el examen actualizado, o None si el examen no existe. NO reimporta
        el contenido: solo actualiza moodle_courseid/moodle_cmid. Estos valores son
        AUTORITATIVOS en el write-back; cuando quedan NULL, se cae al global.
        """
        result = await self._db.execute(
            update(ExamenContenidoModel)
            .where(ExamenContenidoModel.id == examen_id)
            .values(moodle_courseid=moodle_courseid, moodle_cmid=moodle_cmid)
            .returning(ExamenContenidoModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(examen_id)

    async def actualizar_config(
        self, examen_id: str, valores: dict
    ) -> ExamenContenido | None:
        """Actualiza los campos de configuración dados (update parcial) del examen.

        ``valores`` mapea nombre de columna → valor (solo las claves presentes se
        actualizan). Devuelve el examen actualizado, o None si no existe. NO valida:
        la validación de dominio la hace el caller (capa de aplicación/HTTP) antes.
        """
        if not valores:
            return await self.obtener(examen_id)
        result = await self._db.execute(
            update(ExamenContenidoModel)
            .where(ExamenContenidoModel.id == examen_id)
            .values(**valores)
            .returning(ExamenContenidoModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(examen_id)

    async def dar_de_baja(self, examen_id: str) -> bool:
        """Baja lógica del examen (c-78 D1): setea ``eliminado_en = now()``.

        Devuelve ``False`` si el examen no existe **o ya estaba de baja** (el
        router lo traduce a 404, igual que ``eliminar_usuario``). No toca sesiones,
        eventos, capturas ni notas: la baja es administrativa (D2).
        """
        if not _es_uuid(examen_id):
            return False
        result = await self._db.execute(
            update(ExamenContenidoModel)
            .where(
                ExamenContenidoModel.id == examen_id,
                ExamenContenidoModel.eliminado_en.is_(None),
            )
            .values(eliminado_en=func.now())
            .returning(ExamenContenidoModel.id)
        )
        if result.scalar_one_or_none() is None:
            return False
        await self._db.flush()
        return True

    async def reactivar(self, examen_id: str) -> bool:
        """Revierte la baja lógica: ``eliminado_en = NULL`` (c-78 D1).

        Devuelve ``False`` si el examen no existe **o ya estaba activo** (→ 404).
        """
        if not _es_uuid(examen_id):
            return False
        result = await self._db.execute(
            update(ExamenContenidoModel)
            .where(
                ExamenContenidoModel.id == examen_id,
                ExamenContenidoModel.eliminado_en.is_not(None),
            )
            .values(eliminado_en=None)
            .returning(ExamenContenidoModel.id)
        )
        if result.scalar_one_or_none() is None:
            return False
        await self._db.flush()
        return True

    async def _examen_existe(self, examen_id: str) -> bool:
        result = await self._db.execute(
            select(ExamenContenidoModel.id).where(
                ExamenContenidoModel.id == examen_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def listar_preguntas(
        self, examen_id: str
    ) -> list[PreguntaSeleccionItem] | None:
        """Lista TODO el pool de preguntas del examen (seleccionadas y no) — opción B.

        Devuelve None si el examen no existe. Orden estable por ``orden``. D3:
        es_correcta y opciones AUSENTES — el docente identifica por enunciado.
        """
        if not await self._examen_existe(examen_id):
            return None
        result = await self._db.execute(
            select(
                PreguntaExamenModel.id,
                PreguntaExamenModel.enunciado,
                PreguntaExamenModel.tipo,
                PreguntaExamenModel.orden,
                PreguntaExamenModel.seleccionada,
            )
            .where(PreguntaExamenModel.examen_id == examen_id)
            .order_by(PreguntaExamenModel.orden)
        )
        return [
            PreguntaSeleccionItem(
                id=row.id,
                enunciado=row.enunciado,
                tipo=row.tipo,
                orden=row.orden,
                seleccionada=row.seleccionada,
            )
            for row in result.all()
        ]

    async def actualizar_seleccion(
        self, examen_id: str, seleccionadas_ids: list[str]
    ) -> list[PreguntaSeleccionItem] | None:
        """Marca seleccionada=true para los ids dados y false para el resto (opción B).

        - Devuelve None si el examen no existe (→ 404).
        - Ignora ids que no pertenezcan a ESTE examen (intersección con su pool).
        - Si tras filtrar no queda ninguna pregunta válida seleccionada, eleva
          ``SeleccionInvalidaError`` (→ 422): un examen necesita >= 1 seleccionada.
        - Devuelve el pool actualizado en caso de éxito.
        """
        if not await self._examen_existe(examen_id):
            return None

        ids_examen = set(
            (
                await self._db.execute(
                    select(PreguntaExamenModel.id).where(
                        PreguntaExamenModel.examen_id == examen_id
                    )
                )
            )
            .scalars()
            .all()
        )
        validas = ids_examen & set(seleccionadas_ids)
        if not validas:
            raise SeleccionInvalidaError(
                "La selección debe incluir al menos 1 pregunta del examen."
            )

        await self._db.execute(
            update(PreguntaExamenModel)
            .where(
                PreguntaExamenModel.examen_id == examen_id,
                PreguntaExamenModel.id.in_(validas),
            )
            .values(seleccionada=True)
        )
        await self._db.execute(
            update(PreguntaExamenModel)
            .where(
                PreguntaExamenModel.examen_id == examen_id,
                PreguntaExamenModel.id.notin_(validas),
            )
            .values(seleccionada=False)
        )
        await self._db.flush()
        return await self.listar_preguntas(examen_id)

    async def sortear_por_categorias(
        self,
        examen_id: str,
        categoria_ids: list[str],
        cantidad_por_categoria: int,
    ) -> list[PreguntaSeleccionItem] | None:
        """Sortea N preguntas de cada categoría y las marca seleccionada=true.

        - Devuelve None si el examen no existe.
        - Eleva SorteoInsuficienteError si alguna categoría tiene < N preguntas.
        - Eleva SeleccionInvalidaError si la lista de categorías resulta vacía.
        - Cada llamada produce una selección NUEVA (el sorteo no es idempotente).
        """
        if not await self._examen_existe(examen_id):
            return None

        if not categoria_ids:
            raise SeleccionInvalidaError("Se requiere al menos 1 categoría para el sorteo.")

        seleccionadas: list[str] = []
        for cat_id in categoria_ids:
            disponibles_result = await self._db.execute(
                select(func.count(PreguntaExamenModel.id)).where(
                    PreguntaExamenModel.examen_id == examen_id,
                    PreguntaExamenModel.categoria_id == cat_id,
                )
            )
            disponibles = disponibles_result.scalar_one()
            if disponibles < cantidad_por_categoria:
                raise SorteoInsuficienteError(cat_id, disponibles, cantidad_por_categoria)

            elegidas = await self._db.execute(
                select(PreguntaExamenModel.id)
                .where(
                    PreguntaExamenModel.examen_id == examen_id,
                    PreguntaExamenModel.categoria_id == cat_id,
                )
                .order_by(func.random())
                .limit(cantidad_por_categoria)
            )
            seleccionadas.extend(elegidas.scalars().all())

        # Reset todo el examen, luego marca las elegidas.
        await self._db.execute(
            update(PreguntaExamenModel)
            .where(PreguntaExamenModel.examen_id == examen_id)
            .values(seleccionada=False)
        )
        await self._db.execute(
            update(PreguntaExamenModel)
            .where(
                PreguntaExamenModel.examen_id == examen_id,
                PreguntaExamenModel.id.in_(seleccionadas),
            )
            .values(seleccionada=True)
        )
        await self._db.flush()
        return await self.listar_preguntas(examen_id)

    async def obtener(self, examen_id: str) -> ExamenContenido | None:
        """Recupera un examen por id con preguntas y opciones (eager load)."""
        result = await self._db.execute(
            select(ExamenContenidoModel)
            .where(ExamenContenidoModel.id == examen_id)
            .options(
                selectinload(ExamenContenidoModel.preguntas).selectinload(
                    PreguntaExamenModel.opciones
                )
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def obtener_para_rendir(
        self, examen_id: str, pregunta_ids: list[str] | None = None
    ) -> ExamenContenido | None:
        """Recupera un examen con SOLO las preguntas a rendir, y sus blanks.

        `obtener()` trae el pool ENTERO y el filtrado por `seleccionada` ocurría
        recién en Python: con 232 preguntas importadas para servir 20, la rendición
        arrastraba miles de filas de opciones al pedo (preguntas y timer salen del
        mismo GET, así que la pantalla del alumno tardaba en aparecer). Acá el
        filtro va EN SQL.

        ``pregunta_ids`` (c-78 E-07): el set que le tocó a ESTE intento. Con sorteo
        por intento el pool queda todo con `seleccionada=False` y quién entra lo
        decide el sorteo, así que sin este parámetro la rendición saldría vacía.
        None = modo 'fijo', se filtra por `seleccionada` como siempre.

        Además hace eager load de `pregunta_cloze_blank` y sus opciones: sin eso las
        preguntas cloze llegaban al alumno sin huecos que completar.
        """
        criterio = (
            PreguntaExamenModel.id.in_(pregunta_ids)
            if pregunta_ids is not None
            else PreguntaExamenModel.seleccionada.is_(True)
        )
        result = await self._db.execute(
            select(ExamenContenidoModel)
            .where(
                ExamenContenidoModel.id == examen_id,
                # c-78: un examen dado de baja NO se sirve para rendir. Segunda
                # barrera, redundante con `verificar_enforcement` a proposito: si
                # aparece otro camino de rendicion que no pase por el enforcement,
                # este WHERE lo corta igual (devuelve None -> 404).
                ExamenContenidoModel.eliminado_en.is_(None),
            )
            .options(
                selectinload(ExamenContenidoModel.preguntas).selectinload(
                    PreguntaExamenModel.opciones
                ),
                selectinload(ExamenContenidoModel.preguntas)
                .selectinload(PreguntaExamenModel.blanks_cloze)
                .selectinload(PreguntaClozeBlankModel.opciones_cloze),
                # El filtro viaja al WHERE del SELECT de la relación, no a Python.
                with_loader_criteria(PreguntaExamenModel, criterio),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model, con_blanks=True)

    def _to_entity(
        self, model: ExamenContenidoModel, con_blanks: bool = False
    ) -> ExamenContenido:
        preguntas = tuple(
            Pregunta(
                id=p.id,
                enunciado=p.enunciado,
                tipo=p.tipo,
                orden=p.orden,
                seleccionada=p.seleccionada,
                # Sin esto la categoría se perdía en el round-trip: el import la
                # escribía en pregunta_examen, releía la entidad sin categoría y
                # poblaba pregunta_banco con categoria_id=NULL. Resultado: el
                # banco entero quedaba "sin clasificar" y el sorteo por categoría
                # no tenía de dónde sacar.
                categoria_id=p.categoria_id,
                opciones=tuple(
                    OpcionRespuesta(
                        id=o.id,
                        texto=o.texto,
                        es_correcta=o.es_correcta,
                        orden=o.orden,
                    )
                    for o in p.opciones
                ),
                # Solo cuando vienen eager-loaded: con lazy load acá reventaría
                # (sesión async).
                blanks=self._blanks_to_entity(p) if con_blanks else (),
            )
            for p in model.preguntas
        )
        return ExamenContenido(
            id=model.id,
            titulo=model.titulo,
            comision_id=model.comision_id,
            moodle_courseid=model.moodle_courseid,
            moodle_cmid=model.moodle_cmid,
            moodle_component=model.moodle_component,
            tiempo_limite_min=model.tiempo_limite_min,
            intentos_permitidos=model.intentos_permitidos,
            apertura=model.apertura,
            cierre=model.cierre,
            nota_maxima=float(model.nota_maxima),
            nota_aprobacion=float(model.nota_aprobacion),
            mezclar_preguntas=model.mezclar_preguntas,
            limite_preguntas=model.limite_preguntas,
            mostrar_nota=model.mostrar_nota,
            revision_habilitada=model.revision_habilitada,
            # c-78 D9/D10.
            mostrar_eventos_alumno=model.mostrar_eventos_alumno,
            notas_publicadas_en=model.notas_publicadas_en,
            notas_publicadas_por=model.notas_publicadas_por,
            politica_intentos=model.politica_intentos,
            preguntas=preguntas,
        )

    @staticmethod
    def _blanks_to_entity(pregunta: PreguntaExamenModel) -> tuple[BlankCloze, ...]:
        """Mapea los huecos cloze de una pregunta ya eager-loaded."""
        return tuple(
            BlankCloze(
                id=b.id,
                orden=b.orden,
                tipo=b.tipo,
                texto_antes=b.texto_antes or "",
                texto_despues=b.texto_despues or "",
                opciones=tuple(
                    OpcionBlankCloze(
                        id=o.id,
                        texto=o.texto,
                        es_correcta=o.es_correcta,
                        # opcion_cloze_blank no tiene columna `orden`: se usa el
                        # orden de inserción, que es el del XML de Moodle.
                        orden=i,
                        peso=o.peso,
                    )
                    for i, o in enumerate(b.opciones_cloze)
                ),
            )
            for b in sorted(pregunta.blanks_cloze, key=lambda x: x.orden)
        )


class MateriaSqlRepository:
    """CRUD async para la tabla materia (C-69 sección 6, D11)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def guardar(self, materia: Materia) -> Materia:
        """Persiste una materia; codigo único → MateriaDuplicadaError si colisiona."""
        model = MateriaModel(codigo=materia.codigo, nombre=materia.nombre)
        self._db.add(model)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            if _es_violacion_unicidad(exc):
                raise MateriaDuplicadaError(
                    f"Ya existe una materia con codigo {materia.codigo!r}."
                ) from exc
            raise
        return Materia(id=model.id, codigo=model.codigo, nombre=model.nombre, activa=model.activa)

    async def listar(self) -> list[Materia]:
        """Lista todas las materias (id, codigo, nombre), orden alfabético por nombre."""
        result = await self._db.execute(
            select(MateriaModel).order_by(_orden_alfabetico(MateriaModel.nombre))
        )
        return [
            Materia(id=m.id, codigo=m.codigo, nombre=m.nombre, activa=m.activa)
            for m in result.scalars().all()
        ]

    async def obtener(self, materia_id: str) -> Materia | None:
        model = await self._db.get(MateriaModel, materia_id)
        if model is None:
            return None
        return Materia(id=model.id, codigo=model.codigo, nombre=model.nombre, activa=model.activa)

    async def obtener_por_codigo(self, codigo: str) -> Materia | None:
        result = await self._db.execute(
            select(MateriaModel).where(MateriaModel.codigo == codigo)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return Materia(id=model.id, codigo=model.codigo, nombre=model.nombre, activa=model.activa)

    async def actualizar(
        self, materia_id: str, *, nombre: str, codigo: str | None = None
    ) -> Materia | None:
        """Actualiza el nombre y (opcionalmente) el codigo de una materia.

        Devuelve la materia actualizada, o None si no existe. No valida dominio: la
        validación y el chequeo de unicidad los hace el caller (capa de aplicación).
        El codigo único es un backstop de carrera: si colisiona → MateriaDuplicadaError.
        """
        values: dict[str, str] = {"nombre": nombre}
        if codigo is not None:
            values["codigo"] = codigo
        try:
            result = await self._db.execute(
                update(MateriaModel)
                .where(MateriaModel.id == materia_id)
                .values(**values)
                .returning(MateriaModel.id)
            )
            if result.scalar_one_or_none() is None:
                return None
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            if _es_violacion_unicidad(exc):
                raise MateriaDuplicadaError(
                    f"Ya existe una materia con codigo {codigo!r}."
                ) from exc
            raise
        return await self.obtener(materia_id)

    async def set_activa(self, materia_id: str, activa: bool) -> Materia | None:
        """Setea el estado `activa` de una materia (C-72 §17).

        Devuelve la materia actualizada, o None si no existe.
        """
        result = await self._db.execute(
            update(MateriaModel)
            .where(MateriaModel.id == materia_id)
            .values(activa=activa)
            .returning(MateriaModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(materia_id)

    async def contar_inscriptos_y_examenes(self, materia_id: str) -> tuple[int, int]:
        """Cuenta (inscriptos, examenes) bajo TODAS las comisiones de la materia.

        Insumo del guard de borrado (C-72 §16): una materia solo se elimina si
        ambos contadores son 0.
        """
        inscriptos = await self._db.scalar(
            select(func.count())
            .select_from(InscripcionModel)
            .join(ComisionModel, InscripcionModel.comision_id == ComisionModel.id)
            .where(ComisionModel.materia_id == materia_id)
        )
        examenes = await self._db.scalar(
            select(func.count())
            .select_from(ExamenContenidoModel)
            .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
            .where(ComisionModel.materia_id == materia_id)
        )
        return int(inscriptos or 0), int(examenes or 0)

    async def contar_inscriptos_y_examenes_todas(self) -> dict[str, tuple[int, int]]:
        """(inscriptos, examenes) por materia, para TODAS las materias en 2 queries.

        Evita el N+1 del listado: la UI necesita saber por materia si tiene
        inscriptos/exámenes para OCULTAR el botón de eliminar. Materias sin
        inscriptos ni exámenes no aparecen en los mapas → se resuelven a (0, 0).
        """
        ins_rows = (
            await self._db.execute(
                select(ComisionModel.materia_id, func.count(InscripcionModel.id))
                .select_from(ComisionModel)
                .join(InscripcionModel, InscripcionModel.comision_id == ComisionModel.id)
                .group_by(ComisionModel.materia_id)
            )
        ).all()
        ex_rows = (
            await self._db.execute(
                select(ComisionModel.materia_id, func.count(ExamenContenidoModel.id))
                .select_from(ComisionModel)
                .join(ExamenContenidoModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .group_by(ComisionModel.materia_id)
            )
        ).all()
        ex_map = {mid: int(n or 0) for mid, n in ex_rows}
        out: dict[str, tuple[int, int]] = {}
        for mid, n in ins_rows:
            out[mid] = (int(n or 0), ex_map.get(mid, 0))
        for mid, n in ex_map.items():
            out.setdefault(mid, (0, n))
        return out

    async def eliminar(self, materia_id: str) -> bool:
        """Borra la materia (sus comisiones vacías caen por el FK ON DELETE CASCADE).

        Devuelve True si borró, False si no existía. El guard de "vacío" lo aplica
        la capa de aplicación ANTES; acá solo se ejecuta el borrado.
        """
        result = await self._db.execute(
            delete(MateriaModel)
            .where(MateriaModel.id == materia_id)
            .returning(MateriaModel.id)
        )
        borrado = result.scalar_one_or_none() is not None
        if borrado:
            await self._db.flush()
        return borrado

    async def materias_a_cargo(self, tutor_id: str) -> list[Materia]:
        """Materias (distintas) donde el tutor dado dicta alguna comisión (C-73 §9).

        c-79: filtra por membresía en ``comision_tutor`` (N:M) en vez de la vieja
        igualdad ``comision.docente_id`` (1:1). Contraparte de
        ``InscripcionSqlRepository.materias_inscriptas`` pero para el rol TUTOR.
        """
        if not _es_uuid(tutor_id):
            return []
        orden = _orden_alfabetico(MateriaModel.nombre).label("_orden_alfabetico")
        result = await self._db.execute(
            select(MateriaModel)
            .add_columns(orden)
            .join(ComisionModel, ComisionModel.materia_id == MateriaModel.id)
            .join(ComisionTutorModel, ComisionTutorModel.comision_id == ComisionModel.id)
            .where(ComisionTutorModel.tutor_id == tutor_id)
            .distinct()
            .order_by(orden)
        )
        return list(result.scalars().all())

    async def materias_a_cargo_coordinador(self, coordinador_id: str) -> list[Materia]:
        """Materias donde el coordinador dado figura en ``materia_coordinador`` (c-79).

        Contraparte de ``materias_a_cargo`` pero para el rol COORDINADOR — desde
        c-79 el coordinador ya NO tiene alcance global, queda acotado a SUS
        materias asignadas, igual que el tutor a sus comisiones.
        """
        if not _es_uuid(coordinador_id):
            return []
        orden = _orden_alfabetico(MateriaModel.nombre).label("_orden_alfabetico")
        result = await self._db.execute(
            select(MateriaModel)
            .add_columns(orden)
            .join(
                MateriaCoordinadorModel,
                MateriaCoordinadorModel.materia_id == MateriaModel.id,
            )
            .where(MateriaCoordinadorModel.coordinador_id == coordinador_id)
            .distinct()
            .order_by(orden)
        )
        return list(result.scalars().all())

    async def materias_a_cargo_profesor(self, profesor_id: str) -> list[Materia]:
        """Materias donde el profesor dado figura en ``materia_profesor`` (c-78).

        Contraparte de ``materias_a_cargo_coordinador`` para el rol PROFESOR: es
        un rol de MATERIA (arma exámenes y banco de toda la materia), acotado a
        las que tenga asignadas. Ningún rol salvo admin_sistema tiene alcance
        institucional.
        """
        if not _es_uuid(profesor_id):
            return []
        orden = _orden_alfabetico(MateriaModel.nombre).label("_orden_alfabetico")
        result = await self._db.execute(
            select(MateriaModel)
            .add_columns(orden)
            .join(
                MateriaProfesorModel,
                MateriaProfesorModel.materia_id == MateriaModel.id,
            )
            .where(MateriaProfesorModel.profesor_id == profesor_id)
            .distinct()
            .order_by(orden)
        )
        return list(result.scalars().all())

    async def agregar_profesor(self, materia_id: str, profesor_id: str) -> None:
        """Asigna un profesor a la materia (c-78). Idempotente."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(MateriaProfesorModel)
            .values(materia_id=materia_id, profesor_id=profesor_id)
            .on_conflict_do_nothing(index_elements=["materia_id", "profesor_id"])
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def quitar_profesor(self, materia_id: str, profesor_id: str) -> bool:
        """Quita un profesor de la materia. Devuelve True si había una fila."""
        result = await self._db.execute(
            delete(MateriaProfesorModel)
            .where(
                MateriaProfesorModel.materia_id == materia_id,
                MateriaProfesorModel.profesor_id == profesor_id,
            )
            .returning(MateriaProfesorModel.id)
        )
        borrado = result.scalar_one_or_none() is not None
        if borrado:
            await self._db.flush()
        return borrado

    async def profesores_de_materia(self, materia_id: str) -> list[str]:
        """ids de los profesores asignados a la materia (c-78)."""
        result = await self._db.execute(
            select(MateriaProfesorModel.profesor_id).where(
                MateriaProfesorModel.materia_id == materia_id
            )
        )
        return list(result.scalars().all())

    async def profesores_de_materias(
        self, materia_ids: list[str]
    ) -> dict[str, list[str]]:
        """materia_id -> ids de sus profesores, en UNA query (no N+1, c-78)."""
        limpios = [i for i in dict.fromkeys(materia_ids) if i]
        if not limpios:
            return {}
        result = await self._db.execute(
            select(
                MateriaProfesorModel.materia_id,
                MateriaProfesorModel.profesor_id,
            ).where(MateriaProfesorModel.materia_id.in_(limpios))
        )
        por_materia: dict[str, list[str]] = {}
        for materia_id, profesor_id in result.all():
            por_materia.setdefault(materia_id, []).append(profesor_id)
        return por_materia

    async def es_profesor_de_materia(self, profesor_id: str, materia_id: str) -> bool:
        """True si el profesor dado está asignado a la materia (c-78)."""
        if not (_es_uuid(profesor_id) and _es_uuid(materia_id)):
            return False
        result = await self._db.execute(
            select(MateriaProfesorModel.id)
            .where(
                MateriaProfesorModel.materia_id == materia_id,
                MateriaProfesorModel.profesor_id == profesor_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def agregar_coordinador(self, materia_id: str, coordinador_id: str) -> None:
        """Agrega un coordinador a la materia (c-79). Idempotente: si ya está
        asignado, no duplica (ON CONFLICT DO NOTHING vía el UNIQUE de la tabla)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(MateriaCoordinadorModel)
            .values(materia_id=materia_id, coordinador_id=coordinador_id)
            .on_conflict_do_nothing(
                index_elements=["materia_id", "coordinador_id"]
            )
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def quitar_coordinador(self, materia_id: str, coordinador_id: str) -> bool:
        """Quita un coordinador de la materia. Devuelve True si había una fila."""
        result = await self._db.execute(
            delete(MateriaCoordinadorModel)
            .where(
                MateriaCoordinadorModel.materia_id == materia_id,
                MateriaCoordinadorModel.coordinador_id == coordinador_id,
            )
            .returning(MateriaCoordinadorModel.id)
        )
        borrado = result.scalar_one_or_none() is not None
        if borrado:
            await self._db.flush()
        return borrado

    async def coordinadores_de_materia(self, materia_id: str) -> list[str]:
        """ids de los coordinadores asignados a la materia (c-79)."""
        result = await self._db.execute(
            select(MateriaCoordinadorModel.coordinador_id).where(
                MateriaCoordinadorModel.materia_id == materia_id
            )
        )
        return list(result.scalars().all())

    async def coordinadores_de_materias(
        self, materia_ids: list[str]
    ) -> dict[str, list[str]]:
        """materia_id -> ids de sus coordinadores, para un listado entero (c-79).

        Una sola query para toda la lista (no N+1, mismo criterio que
        ``nombres_de_docentes``). Las materias sin coordinador NO aparecen en el
        dict: el llamador cae a lista vacía.
        """
        limpios = [i for i in dict.fromkeys(materia_ids) if i]
        if not limpios:
            return {}
        result = await self._db.execute(
            select(
                MateriaCoordinadorModel.materia_id,
                MateriaCoordinadorModel.coordinador_id,
            ).where(MateriaCoordinadorModel.materia_id.in_(limpios))
        )
        por_materia: dict[str, list[str]] = {}
        for materia_id, coordinador_id in result.all():
            por_materia.setdefault(materia_id, []).append(coordinador_id)
        return por_materia

    async def es_coordinador_de_materia(self, coordinador_id: str, materia_id: str) -> bool:
        """True si el coordinador dado está asignado a la materia (c-79)."""
        if not (_es_uuid(coordinador_id) and _es_uuid(materia_id)):
            return False
        result = await self._db.execute(
            select(MateriaCoordinadorModel.id)
            .where(
                MateriaCoordinadorModel.materia_id == materia_id,
                MateriaCoordinadorModel.coordinador_id == coordinador_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


class ComisionSqlRepository:
    """CRUD async para la tabla comision (C-69 sección 6, D11)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def guardar(self, comision: Comision) -> Comision:
        """Persiste una comisión.

        Unicidad (C-70): distingue CUÁL constraint se violó:
        - (materia_id, codigo) → ComisionDuplicadaError.
        - codigo_matriculacion (global) → CodigoMatriculacionDuplicadoError
          (el alta con autogeneración la reintenta; un código provisto → 409).

        Requiere ``comision.codigo_matriculacion`` ya resuelto (autogenerado o
        provisto) por la capa de aplicación — el modelo lo exige NOT NULL.
        """
        model = ComisionModel(
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
        )
        self._db.add(model)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            if _es_violacion_unicidad(exc):
                if _nombre_constraint(exc) == "uq_comision_codigo_matriculacion":
                    raise CodigoMatriculacionDuplicadoError(
                        f"Ya existe una comisión con codigo_matriculacion "
                        f"{comision.codigo_matriculacion!r}."
                    ) from exc
                raise ComisionDuplicadaError(
                    f"Ya existe una comisión con codigo {comision.codigo!r} en esa materia."
                ) from exc
            raise
        return self._to_entity(model)

    async def obtener_por_codigo_matriculacion(self, codigo: str) -> Comision | None:
        """Lookup GLOBAL de una comisión por su codigo_matriculacion (C-70).

        Comparación EXACTA (case-sensitive): el código se guarda tal cual se tipeó.
        Devuelve None si ningún registro coincide.
        """
        result = await self._db.execute(
            select(ComisionModel).where(
                ComisionModel.codigo_matriculacion == codigo
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def actualizar_codigo_matriculacion(
        self, comision_id: str, nuevo_codigo: str
    ) -> Comision | None:
        """Reemplaza el codigo_matriculacion de una comisión (rotación, C-70).

        NO toca las inscripciones (rotar no desmatricula a nadie). Devuelve la
        comisión actualizada, o None si no existe.

        Raises:
            CodigoMatriculacionDuplicadoError: el nuevo código ya pertenece a otra
                comisión (viola uq_comision_codigo_matriculacion).
        """
        try:
            result = await self._db.execute(
                update(ComisionModel)
                .where(ComisionModel.id == comision_id)
                .values(codigo_matriculacion=nuevo_codigo)
                .returning(ComisionModel.id)
            )
        except IntegrityError as exc:
            await self._db.rollback()
            if _es_violacion_unicidad(exc):
                raise CodigoMatriculacionDuplicadoError(
                    f"Ya existe una comisión con codigo_matriculacion {nuevo_codigo!r}."
                ) from exc
            raise
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(comision_id)

    async def listar_por_materia(self, materia_id: str) -> list[Comision]:
        """Lista las comisiones de una materia (orden alfabético por nombre)."""
        result = await self._db.execute(
            select(ComisionModel)
            .where(ComisionModel.materia_id == materia_id)
            .order_by(_orden_alfabetico(ComisionModel.nombre))
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def listar_todas_con_materia(
        self, tutor_id: str | None = None
    ) -> list[tuple[Comision, str, str]]:
        """Todas las comisiones (join con materia), para un selector combinado
        "CÓDIGO - Materia" que no requiere elegir materia primero.

        ``tutor_id`` None = todas (staff); provisto = solo las comisiones que
        dicta ese tutor, across todas sus materias (C-73 §9, N:M desde c-79).
        Devuelve tuplas ``(comision, materia_nombre, materia_codigo)``.
        """
        stmt = (
            select(ComisionModel, MateriaModel.nombre, MateriaModel.codigo)
            .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
            .order_by(
                _orden_alfabetico(MateriaModel.nombre),
                _orden_alfabetico(ComisionModel.nombre),
            )
        )
        if tutor_id is not None:
            stmt = stmt.join(
                ComisionTutorModel, ComisionTutorModel.comision_id == ComisionModel.id
            ).where(ComisionTutorModel.tutor_id == tutor_id)
        result = await self._db.execute(stmt)
        return [
            (self._to_entity(comision), materia_nombre, materia_codigo)
            for comision, materia_nombre, materia_codigo in result.all()
        ]

    async def listar_todas_con_materia_coordinador(
        self, coordinador_id: str
    ) -> list[tuple[Comision, str, str]]:
        """Todas las comisiones de las materias que el coordinador dado coordina
        (c-79, N:M). Contraparte de ``listar_todas_con_materia`` para el rol
        COORDINADOR — ya no tiene alcance global, ve las comisiones de SUS
        materias asignadas (materia_coordinador)."""
        result = await self._db.execute(
            select(ComisionModel, MateriaModel.nombre, MateriaModel.codigo)
            .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
            .join(
                MateriaCoordinadorModel,
                MateriaCoordinadorModel.materia_id == MateriaModel.id,
            )
            .where(MateriaCoordinadorModel.coordinador_id == coordinador_id)
            .order_by(
                _orden_alfabetico(MateriaModel.nombre),
                _orden_alfabetico(ComisionModel.nombre),
            )
        )
        return [
            (self._to_entity(comision), materia_nombre, materia_codigo)
            for comision, materia_nombre, materia_codigo in result.all()
        ]

    async def obtener(self, comision_id: str) -> Comision | None:
        model = await self._db.get(ComisionModel, comision_id)
        if model is None:
            return None
        return self._to_entity(model)

    async def actualizar(
        self,
        comision_id: str,
        *,
        nombre: str,
        periodo: str | None,
        anio: int | None,
    ) -> Comision | None:
        """Actualiza nombre/periodo/anio de una comisión (codigo y materia_id inmutables).

        Devuelve la comisión actualizada, o None si no existe. No valida: la
        validación de dominio la hace el caller (capa de aplicación) antes.
        """
        result = await self._db.execute(
            update(ComisionModel)
            .where(ComisionModel.id == comision_id)
            .values(nombre=nombre, periodo=periodo, anio=anio)
            .returning(ComisionModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(comision_id)

    async def set_activa(self, comision_id: str, activa: bool) -> Comision | None:
        """Setea el estado `activa` de una comisión (baja lógica, C-72 §17).

        Devuelve la comisión actualizada, o None si no existe. No desmatricula ni
        borra nada: solo cambia el flag.
        """
        result = await self._db.execute(
            update(ComisionModel)
            .where(ComisionModel.id == comision_id)
            .values(activa=activa)
            .returning(ComisionModel.id)
        )
        if result.scalar_one_or_none() is None:
            return None
        await self._db.flush()
        return await self.obtener(comision_id)

    async def contar_inscriptos_y_examenes(self, comision_id: str) -> tuple[int, int]:
        """Cuenta (inscriptos, examenes) de la comisión. Insumo del guard de borrado."""
        inscriptos = await self._db.scalar(
            select(func.count())
            .select_from(InscripcionModel)
            .where(InscripcionModel.comision_id == comision_id)
        )
        examenes = await self._db.scalar(
            select(func.count())
            .select_from(ExamenContenidoModel)
            .where(ExamenContenidoModel.comision_id == comision_id)
        )
        return int(inscriptos or 0), int(examenes or 0)

    async def contar_inscriptos_y_examenes_por_materia(
        self, materia_id: str
    ) -> dict[str, tuple[int, int]]:
        """(inscriptos, examenes) por comisión de una materia, en 2 queries.

        Evita el N+1 del listado: la UI oculta el botón de eliminar en las
        comisiones que tienen inscriptos/exámenes. Comisiones vacías no aparecen
        en los mapas → se resuelven a (0, 0) en el caller.
        """
        ins_rows = (
            await self._db.execute(
                select(InscripcionModel.comision_id, func.count(InscripcionModel.id))
                .join(ComisionModel, InscripcionModel.comision_id == ComisionModel.id)
                .where(ComisionModel.materia_id == materia_id)
                .group_by(InscripcionModel.comision_id)
            )
        ).all()
        ex_rows = (
            await self._db.execute(
                select(ExamenContenidoModel.comision_id, func.count(ExamenContenidoModel.id))
                .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .where(ComisionModel.materia_id == materia_id)
                .group_by(ExamenContenidoModel.comision_id)
            )
        ).all()
        ex_map = {cid: int(n or 0) for cid, n in ex_rows}
        out: dict[str, tuple[int, int]] = {}
        for cid, n in ins_rows:
            out[cid] = (int(n or 0), ex_map.get(cid, 0))
        for cid, n in ex_map.items():
            out.setdefault(cid, (0, n))
        return out

    async def eliminar(self, comision_id: str) -> bool:
        """Borra la comisión. Devuelve True si borró, False si no existía.

        El guard de "vacía" lo aplica la capa de aplicación ANTES.
        """
        result = await self._db.execute(
            delete(ComisionModel)
            .where(ComisionModel.id == comision_id)
            .returning(ComisionModel.id)
        )
        borrado = result.scalar_one_or_none() is not None
        if borrado:
            await self._db.flush()
        return borrado

    async def agregar_tutor(self, comision_id: str, tutor_id: str) -> None:
        """Agrega un tutor a cargo de la comisión (c-79, N:M). Idempotente: si ya
        está asignado, no duplica (ON CONFLICT DO NOTHING vía el UNIQUE)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(ComisionTutorModel)
            .values(comision_id=comision_id, tutor_id=tutor_id)
            .on_conflict_do_nothing(index_elements=["comision_id", "tutor_id"])
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def quitar_tutor(self, comision_id: str, tutor_id: str) -> bool:
        """Quita un tutor de la comisión. Devuelve True si había una fila."""
        result = await self._db.execute(
            delete(ComisionTutorModel)
            .where(
                ComisionTutorModel.comision_id == comision_id,
                ComisionTutorModel.tutor_id == tutor_id,
            )
            .returning(ComisionTutorModel.id)
        )
        borrado = result.scalar_one_or_none() is not None
        if borrado:
            await self._db.flush()
        return borrado

    async def tutores_de_comision(self, comision_id: str) -> list[str]:
        """ids de los tutores a cargo de la comisión (c-79, N:M)."""
        result = await self._db.execute(
            select(ComisionTutorModel.tutor_id).where(
                ComisionTutorModel.comision_id == comision_id
            )
        )
        return list(result.scalars().all())

    async def tiene_pertenencia_sobre_comision(
        self,
        usuario_id: str,
        comision_id: str,
        *,
        es_coordinador: bool = False,
        es_profesor: bool = False,
    ) -> bool:
        """Pertenencia sobre una COMISIÓN puntual: tutor de esa comisión, o (si
        ``es_coordinador``) coordinador de su materia (C-74 post-cierre, c-79), o
        (si ``es_profesor``) profesor de su materia (c-78, materia_profesor)."""
        if not (_es_uuid(usuario_id) and _es_uuid(comision_id)):
            return False
        if es_profesor:
            result = await self._db.execute(
                select(MateriaProfesorModel.id)
                .select_from(ComisionModel)
                .join(
                    MateriaProfesorModel,
                    MateriaProfesorModel.materia_id == ComisionModel.materia_id,
                )
                .where(
                    ComisionModel.id == comision_id,
                    MateriaProfesorModel.profesor_id == usuario_id,
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
        if es_coordinador:
            result = await self._db.execute(
                select(MateriaCoordinadorModel.id)
                .select_from(ComisionModel)
                .join(
                    MateriaCoordinadorModel,
                    MateriaCoordinadorModel.materia_id == ComisionModel.materia_id,
                )
                .where(
                    ComisionModel.id == comision_id,
                    MateriaCoordinadorModel.coordinador_id == usuario_id,
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None
        result = await self._db.execute(
            select(ComisionTutorModel.id)
            .where(
                ComisionTutorModel.comision_id == comision_id,
                ComisionTutorModel.tutor_id == usuario_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def nombres_de_docentes(self, ids: list[str]) -> dict[str, str]:
        """id de usuario -> nombre visible, para las comisiones de un listado. C-73 §9.

        Una sola query para todo el listado (no N+1). Cae al legajo cuando el usuario
        no tiene nombre cargado — usuarios federados/seed viejos pueden no tenerlo, y
        mostrar un UUID en pantalla no le sirve a nadie."""
        limpios = [i for i in dict.fromkeys(ids) if i]
        if not limpios:
            return {}
        result = await self._db.execute(
            select(
                UsuarioModel.id,
                UsuarioModel.nombre,
                UsuarioModel.apellido,
                UsuarioModel.username,
            ).where(UsuarioModel.id.in_(limpios))
        )
        nombres: dict[str, str] = {}
        for uid, nombre, apellido, legajo in result.all():
            completo = " ".join(p for p in (nombre, apellido) if p).strip()
            nombres[uid] = completo or legajo
        return nombres

    async def tiene_pertenencia_sobre_examen(
        self,
        usuario_id: str,
        examen_id: str,
        *,
        es_coordinador: bool = False,
        es_profesor: bool = False,
    ) -> bool:
        """Pertenencia sobre el examen: tutor de su comisión, o (si
        ``es_coordinador``) coordinador de su materia (C-73 §9, N:M desde c-79).

        Reemplaza a ``docente_de_examen`` + comparación por igualdad: ahora es una
        pregunta de MEMBRESÍA (comision_tutor / materia_coordinador), no de "quién
        es el dueño único". Devuelve ``False`` si el examen no existe, no tiene
        comisión, o nadie con ese id está a cargo."""
        if not (_es_uuid(usuario_id) and _es_uuid(examen_id)):
            return False
        if es_profesor:
            # c-78: el profesor es rol de MATERIA — pertenece a todo examen de
            # cualquier comisión de las materias que tiene asignadas.
            result = await self._db.execute(
                select(MateriaProfesorModel.id)
                .select_from(ExamenContenidoModel)
                .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .join(
                    MateriaProfesorModel,
                    MateriaProfesorModel.materia_id == ComisionModel.materia_id,
                )
                .where(
                    ExamenContenidoModel.id == examen_id,
                    MateriaProfesorModel.profesor_id == usuario_id,
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
        if es_coordinador:
            result = await self._db.execute(
                select(MateriaCoordinadorModel.id)
                .select_from(ExamenContenidoModel)
                .join(ComisionModel, ExamenContenidoModel.comision_id == ComisionModel.id)
                .join(
                    MateriaCoordinadorModel,
                    MateriaCoordinadorModel.materia_id == ComisionModel.materia_id,
                )
                .where(
                    ExamenContenidoModel.id == examen_id,
                    MateriaCoordinadorModel.coordinador_id == usuario_id,
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None
        result = await self._db.execute(
            select(ComisionTutorModel.id)
            .select_from(ExamenContenidoModel)
            .join(
                ComisionTutorModel,
                ComisionTutorModel.comision_id == ExamenContenidoModel.comision_id,
            )
            .where(
                ExamenContenidoModel.id == examen_id,
                ComisionTutorModel.tutor_id == usuario_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def es_docente_de_materia(self, docente_id: str, materia_id: str) -> bool:
        """True si el docente dado dicta AL MENOS UNA comisión de la materia.

        c-79: filtra por membresía en ``comision_tutor`` (N:M). Reemplaza al viejo
        ``docente_de_materia`` (bug real, C-74 post-cierre): ese método devolvía un
        docente ARBITRARIO de la materia (``.limit(1)``, sin filtrar por quién
        pregunta) y el caller comparaba identidad contra ESE — un docente real que
        dicta una comisión distinta de la que la query devolvía primero era
        rechazado con falso negativo. Acá se filtra directamente por
        ``docente_id`` — es una pregunta de membresía, no de "quién es el dueño
        arbitrario"."""
        if not (_es_uuid(docente_id) and _es_uuid(materia_id)):
            return False
        result = await self._db.execute(
            select(ComisionModel.id)
            .join(ComisionTutorModel, ComisionTutorModel.comision_id == ComisionModel.id)
            .where(
                ComisionModel.materia_id == materia_id,
                ComisionTutorModel.tutor_id == docente_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def comision_ids_a_cargo(self, docente_id: str) -> list[str]:
        """Comisiones donde el docente dado es tutor (c-79, N:M).

        Contraparte de ``InscripcionSqlRepository.comision_ids_inscriptas`` pero
        para el rol DOCENTE (C-73 §9): un docente no se "inscribe" a su propia
        comisión como alumno, así que el gate de catálogo necesita esta fuente
        distinta — "lo que dicta", no "lo que cursa".
        """
        if not _es_uuid(docente_id):
            return []
        result = await self._db.execute(
            select(ComisionTutorModel.comision_id).where(
                ComisionTutorModel.tutor_id == docente_id
            )
        )
        return list(result.scalars().all())

    async def comision_ids_a_cargo_coordinador(self, coordinador_id: str) -> list[str]:
        """Comisiones de las materias que el coordinador dado coordina (c-79).

        Contraparte de ``comision_ids_a_cargo`` (tutor) para el rol COORDINADOR:
        ve TODAS las comisiones de sus materias asignadas, no solo las que dicta.
        """
        if not _es_uuid(coordinador_id):
            return []
        result = await self._db.execute(
            select(ComisionModel.id)
            .join(
                MateriaCoordinadorModel,
                MateriaCoordinadorModel.materia_id == ComisionModel.materia_id,
            )
            .where(MateriaCoordinadorModel.coordinador_id == coordinador_id)
        )
        return list(result.scalars().all())

    async def comision_ids_a_cargo_profesor(self, profesor_id: str) -> list[str]:
        """Comisiones de las materias que el profesor dado tiene asignadas (c-78).

        Igual criterio que ``comision_ids_a_cargo_coordinador``: el PROFESOR es un
        rol de MATERIA, así que su alcance son TODAS las comisiones de sus
        materias, no solo las que dicta.
        """
        if not _es_uuid(profesor_id):
            return []
        result = await self._db.execute(
            select(ComisionModel.id)
            .join(
                MateriaProfesorModel,
                MateriaProfesorModel.materia_id == ComisionModel.materia_id,
            )
            .where(MateriaProfesorModel.profesor_id == profesor_id)
        )
        return list(result.scalars().all())

    async def listar_todas_con_materia_profesor(
        self, profesor_id: str
    ) -> list[tuple[Comision, str, str]]:
        """Comisiones de las materias que el profesor coordina académicamente
        (c-78). Contraparte de ``listar_todas_con_materia_coordinador``."""
        result = await self._db.execute(
            select(ComisionModel, MateriaModel.nombre, MateriaModel.codigo)
            .join(MateriaModel, MateriaModel.id == ComisionModel.materia_id)
            .join(
                MateriaProfesorModel,
                MateriaProfesorModel.materia_id == MateriaModel.id,
            )
            .where(MateriaProfesorModel.profesor_id == profesor_id)
            .order_by(
                _orden_alfabetico(MateriaModel.nombre),
                _orden_alfabetico(ComisionModel.nombre),
            )
        )
        return [
            (self._to_entity(comision), materia_nombre, materia_codigo)
            for comision, materia_nombre, materia_codigo in result.all()
        ]

    async def listar_a_cargo_de_materia(
        self, docente_id: str, materia_id: str
    ) -> list[Comision]:
        """Comisiones de una materia donde el docente dado es tutor (C-73 §9, N:M)."""
        result = await self._db.execute(
            select(ComisionModel)
            .join(ComisionTutorModel, ComisionTutorModel.comision_id == ComisionModel.id)
            .where(
                ComisionModel.materia_id == materia_id,
                ComisionTutorModel.tutor_id == docente_id,
            )
            .order_by(_orden_alfabetico(ComisionModel.nombre))
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    def _to_entity(self, model: ComisionModel) -> Comision:
        return Comision(
            id=model.id,
            materia_id=model.materia_id,
            codigo=model.codigo,
            nombre=model.nombre,
            periodo=model.periodo,
            anio=model.anio,
            codigo_matriculacion=model.codigo_matriculacion,
            activa=model.activa,
        )


class InscripcionSqlRepository:
    """CRUD async para la tabla inscripcion (C-69): alumno↔comisión."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def inscribir(self, usuario_id: str, comision_id: str) -> InscripcionModel:
        """Inscribe un alumno a una comisión.

        Raises:
            InscripcionDuplicadaError: el alumno ya está inscripto a esa comisión
                (viola UNIQUE(usuario_id, comision_id)).
        """
        model = InscripcionModel(usuario_id=usuario_id, comision_id=comision_id)
        self._db.add(model)
        try:
            await self._db.flush()
        except IntegrityError as exc:
            await self._db.rollback()
            if _es_violacion_unicidad(exc):
                raise InscripcionDuplicadaError(
                    f"El usuario {usuario_id!r} ya está inscripto a la comisión "
                    f"{comision_id!r}."
                ) from exc
            raise
        return model

    async def eliminar(self, usuario_id: str, comision_id: str) -> bool:
        """Elimina la inscripción del alumno a la comisión.

        Devuelve True si se borró una fila; False si no existía (→ 404 en el caller).
        """
        result = await self._db.execute(
            delete(InscripcionModel).where(
                InscripcionModel.usuario_id == usuario_id,
                InscripcionModel.comision_id == comision_id,
            )
        )
        await self._db.flush()
        return (result.rowcount or 0) > 0

    async def alumno_rindio_en_comision(self, usuario_id: str, comision_id: str) -> bool:
        """True si el alumno tiene alguna sesión de proctoring en un examen de la comisión.

        Guarda de baja de inscripción: si hay actividad, la baja se bloquea para no
        huerfanar la sesión/evidencia/nota (cadena de custodia). Cruza
        ``usuario.username`` con ``proctoring_session.alumno_idnumber`` sobre
        los exámenes cuya ``comision_id`` es la de la inscripción.
        """
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        idnumber = (
            select(UsuarioModel.username)
            .where(UsuarioModel.id == usuario_id)
            .scalar_subquery()
        )
        examenes_de_comision = select(ExamenContenidoModel.id).where(
            ExamenContenidoModel.comision_id == comision_id
        )
        n = (
            await self._db.execute(
                select(func.count())
                .select_from(ProctoringSessionModel)
                .where(
                    ProctoringSessionModel.alumno_idnumber == idnumber,
                    ProctoringSessionModel.examen_contenido_id.in_(examenes_de_comision),
                )
            )
        ).scalar_one()
        return int(n or 0) > 0

    async def existe(self, usuario_id: str, comision_id: str) -> bool:
        """True si el alumno ya está inscripto a la comisión."""
        result = await self._db.execute(
            select(InscripcionModel.id).where(
                InscripcionModel.usuario_id == usuario_id,
                InscripcionModel.comision_id == comision_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def esta_inscripto_institucional(
        self, username: str, comision_id: str
    ) -> bool:
        """True si el alumno (por username del JWT) está inscripto a la comisión.

        Gate de inscripción (C-71): resuelve username → usuario.id (JOIN
        usuario) y verifica la fila en inscripcion. La identidad del alumno es el
        username del principal, nunca un dato del cliente (regla dura #6).
        """
        result = await self._db.execute(
            select(InscripcionModel.id)
            .join(UsuarioModel, UsuarioModel.id == InscripcionModel.usuario_id)
            .where(
                UsuarioModel.username == username,
                UsuarioModel.eliminado_en.is_(None),
                InscripcionModel.comision_id == comision_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def comision_ids_inscriptas(self, username: str) -> list[str]:
        """Lista los comision_id donde el alumno (por username) está inscripto.

        Se usa para filtrar el catálogo de exámenes/materias del alumno (C-71).
        """
        result = await self._db.execute(
            select(InscripcionModel.comision_id)
            .join(UsuarioModel, UsuarioModel.id == InscripcionModel.usuario_id)
            .where(
                UsuarioModel.username == username,
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        return list(result.scalars().all())

    async def materias_inscriptas(self, username: str) -> list[MateriaModel]:
        """Materias (distintas) donde el alumno tiene alguna comisión inscripta (C-71).

        La clave de orden va TAMBIÉN en el SELECT: con ``DISTINCT``, Postgres exige
        que toda expresión del ORDER BY esté en la lista de selección
        (InvalidColumnReference si no). Es determinista igual: la clave se deriva de
        ``nombre``, así que no agrega filas al conjunto distinto.
        """
        orden = _orden_alfabetico(MateriaModel.nombre).label("_orden_alfabetico")
        result = await self._db.execute(
            select(MateriaModel)
            .add_columns(orden)
            .join(ComisionModel, ComisionModel.materia_id == MateriaModel.id)
            .join(InscripcionModel, InscripcionModel.comision_id == ComisionModel.id)
            .join(UsuarioModel, UsuarioModel.id == InscripcionModel.usuario_id)
            .where(
                UsuarioModel.username == username,
                UsuarioModel.eliminado_en.is_(None),
            )
            .distinct()
            .order_by(orden)
        )
        # scalars() toma la primera columna de cada fila = la entidad MateriaModel;
        # la clave de orden viaja solo para satisfacer el DISTINCT.
        return list(result.scalars().all())

    async def comisiones_inscriptas_de_materia(
        self, username: str, materia_id: str
    ) -> list[ComisionModel]:
        """Comisiones de una materia donde el alumno está inscripto (C-71)."""
        result = await self._db.execute(
            select(ComisionModel)
            .join(InscripcionModel, InscripcionModel.comision_id == ComisionModel.id)
            .join(UsuarioModel, UsuarioModel.id == InscripcionModel.usuario_id)
            .where(
                UsuarioModel.username == username,
                UsuarioModel.eliminado_en.is_(None),
                ComisionModel.materia_id == materia_id,
            )
            .order_by(ComisionModel.codigo)
        )
        return list(result.scalars().all())

    async def obtener_usuario_id_por_username(
        self, username: str
    ) -> str | None:
        """Resuelve usuario.id (FK) desde el username del principal (C-70).

        Devuelve None si no hay un usuario ACTIVO (no dado de baja) con ese
        username. Se usa en la auto-matriculación: el usuario_id sale del
        principal autenticado, NUNCA del body (cliente = sensor no confiable).
        """
        result = await self._db.execute(
            select(UsuarioModel.id).where(
                UsuarioModel.username == username,
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def usuario_existe(self, usuario_id: str) -> bool:
        """True si existe un usuario ACTIVO (no dado de baja) con ese id."""
        result = await self._db.execute(
            select(UsuarioModel.id).where(
                UsuarioModel.id == usuario_id,
                UsuarioModel.eliminado_en.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def listar_usuarios_de_comision(
        self, comision_id: str
    ) -> list[UsuarioModel]:
        """Lista los usuarios ACTIVOS inscriptos a la comisión (orden estable).

        Join inscripcion→usuario filtrando dados de baja (eliminado_en IS NULL).
        Orden alfabético por apellido y nombre (NULLs al final) para un listado
        determinístico.

        c-78 §13.4: cada usuario sale con ``inscripto_en`` proyectado (atributo NO
        mapeado, en memoria) — el export de inscriptos lo necesita para cruzar
        contra el padrón del campus, y sin esto habría que hacer una query por
        alumno solo para la fecha.
        """
        result = await self._db.execute(
            select(UsuarioModel, InscripcionModel.created_at.label("inscripto_en"))
            .join(InscripcionModel, InscripcionModel.usuario_id == UsuarioModel.id)
            .where(
                InscripcionModel.comision_id == comision_id,
                UsuarioModel.eliminado_en.is_(None),
            )
            .order_by(
                UsuarioModel.apellido.asc().nulls_last(),
                UsuarioModel.nombre.asc().nulls_last(),
                UsuarioModel.id.asc(),
            )
        )
        usuarios: list[UsuarioModel] = []
        for usuario, inscripto_en in result.all():
            usuario.inscripto_en = inscripto_en
            usuarios.append(usuario)
        return usuarios
