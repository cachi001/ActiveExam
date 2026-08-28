"""Qué preguntas del banco se lleva un examen, y cómo se copian.

Estaba escrito adentro del endpoint de creación. Al aparecer la EDICIÓN del
sorteo (cambiar cuántas preguntas, sacar una categoría, sumar otra) hacía falta
lo mismo en un segundo lugar, y una segunda copia de esta regla significa que
crear y editar el mismo examen pueden dar resultados distintos.

Dos responsabilidades y nada más:

- `resolver_pool`: valida la lista de preguntas elegidas a mano contra la materia.
- `seleccionar_del_banco`: qué preguntas califican para cada tramo.
- `copiar_al_examen`: las copia con sus opciones y sus blanks.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models.exam_content import (
    BlankBancoModel,
    CategoriaPreguntaModel,
    PreguntaBancoModel,
)


class PoolInvalidoError(Exception):
    """Se mandaron ids de preguntas que no son del banco de esta materia."""

    def __init__(self, ajenas: list[str], vacio: bool = False) -> None:
        self.ajenas = ajenas
        self.vacio = vacio
        super().__init__("El pool elegido no es válido.")


@dataclass
class TramoInsuficienteError(Exception):
    """Un tramo pide más preguntas de las que hay disponibles."""

    categoria_id: str | None
    disponibles: int
    pedidas: int

    def __str__(self) -> str:  # pragma: no cover - mensaje del router
        return (
            f"Categoría '{self.categoria_id or 'sin clasificar'}': se pidieron "
            f"{self.pedidas} preguntas pero solo hay {self.disponibles} disponibles."
        )


async def arbol_de_categorias(db: AsyncSession, materia_id: str) -> dict:
    """Mapa padre -> hijos de la materia, en UNA consulta.

    El árbol es chico (decenas de filas) y así se evita una consulta recursiva
    por tramo.
    """
    hijos: dict[str | None, list[str]] = {}
    filas = await db.execute(
        select(
            CategoriaPreguntaModel.id,
            CategoriaPreguntaModel.categoria_padre_id,
        ).where(CategoriaPreguntaModel.materia_id == materia_id)
    )
    for cat_id, padre_id in filas.all():
        hijos.setdefault(padre_id, []).append(cat_id)
    return hijos


def con_descendencia(raiz: str, hijos: dict) -> list[str]:
    """La categoría más todas sus subcategorías, a cualquier profundidad."""
    acumulado: list[str] = []
    pendientes = [raiz]
    vistos: set[str] = set()
    while pendientes:
        actual = pendientes.pop()
        if actual in vistos:
            continue
        vistos.add(actual)
        acumulado.append(actual)
        pendientes.extend(hijos.get(actual, []))
    return acumulado


async def resolver_pool(
    db: AsyncSession, *, materia_id: str, pool_preguntas: list[str] | None
) -> set[str] | None:
    """Los ids del pool elegido a mano, validados. ``None`` = sin restricción.

    Los ids llegan del cliente: sin esta validación, mandar el id de una
    pregunta de otra materia la copiaría a este examen.
    """
    if pool_preguntas is None:
        return None

    pedidos = {str(p) for p in pool_preguntas}
    if not pedidos:
        raise PoolInvalidoError(ajenas=[], vacio=True)

    validas = await db.execute(
        select(PreguntaBancoModel.id).where(
            PreguntaBancoModel.id.in_(pedidos),
            PreguntaBancoModel.materia_id == materia_id,
            PreguntaBancoModel.eliminada_en.is_(None),
        )
    )
    del_banco = {str(r[0]) for r in validas.all()}
    ajenas = sorted(pedidos - del_banco)
    if ajenas:
        raise PoolInvalidoError(ajenas=ajenas)
    return del_banco


async def seleccionar_del_banco(
    db: AsyncSession,
    *,
    materia_id: str,
    tramos,
    pool_elegido: set[str] | None,
    hijos: dict,
    todo_el_pool: bool,
) -> list[PreguntaBancoModel]:
    """Las preguntas que se copian al examen, recorriendo los tramos.

    ``todo_el_pool`` (sorteo por intento): el examen se lleva el POOL ENTERO de
    cada tramo y no las ``cantidad`` sorteadas — el sorteo lo hace después cada
    intento, contra esta copia. En False se sortea acá una sola vez.

    Una pregunta no puede caer dos veces en el mismo examen: con tramos anidados
    ("Unidad 1" y además "Unidad 1 / Tema A") el mismo registro entra en los dos
    conjuntos.
    """
    import random

    elegidas: list[PreguntaBancoModel] = []
    ya_usadas: set[str] = set()

    for tramo in tramos:
        # Opciones y blanks viajan con la pregunta (se copian al examen), así que
        # se cargan acá de una: sin esto es un N+1 por pregunta.
        stmt = (
            select(PreguntaBancoModel)
            .where(
                PreguntaBancoModel.materia_id == materia_id,
                # Las dadas de baja quedan fuera: sacarlas del banco tiene que
                # sacarlas también de los exámenes que se armen a partir de ahora.
                PreguntaBancoModel.eliminada_en.is_(None),
            )
            .options(
                selectinload(PreguntaBancoModel.opciones_banco),
                selectinload(PreguntaBancoModel.blanks_banco).selectinload(
                    BlankBancoModel.opciones_blank_banco
                ),
            )
        )
        if pool_elegido is not None:
            stmt = stmt.where(PreguntaBancoModel.id.in_(pool_elegido))

        if tramo.categoria_id is None and not tramo.incluir_subcategorias:
            stmt = stmt.where(PreguntaBancoModel.categoria_id.is_(None))
        elif tramo.categoria_id is None:
            # Todo el banco de la materia: sin filtro de categoría.
            pass
        elif tramo.incluir_subcategorias:
            stmt = stmt.where(
                PreguntaBancoModel.categoria_id.in_(
                    con_descendencia(tramo.categoria_id, hijos)
                )
            )
        else:
            stmt = stmt.where(PreguntaBancoModel.categoria_id == tramo.categoria_id)

        if tramo.tipos:
            stmt = stmt.where(PreguntaBancoModel.tipo.in_(tramo.tipos))

        result = await db.execute(stmt)
        disponibles = [p for p in result.scalars().all() if p.id not in ya_usadas]

        if len(disponibles) < tramo.cantidad:
            raise TramoInsuficienteError(
                categoria_id=tramo.categoria_id,
                disponibles=len(disponibles),
                pedidas=tramo.cantidad,
            )

        del_tramo = (
            disponibles if todo_el_pool else random.sample(disponibles, tramo.cantidad)
        )
        elegidas.extend(del_tramo)
        ya_usadas.update(p.id for p in del_tramo)

    return elegidas


def copiar_al_examen(
    db: AsyncSession,
    *,
    examen_id: str,
    preguntas: list[PreguntaBancoModel],
    seleccionada: bool,
) -> None:
    """Copia las preguntas del banco al examen, con sus opciones y sus blanks.

    La pregunta se COPIA, no se referencia: el examen queda congelado aunque
    después se edite el banco. Y hay que copiar TAMBIÉN opciones y blanks — sin
    ellos la pregunta le llega al alumno sin nada que responder y sin nada con
    qué calificarla.

    ``seleccionada=False`` es el caso del sorteo por intento: quién entra al
    examen lo decide el sorteo de cada intento, no una marca del examen.

    No hace commit: la transacción la maneja el llamador.
    """
    import uuid as _uuid

    from app.infrastructure.persistence.models.exam_content import (
        OpcionClozeBlancoModel,
        OpcionRespuestaModel,
        PreguntaClozeBlankModel,
        PreguntaExamenModel,
    )

    for orden, pb in enumerate(preguntas):
        pregunta_id = str(_uuid.uuid4())
        db.add(
            PreguntaExamenModel(
                id=pregunta_id,
                examen_id=examen_id,
                enunciado=pb.enunciado,
                tipo=pb.tipo,
                orden=orden,
                seleccionada=seleccionada,
                categoria_id=pb.categoria_id,
                moodle_question_id=pb.moodle_question_id,
                pregunta_banco_id=pb.id,
            )
        )

        for opcion in pb.opciones_banco:
            db.add(
                OpcionRespuestaModel(
                    id=str(_uuid.uuid4()),
                    pregunta_id=pregunta_id,
                    texto=opcion.texto,
                    es_correcta=opcion.es_correcta,
                    orden=opcion.orden,
                )
            )

        for blank in pb.blanks_banco:
            blank_id = str(_uuid.uuid4())
            db.add(
                PreguntaClozeBlankModel(
                    id=blank_id,
                    pregunta_id=pregunta_id,
                    orden=blank.orden,
                    tipo=blank.tipo,
                    texto_antes=blank.texto_antes,
                    texto_despues=blank.texto_despues,
                )
            )
            for opcion_blank in blank.opciones_blank_banco:
                db.add(
                    OpcionClozeBlancoModel(
                        id=str(_uuid.uuid4()),
                        blank_id=blank_id,
                        texto=opcion_blank.texto,
                        es_correcta=opcion_blank.es_correcta,
                        peso=opcion_blank.peso,
                    )
                )
