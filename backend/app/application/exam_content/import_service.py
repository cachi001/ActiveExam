"""Servicio de importación de Moodle XML → ExamenContenido (C-69, C-74).

Orquesta: parse XML → validar preguntas → resolver categorías → persistir → reporte.
Preguntas que no superan la validación de dominio se reportan como omitidas
sin abortar la importación.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import uuid

import sqlalchemy as sa

from app.application.exam_content.errors import LimitePreguntasExcedidoError
from app.application.exam_content.moodle_parser import BlankData, PreguntaData, PreguntaOmitida, parse_moodle_xml
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.domain.exam_content.errors import PreguntaInvalidaError
from app.domain.exam_content.ports import AbstractExamenContenidoRepository
from app.infrastructure.persistence.repositories.categoria_pregunta import (
    CategoriaPreguntaSqlRepository,
)

# Tope duro del sistema: ningún examen puede importar más preguntas que esto, se
# pida el tope que se pida. Protege de un XML enorme (accidental o no) que haría
# impracticable la pantalla de selección y la rendición.
LIMITE_PREGUNTAS_SISTEMA = 500


@dataclass
class OmitidaItem:
    tipo: str
    nombre: str
    motivo: str = ""


@dataclass
class ImportReport:
    examen_id: str
    importadas: int
    omitidas: list[OmitidaItem] = field(default_factory=list)


@dataclass
class PreguntaImportadaItem:
    enunciado: str
    tipo: str


@dataclass
class ImportBancoReport:
    """Resultado de importar un XML directo al banco de preguntas (sin examen)."""

    preguntas_nuevas: int
    preguntas_actualizadas: int
    omitidas: list[OmitidaItem] = field(default_factory=list)
    nuevas: list[PreguntaImportadaItem] = field(default_factory=list)
    actualizadas: list[PreguntaImportadaItem] = field(default_factory=list)


@dataclass
class PreviewCategoria:
    ruta: list[str]
    preguntas_por_tipo: dict[str, int]
    preguntas: list[PreguntaImportadaItem] = field(default_factory=list)


@dataclass
class PreviewImportBancoReport:
    """Preview de qué trae un XML — SIN tocar la DB (ni resolver categorías reales,
    ni upsertear preguntas). Agrupa por la ruta cruda que trae el XML."""

    categorias: list[PreviewCategoria]
    sin_categoria_por_tipo: dict[str, int]
    omitidas: list[OmitidaItem]
    total_preguntas: int
    sin_categoria_preguntas: list[PreguntaImportadaItem] = field(default_factory=list)


def preview_import_banco(xml_bytes: bytes) -> PreviewImportBancoReport:
    """Parsea el XML y arma el preview: árbol de categorías + conteo por tipo.

    Pura: no abre sesión de DB, no persiste nada. Usa la misma validación de
    dominio que el import real para que "omitidas" en el preview coincida con
    lo que después omitiría el import de verdad.
    """
    parse_result = parse_moodle_xml(xml_bytes)

    omitidas: list[OmitidaItem] = [
        OmitidaItem(tipo=o.tipo, nombre=o.nombre, motivo="tipo no soportado")
        for o in parse_result.omitidas
    ]

    por_ruta: dict[tuple[str, ...], dict[str, int]] = {}
    preguntas_por_ruta: dict[tuple[str, ...], list[PreguntaImportadaItem]] = {}
    sin_categoria: dict[str, int] = {}
    sin_categoria_preguntas: list[PreguntaImportadaItem] = []
    total = 0

    for p_data in parse_result.preguntas:
        try:
            _pregunta_data_to_entity(p_data, categoria_id=None)
        except PreguntaInvalidaError as exc:
            omitidas.append(
                OmitidaItem(tipo=p_data.tipo, nombre=p_data.enunciado[:60], motivo=str(exc))
            )
            continue

        total += 1
        item = PreguntaImportadaItem(enunciado=p_data.enunciado, tipo=p_data.tipo)
        if p_data.categoria_ruta:
            clave = tuple(p_data.categoria_ruta)
            conteo = por_ruta.setdefault(clave, {})
            preguntas_por_ruta.setdefault(clave, []).append(item)
        else:
            conteo = sin_categoria
            sin_categoria_preguntas.append(item)
        conteo[p_data.tipo] = conteo.get(p_data.tipo, 0) + 1

    categorias = [
        PreviewCategoria(
            ruta=list(ruta),
            preguntas_por_tipo=conteo,
            preguntas=preguntas_por_ruta.get(ruta, []),
        )
        for ruta, conteo in por_ruta.items()
    ]

    return PreviewImportBancoReport(
        categorias=categorias,
        sin_categoria_por_tipo=sin_categoria,
        omitidas=omitidas,
        total_preguntas=total,
        sin_categoria_preguntas=sin_categoria_preguntas,
    )


#: Clave sentinel para "sin categoría" en ``categorias_excluidas`` — un ``None``/
#: tupla vacía no puede ir en un set junto con tuplas de ruta sin ambigüedad
#: (una ruta real nunca puede colisionar con este string).
SIN_CATEGORIA_SENTINEL: tuple[str, ...] = ("__sin_categoria__",)


async def importar_banco_desde_xml(
    session,
    xml_bytes: bytes,
    materia_id: str,
    categorias_excluidas: set[tuple[str, ...]] | None = None,
    categoria_padre_id: str | None = None,
) -> ImportBancoReport:
    """Importa un XML de Moodle directo a ``pregunta_banco``/``categoria_pregunta``.

    A diferencia de ``ImportacionMoodleService.importar()``, NO crea ningún
    ``examen_contenido``: el banco de preguntas es el destino, no un examen. El
    examen se arma después, por separado, sorteando desde el banco
    (``crear-desde-banco``).

    ``categorias_excluidas``: rutas (tuplas de segmentos, igual que
    ``PreviewCategoria.ruta``) que el docente destildó en el preview antes de
    confirmar — esas preguntas NO se persisten. ``SIN_CATEGORIA_SENTINEL``
    excluye las preguntas sin categoría. Filtrar ANTES de resolver categorías:
    si una categoría queda 100% excluida, no se crea vacía en el banco.

    ``categoria_padre_id``: id de una categoría YA EXISTENTE (elegida por el
    docente en un selector, no tipeada) bajo la cual anidar TODO lo que traiga
    el XML. Bug real (2026-08-21, campus FRM): Moodle exporta cada subcategoría
    con el path completo (``$course$/top/Clase 1...``) pero nunca emite una
    categoría propia para el nodo "top" en sí — ese nombre (ej. "Superior para
    Programación 3-2026 Agosto") es solo la etiqueta que Moodle le pone al
    dropdown de export, no una categoría real — así que las subcategorías
    quedaban sueltas en ActiveExam sin ningún padre común. Se usa un ID (no un
    nombre libre) para no depender de un match de string exacto entre imports
    (``resolver_o_crear`` matchea por string exacto: un typo/tilde distinta
    crearía una carpeta duplicada en vez de reusar la existente).

    Escritura en LOTES, no pregunta por pregunta (perf): con un banco real de
    232 preguntas, la versión secuencial (1-2 SELECT + varios INSERT por
    pregunta, todo awaited uno por uno) tardaba ~55s — cada await es un
    round-trip de red a Postgres. Acá se resuelve "nueva vs actualizada" con
    UNA sola consulta que trae todo el banco existente de la materia, y las
    escrituras van en ~6 sentencias con executemany (una lista de dicts por
    sentencia) en vez de una sentencia por fila.
    """
    parse_result = parse_moodle_xml(xml_bytes)

    omitidas: list[OmitidaItem] = [
        OmitidaItem(tipo=o.tipo, nombre=o.nombre, motivo="tipo no soportado")
        for o in parse_result.omitidas
    ]

    excluidas = categorias_excluidas or set()
    preguntas_a_procesar = [
        p_data
        for p_data in parse_result.preguntas
        if (tuple(p_data.categoria_ruta) if p_data.categoria_ruta else SIN_CATEGORIA_SENTINEL)
        not in excluidas
    ]

    cat_repo = CategoriaPreguntaSqlRepository(session)
    ruta_memo: dict[tuple[str, ...], str] = {}

    # 1. Validar + resolver categoría por pregunta. La resolución de categoría
    #    ya está memoizada por ruta (ruta_memo) — barata incluso para cientos
    #    de preguntas, porque el número de categorías ÚNICAS es chico.
    validas: list[tuple[PreguntaData, str | None]] = []
    for p_data in preguntas_a_procesar:
        categoria_id: str | None = categoria_padre_id
        if p_data.categoria_ruta:
            categoria_id = await _resolver_ruta(
                cat_repo, materia_id, p_data.categoria_ruta, ruta_memo, categoria_padre_id
            )
        try:
            _pregunta_data_to_entity(p_data, categoria_id=categoria_id)
        except PreguntaInvalidaError as exc:
            omitidas.append(
                OmitidaItem(tipo=p_data.tipo, nombre=p_data.enunciado[:60], motivo=str(exc))
            )
            continue
        validas.append((p_data, categoria_id))

    if not validas:
        return ImportBancoReport(preguntas_nuevas=0, preguntas_actualizadas=0, omitidas=omitidas)

    # Deduplicar DENTRO del mismo archivo, con el MISMO criterio de identidad que
    # se usa después contra la base: moodle_question_id → nombre → (enunciado, tipo).
    # Sin esto, dos preguntas "iguales" en el mismo XML sin id crearían dos
    # filas nuevas en vez de que la última pise a la primera (como hacía la
    # versión secuencial, que las veía como "ya existe" en la 2da vuelta).
    dedup: dict[tuple, tuple[PreguntaData, str | None]] = {}
    orden_dedup: list[tuple] = []
    for p_data, categoria_id in validas:
        moodle_qid = getattr(p_data, "moodle_question_id", None)
        nombre = getattr(p_data, "nombre_moodle", None)
        if moodle_qid:
            key: tuple = ("qid", moodle_qid)
        elif nombre:
            key = ("nom", nombre, p_data.tipo)
        else:
            key = ("et", p_data.enunciado, p_data.tipo)
        if key not in dedup:
            orden_dedup.append(key)
        dedup[key] = (p_data, categoria_id)
    validas = [dedup[k] for k in orden_dedup]

    # 2. UNA consulta: todo lo que ya existe en el banco de esta materia, para
    #    resolver nueva/actualizada en memoria (antes: 1-2 SELECT por pregunta).
    existentes_result = await session.execute(
        sa.text(
            "SELECT id, moodle_question_id, nombre_moodle, enunciado, tipo, "
            "categoria_manual, categoria_id FROM pregunta_banco WHERE materia_id = :mid"
        ),
        {"mid": materia_id},
    )
    por_qid: dict[int, dict] = {}
    por_nombre_tipo: dict[tuple[str, str], dict] = {}
    por_enunciado_tipo: dict[tuple[str, str], dict] = {}
    for row in existentes_result.mappings():
        if row["moodle_question_id"] is not None:
            por_qid.setdefault(row["moodle_question_id"], row)
        if row["nombre_moodle"]:
            por_nombre_tipo.setdefault((row["nombre_moodle"], row["tipo"]), row)
        por_enunciado_tipo.setdefault((row["enunciado"], row["tipo"]), row)

    nuevas_rows: list[dict] = []
    actualizadas_rows: list[dict] = []
    banco_ids_actualizadas: list[str] = []
    opciones_rows: list[dict] = []
    blanks_rows: list[dict] = []
    blank_opciones_rows: list[dict] = []
    nuevas_items: list[PreguntaImportadaItem] = []
    actualizadas_items: list[PreguntaImportadaItem] = []

    for p_data, categoria_id in validas:
        moodle_qid = getattr(p_data, "moodle_question_id", None)
        nombre = getattr(p_data, "nombre_moodle", None)
        # Orden de reconocimiento, del más confiable al de respaldo:
        #   1. moodle_question_id — solo lo trae el sync vía API.
        #   2. nombre_moodle      — lo trae el XML y sobrevive a que editen el texto.
        #   3. enunciado          — para lo cargado antes de que se guardara el nombre.
        # Sin el paso 2, corregir una errata y volver a subir el banco daba de alta
        # la pregunta OTRA VEZ y dejaba viva la versión vieja.
        existente = por_qid.get(moodle_qid) if moodle_qid else None
        if existente is None and nombre:
            existente = por_nombre_tipo.get((nombre, p_data.tipo))
        if existente is None:
            existente = por_enunciado_tipo.get((p_data.enunciado, p_data.tipo))

        if existente is not None:
            # Regla de propiedad (0058): si el docente movió la pregunta a
            # mano (categoria_manual), Moodle no la vuelve a recategorizar.
            banco_id = str(existente["id"])
            cat_final = (
                existente["categoria_id"] if existente["categoria_manual"] else categoria_id
            )
            actualizadas_rows.append(
                {
                    "id": banco_id,
                    "enunciado": p_data.enunciado,
                    "qid": moodle_qid,
                    "cat_id": cat_final,
                    # Se refresca también en las que ya estaban: así una pregunta
                    # cargada antes de la migración gana su clave estable en el
                    # primer reimport, y el siguiente ya la reconoce por nombre.
                    "nombre": nombre,
                }
            )
            banco_ids_actualizadas.append(banco_id)
            actualizadas_items.append(
                PreguntaImportadaItem(enunciado=p_data.enunciado, tipo=p_data.tipo)
            )
        else:
            banco_id = str(uuid.uuid4())
            nuevas_rows.append(
                {
                    "id": banco_id,
                    "materia_id": materia_id,
                    "enunciado": p_data.enunciado,
                    "tipo": p_data.tipo,
                    "categoria_id": categoria_id,
                    "moodle_question_id": moodle_qid,
                    "nombre_moodle": nombre,
                }
            )
            nuevas_items.append(
                PreguntaImportadaItem(enunciado=p_data.enunciado, tipo=p_data.tipo)
            )

        for opcion in getattr(p_data, "opciones", []):
            opciones_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "pid": banco_id,
                    "texto": opcion.texto,
                    "es_correcta": opcion.es_correcta,
                    "orden": opcion.orden,
                }
            )

        for blank in getattr(p_data, "blanks", []):
            blank_id = str(uuid.uuid4())
            blanks_rows.append(
                {
                    "id": blank_id,
                    "pid": banco_id,
                    "orden": blank.orden,
                    "tipo": blank.tipo,
                    "texto_antes": blank.texto_antes or None,
                    "texto_despues": blank.texto_despues or None,
                }
            )
            for opcion in blank.opciones:
                blank_opciones_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "bid": blank_id,
                        "texto": opcion.texto,
                        "es_correcta": opcion.es_correcta,
                        "peso": opcion.peso,
                    }
                )

    # 3. Escrituras en lotes — cada bloque es UNA sola sentencia (executemany
    #    vía lista de dicts), no una sentencia por fila.
    if actualizadas_rows:
        await session.execute(
            sa.text(
                "UPDATE pregunta_banco SET enunciado = :enunciado, "
                "moodle_question_id = COALESCE(:qid, moodle_question_id), "
                "nombre_moodle = COALESCE(:nombre, nombre_moodle), "
                "categoria_id = :cat_id WHERE id = :id"
            ),
            actualizadas_rows,
        )
        # Opciones/blanks se reemplazan enteros (si cambió cuál es la correcta,
        # quedarnos con la vieja calificaría mal en silencio). IN expanding en
        # vez de ANY(:ids): forma estándar y portable de SQLAlchemy para listas.
        ids_stmt = sa.text(
            "DELETE FROM opcion_banco WHERE pregunta_banco_id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True))
        await session.execute(ids_stmt, {"ids": banco_ids_actualizadas})
        ids_stmt = sa.text(
            "DELETE FROM blank_banco WHERE pregunta_banco_id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True))
        await session.execute(ids_stmt, {"ids": banco_ids_actualizadas})

    if nuevas_rows:
        await session.execute(
            sa.text(
                "INSERT INTO pregunta_banco "
                "(id, materia_id, enunciado, tipo, categoria_id, moodle_question_id, "
                "nombre_moodle) "
                "VALUES (:id, :materia_id, :enunciado, :tipo, :categoria_id, "
                ":moodle_question_id, :nombre_moodle)"
            ),
            nuevas_rows,
        )

    if opciones_rows:
        await session.execute(
            sa.text(
                "INSERT INTO opcion_banco (id, pregunta_banco_id, texto, es_correcta, orden) "
                "VALUES (:id, :pid, :texto, :es_correcta, :orden)"
            ),
            opciones_rows,
        )

    if blanks_rows:
        await session.execute(
            sa.text(
                "INSERT INTO blank_banco (id, pregunta_banco_id, orden, tipo, texto_antes, texto_despues) "
                "VALUES (:id, :pid, :orden, :tipo, :texto_antes, :texto_despues)"
            ),
            blanks_rows,
        )

    if blank_opciones_rows:
        await session.execute(
            sa.text(
                "INSERT INTO opcion_blank_banco (id, blank_banco_id, texto, es_correcta, peso) "
                "VALUES (:id, :bid, :texto, :es_correcta, :peso)"
            ),
            blank_opciones_rows,
        )

    return ImportBancoReport(
        preguntas_nuevas=len(nuevas_rows),
        nuevas=nuevas_items,
        actualizadas=actualizadas_items,
        preguntas_actualizadas=len(actualizadas_rows),
        omitidas=omitidas,
    )


class ImportacionMoodleService:
    """Caso de uso: importar examen desde Moodle XML."""

    def __init__(self, repo: AbstractExamenContenidoRepository) -> None:
        self._repo = repo

    async def importar(
        self,
        xml_bytes: bytes,
        titulo: str | None = None,
        *,
        moodle_courseid: int | None = None,
        moodle_cmid: int | None = None,
        moodle_component: str | None = None,
        limite_preguntas: int | None = None,
        materia_id: str | None = None,
    ) -> ImportReport:
        """Parsea XML, valida preguntas y persiste el examen.

        D12 (parte B): moodle_courseid/moodle_cmid fijan el destino del write-back
        de nota POR EXAMEN. Si quedan en None, el write-back cae al global (compat).

        ``limite_preguntas``: tope de preguntas del examen. None = solo aplica el
        tope duro del sistema. Si el XML trae más preguntas válidas que el tope, la
        importación se RECHAZA entera (no se truncan: ver LimitePreguntasExcedidoError).

        ``materia_id``: si se provee, resuelve/crea la jerarquía de categorías
        (C-74) y asigna `categoria_id` a cada pregunta según su `categoria_ruta`.

        Raises:
            MoodleXmlInvalidoError: si el XML es malformado.
            MoodleXmlVacioError: si no hay preguntas soportadas.
            LimitePreguntasExcedidoError: si las preguntas válidas superan el tope.
        """
        parse_result = parse_moodle_xml(xml_bytes)

        omitidas: list[OmitidaItem] = [
            OmitidaItem(tipo=o.tipo, nombre=o.nombre, motivo="tipo no soportado")
            for o in parse_result.omitidas
        ]

        # C-74 §2.3: resolver jerarquía de categorías si se provee materia_id.
        # Memo: ruta_tuple → categoria_id para evitar round-trips repetidos.
        cat_repo: CategoriaPreguntaSqlRepository | None = None
        ruta_memo: dict[tuple[str, ...], str] = {}
        if materia_id:
            session = getattr(self._repo, "_db", None)
            if session is not None:
                cat_repo = CategoriaPreguntaSqlRepository(session)

        preguntas_validas: list[Pregunta] = []
        blanks_por_pregunta: list[list[BlankData]] = []
        for p_data in parse_result.preguntas:
            try:
                categoria_id: str | None = None
                if cat_repo and materia_id and p_data.categoria_ruta:
                    categoria_id = await _resolver_ruta(
                        cat_repo, materia_id, p_data.categoria_ruta, ruta_memo
                    )
                pregunta = _pregunta_data_to_entity(p_data, categoria_id=categoria_id)
                preguntas_validas.append(pregunta)
                blanks_por_pregunta.append(p_data.blanks)
            except PreguntaInvalidaError as exc:
                omitidas.append(
                    OmitidaItem(
                        tipo=p_data.tipo,
                        nombre=p_data.enunciado[:60],
                        motivo=str(exc),
                    )
                )

        # Tope efectivo: el que pidió el docente, acotado por el tope del sistema.
        # Se evalúa sobre las preguntas VÁLIDAS (las omitidas no forman el examen).
        tope = min(limite_preguntas or LIMITE_PREGUNTAS_SISTEMA, LIMITE_PREGUNTAS_SISTEMA)
        if len(preguntas_validas) > tope:
            raise LimitePreguntasExcedidoError(len(preguntas_validas), tope)

        examen = ExamenContenido(
            titulo=titulo or "Examen importado",
            preguntas=tuple(preguntas_validas),
            limite_preguntas=limite_preguntas,
            comision_id=None,  # D11: se asocia en sección 6
            moodle_courseid=moodle_courseid,  # D12: destino por examen (None = global)
            moodle_cmid=moodle_cmid,
            moodle_component=moodle_component,  # C-73: mod_assign|mod_quiz (None = global)
        )
        guardado = await self._repo.guardar(examen)

        session = getattr(self._repo, "_db", None)
        if session is not None:
            # Persistir blanks cloze en pregunta_examen (instancia exam-específica)
            for pregunta, blanks in zip(guardado.preguntas, blanks_por_pregunta):
                if blanks:
                    await _persistir_blanks_cloze(session, pregunta.id, blanks)

            # 0057: popular pregunta_banco si se provee materia_id.
            # Las preguntas del banco son independientes del examen.
            if materia_id:
                p_data_list = parse_result.preguntas
                for p_data, pregunta_guardada in zip(p_data_list, guardado.preguntas):
                    banco_id, _es_nueva = await _upsert_pregunta_banco(
                        session,
                        materia_id=materia_id,
                        p_data=p_data,
                        categoria_id=pregunta_guardada.categoria_id,
                    )
                    if banco_id:
                        # Vincular instancia de examen con la pregunta del banco
                        await session.execute(
                            sa.text(
                                "UPDATE pregunta_examen SET pregunta_banco_id = :banco_id WHERE id = :pe_id"
                            ),
                            {"banco_id": banco_id, "pe_id": pregunta_guardada.id},
                        )

        return ImportReport(
            examen_id=guardado.id,
            importadas=len(preguntas_validas),
            omitidas=omitidas,
        )


async def _resolver_ruta(
    cat_repo: CategoriaPreguntaSqlRepository,
    materia_id: str,
    ruta: list[str],
    memo: dict[tuple[str, ...], str],
    padre_raiz: str | None = None,
) -> str:
    """Resuelve (o crea) la jerarquía de categorías para una ruta dada.

    Recorre los segmentos de la ruta de izquierda a derecha, creando cada nivel
    si no existe. El memo evita consultas repetidas para la misma sub-ruta.
    Devuelve el id de la categoría hoja.

    ``padre_raiz``: si se provee, todo el árbol de esta ruta cuelga de esa
    categoría existente en vez de crearse a nivel raíz (ver
    ``importar_banco_desde_xml``, param ``categoria_padre_id``).
    """
    padre_id: str | None = padre_raiz
    for i, segmento in enumerate(ruta):
        parcial = tuple(ruta[: i + 1])
        if parcial in memo:
            padre_id = memo[parcial]
        else:
            cat = await cat_repo.resolver_o_crear(materia_id, segmento, padre_id)
            memo[parcial] = cat.id
            padre_id = cat.id
    return padre_id  # type: ignore[return-value]  # ruta no vacía garantizada por el caller


def _pregunta_data_to_entity(p: PreguntaData, *, categoria_id: str | None = None) -> Pregunta:
    opciones = tuple(
        OpcionRespuesta(
            texto=o.texto,
            es_correcta=o.es_correcta,
            orden=o.orden,
        )
        for o in p.opciones
    )
    return Pregunta(
        enunciado=p.enunciado,
        tipo=p.tipo,
        opciones=opciones,
        orden=p.orden,
        categoria_id=categoria_id,
    )


async def _buscar_pregunta_banco(
    session,
    *,
    materia_id: str,
    p_data: "PreguntaData",
    moodle_qid: int | None,
) -> str | None:
    """Busca la pregunta ya existente en el banco. None si es nueva.

    Identidad, en orden:
    1. ``moodle_question_id`` — la identidad fuerte, cuando el XML la trae.
    2. ``(enunciado, tipo)`` — red de seguridad para XML sin id de pregunta.
       Sin esto, cada re-import duplicaba TODA pregunta sin ``moodle_question_id``
       y el sorteo repartía duplicados como si fueran preguntas distintas.
    """
    if moodle_qid:
        row = await session.execute(
            sa.text(
                "SELECT id FROM pregunta_banco "
                "WHERE materia_id = :mid AND moodle_question_id = :qid"
            ),
            {"mid": materia_id, "qid": moodle_qid},
        )
        existing = row.fetchone()
        if existing:
            return str(existing[0])

    row = await session.execute(
        sa.text(
            "SELECT id FROM pregunta_banco "
            "WHERE materia_id = :mid AND enunciado = :enunciado AND tipo = :tipo "
            "ORDER BY creada_en LIMIT 1"
        ),
        {"mid": materia_id, "enunciado": p_data.enunciado, "tipo": p_data.tipo},
    )
    existing = row.fetchone()
    return str(existing[0]) if existing else None


async def _upsert_pregunta_banco(
    session,
    *,
    materia_id: str,
    p_data: "PreguntaData",
    categoria_id: str | None,
) -> tuple[str | None, bool]:
    """Inserta o actualiza la pregunta en pregunta_banco. Idempotente.

    Regla de propiedad (0058): el contenido lo manda Moodle, la organización la
    manda el docente. En una pregunta ya existente se refrescan enunciado,
    opciones y blancos desde el XML, pero ``categoria_id`` se deja intacto si
    ``categoria_manual`` está en true — o sea, si el docente la movió a mano.

    Retorna ``(id del registro en pregunta_banco, es_nueva)``.
    """
    moodle_qid = getattr(p_data, "moodle_question_id", None)
    banco_id = await _buscar_pregunta_banco(
        session, materia_id=materia_id, p_data=p_data, moodle_qid=moodle_qid
    )
    es_nueva = banco_id is None

    if banco_id:
        # Existe: refrescamos contenido, respetamos la organización del docente.
        # El WHERE del CASE es lo que impide que Moodle pise el trabajo manual.
        await session.execute(
            sa.text(
                "UPDATE pregunta_banco SET "
                "  enunciado = :enunciado, "
                "  moodle_question_id = COALESCE(:qid, moodle_question_id), "
                "  categoria_id = CASE WHEN categoria_manual THEN categoria_id "
                "                      ELSE :cat_id END "
                "WHERE id = :id"
            ),
            {
                "enunciado": p_data.enunciado,
                "qid": moodle_qid,
                "cat_id": categoria_id,
                "id": banco_id,
            },
        )
        # Las opciones y blancos se reemplazan enteros: si en Moodle cambió cuál
        # es la correcta, quedarnos con las viejas calificaría mal en silencio.
        # ON DELETE CASCADE limpia opcion_blank_banco al borrar los blank_banco.
        await session.execute(
            sa.text("DELETE FROM opcion_banco WHERE pregunta_banco_id = :id"),
            {"id": banco_id},
        )
        await session.execute(
            sa.text("DELETE FROM blank_banco WHERE pregunta_banco_id = :id"),
            {"id": banco_id},
        )
    else:
        banco_id = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id, moodle_question_id) "
                "VALUES (:id, :materia_id, :enunciado, :tipo, :categoria_id, :moodle_question_id)"
            ),
            {
                "id": banco_id,
                "materia_id": materia_id,
                "enunciado": p_data.enunciado,
                "tipo": p_data.tipo,
                "categoria_id": categoria_id,
                "moodle_question_id": moodle_qid,
            },
        )

    # Opciones (multichoice / truefalse)
    for opcion in getattr(p_data, "opciones", []):
        await session.execute(
            sa.text(
                "INSERT INTO opcion_banco (id, pregunta_banco_id, texto, es_correcta, orden) "
                "VALUES (:id, :pid, :texto, :es_correcta, :orden)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pid": banco_id,
                "texto": opcion.texto,
                "es_correcta": opcion.es_correcta,
                "orden": opcion.orden,
            },
        )

    # Blanks cloze
    for blank in getattr(p_data, "blanks", []):
        blank_banco_id = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO blank_banco (id, pregunta_banco_id, orden, tipo, texto_antes, texto_despues) "
                "VALUES (:id, :pid, :orden, :tipo, :texto_antes, :texto_despues)"
            ),
            {
                "id": blank_banco_id,
                "pid": banco_id,
                "orden": blank.orden,
                "tipo": blank.tipo,
                "texto_antes": blank.texto_antes or None,
                "texto_despues": blank.texto_despues or None,
            },
        )
        for opcion in blank.opciones:
            await session.execute(
                sa.text(
                    "INSERT INTO opcion_blank_banco (id, blank_banco_id, texto, es_correcta, peso) "
                    "VALUES (:id, :bid, :texto, :es_correcta, :peso)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "bid": blank_banco_id,
                    "texto": opcion.texto,
                    "es_correcta": opcion.es_correcta,
                    "peso": opcion.peso,
                },
            )

    return banco_id, es_nueva


async def _persistir_blanks_cloze(session, pregunta_id: str, blanks: list) -> None:
    """Inserta los blanks cloze (y sus opciones) para una pregunta ya guardada."""
    for blank in blanks:
        blank_id = str(uuid.uuid4())
        await session.execute(
            sa.text(
                "INSERT INTO pregunta_cloze_blank (id, pregunta_id, orden, tipo, texto_antes, texto_despues) "
                "VALUES (:id, :pregunta_id, :orden, :tipo, :texto_antes, :texto_despues)"
            ),
            {
                "id": blank_id,
                "pregunta_id": pregunta_id,
                "orden": blank.orden,
                "tipo": blank.tipo,
                "texto_antes": blank.texto_antes or None,
                "texto_despues": blank.texto_despues or None,
            },
        )
        for opcion in blank.opciones:
            await session.execute(
                sa.text(
                    "INSERT INTO opcion_cloze_blank (id, blank_id, texto, es_correcta, peso) "
                    "VALUES (:id, :blank_id, :texto, :es_correcta, :peso)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "blank_id": blank_id,
                    "texto": opcion.texto,
                    "es_correcta": opcion.es_correcta,
                    "peso": opcion.peso,
                },
            )
