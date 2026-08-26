"""Resolución del set de preguntas de un intento (c-78 E-07, tasks 15.1/15.2).

Hasta acá el sorteo de preguntas era de ARMADO: `crear-desde-banco` elegía N
preguntas una sola vez y todos los alumnos rendían esas mismas. Este módulo
implementa el otro modelo, el de Moodle: el examen guarda la CONDICIÓN del sorteo
(`tramo_sorteo_examen`) y el set concreto se resuelve al arrancar CADA intento.

## La diferencia deliberada con Moodle

Moodle sortea contra el banco de preguntas vivo. Por eso necesitó construir
versionado de preguntas (4.0+), para que editar una pregunta no le cambie el
examen a quien está rindiendo, más el bloqueo de borrado de categorías en uso. Aun
así le queda un agujero que su propia documentación reconoce: si la categoría se
queda sin suficientes preguntas al momento del sorteo, el ALUMNO ve un error.

Acá el sorteo corre contra el POOL YA COPIADO dentro del examen
(`pregunta_examen`), que ActiveExam viene manteniendo desde la migración 0031.
Eso da la misma protección sin versionar nada, y mueve el "no alcanzan las
preguntas" al momento de ARMAR el examen, cuando todavía hay alguien mirando que
lo puede corregir. `PoolInsuficienteError` es la red de seguridad, no el camino
esperado.

## Compatibilidad

Un examen en modo 'fijo' (todo lo que ya existía, y todo lo importado de XML) se
resuelve por `pregunta_examen.seleccionada`, igual que siempre, y NO escribe en
`pregunta_sesion`. Los lectores que todavía miran `seleccionada` siguen andando.
"""

from __future__ import annotations

import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.exam_content import (
    ExamenContenidoModel,
    PreguntaExamenModel,
    PreguntaSesionModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

MODO_FIJO = "fijo"
MODO_SORTEO_POR_INTENTO = "sorteo_por_intento"


class PoolInsuficienteError(Exception):
    """Un tramo pide más preguntas de las que hay en el pool del examen.

    No debería ocurrir: el tamaño del pool se valida al armar el examen. Si llega
    acá, es preferible romper a servir un examen incompleto y calificarlo como si
    estuviera entero.
    """

    def __init__(self, *, disponibles: int, pedidas: int, categoria_id: str | None):
        self.disponibles = disponibles
        self.pedidas = pedidas
        self.categoria_id = categoria_id
        super().__init__(
            f"El examen pide {pedidas} pregunta(s) de la categoría "
            f"{categoria_id or 'sin clasificar'} pero su pool tiene {disponibles}."
        )


async def resolver_preguntas_del_intento(
    *,
    db: AsyncSession,
    session_id: str,
    examen_contenido_id: str,
) -> list[str]:
    """Los ``pregunta_examen.id`` que le tocan a este intento, en orden.

    Con modo 'fijo' devuelve las seleccionadas y no persiste nada.

    Con modo 'sorteo_por_intento':
      - si el intento ya tiene su set, lo devuelve tal cual (idempotente: el alumno
        recarga la página y sigue viendo SU examen, y las respuestas que ya cargó
        no quedan huérfanas);
      - si no, sortea contra el pool del examen y lo persiste.

    No hace commit: la transacción la maneja el llamador.
    """
    examen = (
        await db.execute(
            select(
                ExamenContenidoModel.modo_preguntas,
            ).where(ExamenContenidoModel.id == examen_contenido_id)
        )
    ).one_or_none()
    if examen is None:
        return []

    if examen[0] != MODO_SORTEO_POR_INTENTO:
        return await _preguntas_fijas(db, examen_contenido_id)

    ya_resuelto = await _set_del_intento(db, session_id)
    if ya_resuelto:
        return ya_resuelto

    # Candado sobre la sesión: dos pedidos simultáneos (doble click, dos pestañas)
    # sortearían sets distintos y el intento terminaría con el doble de preguntas.
    # El unique de (session_id, pregunta_id) no alcanza, porque dos sorteos
    # disjuntos insertarían sin pisarse.
    await db.execute(
        select(ProctoringSessionModel.id)
        .where(ProctoringSessionModel.id == session_id)
        .with_for_update()
    )

    # Segunda lectura ya con el candado tomado: el que perdió la carrera encuentra
    # acá el set que escribió el otro.
    ya_resuelto = await _set_del_intento(db, session_id)
    if ya_resuelto:
        return ya_resuelto

    elegidas = await _sortear(db, examen_contenido_id)
    for orden, pregunta_id in enumerate(elegidas):
        db.add(
            PreguntaSesionModel(
                id=str(uuid.uuid4()),
                session_id=session_id,
                pregunta_id=pregunta_id,
                orden=orden,
            )
        )
    await db.flush()
    return elegidas


async def _preguntas_fijas(db: AsyncSession, examen_contenido_id: str) -> list[str]:
    """Modo 'fijo': las marcadas por el docente, en su orden de examen."""
    filas = await db.execute(
        select(PreguntaExamenModel.id)
        .where(
            PreguntaExamenModel.examen_id == examen_contenido_id,
            PreguntaExamenModel.seleccionada.is_(True),
        )
        .order_by(PreguntaExamenModel.orden)
    )
    return [str(r[0]) for r in filas.all()]


async def _set_del_intento(db: AsyncSession, session_id: str) -> list[str]:
    filas = await db.execute(
        select(PreguntaSesionModel.pregunta_id)
        .where(PreguntaSesionModel.session_id == session_id)
        .order_by(PreguntaSesionModel.orden)
    )
    return [str(r[0]) for r in filas.all()]


async def _sortear(db: AsyncSession, examen_contenido_id: str) -> list[str]:
    """Sortea un set nuevo recorriendo los tramos, contra el pool del examen.

    Una pregunta no puede caer dos veces en el mismo examen: con tramos anidados
    ("Unidad 1" y además "Unidad 1 / Tema A") el mismo registro entra en los dos
    conjuntos. Mismo criterio que `crear_desde_banco`.
    """
    tramos = (
        (
            await db.execute(
                select(TramoSorteoExamenModel)
                .where(TramoSorteoExamenModel.examen_id == examen_contenido_id)
                .order_by(TramoSorteoExamenModel.orden)
            )
        )
        .scalars()
        .all()
    )

    # El pool entero de una: son decenas de filas y así se evita una consulta por
    # tramo. Las categorías se comparan sobre la copia, no sobre el banco.
    pool = (
        await db.execute(
            select(
                PreguntaExamenModel.id,
                PreguntaExamenModel.categoria_id,
                PreguntaExamenModel.tipo,
            )
            .where(PreguntaExamenModel.examen_id == examen_contenido_id)
            .order_by(PreguntaExamenModel.orden)
        )
    ).all()

    # Descendencia de categorías, resuelta sobre el árbol del banco. Si la categoría
    # ya no existe (la borraron), el tramo cae a comparación directa: las preguntas
    # copiadas conservan su `categoria_id` igual.
    hijos = await _hijos_por_padre(db, [c for _, c, _ in pool if c])

    elegidas: list[str] = []
    ya_usadas: set[str] = set()

    for tramo in tramos:
        if tramo.categoria_id is None:
            admitidas = {None}
        elif tramo.incluir_subcategorias:
            admitidas = _con_descendencia(str(tramo.categoria_id), hijos)
        else:
            admitidas = {str(tramo.categoria_id)}

        tipos = set(tramo.tipos) if tramo.tipos else None
        disponibles = [
            str(pid)
            for pid, cat, tipo in pool
            if str(pid) not in ya_usadas
            and (str(cat) if cat else None) in admitidas
            and (tipos is None or tipo in tipos)
        ]

        if len(disponibles) < tramo.cantidad:
            raise PoolInsuficienteError(
                disponibles=len(disponibles),
                pedidas=tramo.cantidad,
                categoria_id=str(tramo.categoria_id) if tramo.categoria_id else None,
            )

        del_tramo = random.sample(disponibles, tramo.cantidad)
        elegidas.extend(del_tramo)
        ya_usadas.update(del_tramo)

    # Preguntas fijas del examen (15.5): las que el docente marcó explícitamente
    # conviven con los tramos sorteados. Van primero y no participan del sorteo,
    # así "3 fijas + 4 de Unidad 1" es un examen válido.
    ids_fijas = set(await _preguntas_fijas(db, examen_contenido_id))
    fijas = [
        str(pid)
        for pid, _, _ in pool
        if str(pid) in ids_fijas and str(pid) not in ya_usadas
    ]
    return fijas + elegidas


async def _hijos_por_padre(
    db: AsyncSession, categorias: list
) -> dict[str, list[str]]:
    """Mapa padre → hijos del árbol de categorías que toca este examen."""
    from app.infrastructure.persistence.models.exam_content import (
        CategoriaPreguntaModel,
    )

    if not categorias:
        return {}
    materias = await db.execute(
        select(CategoriaPreguntaModel.materia_id)
        .where(CategoriaPreguntaModel.id.in_([str(c) for c in categorias]))
        .distinct()
    )
    ids_materia = [str(r[0]) for r in materias.all()]
    if not ids_materia:
        return {}

    filas = await db.execute(
        select(
            CategoriaPreguntaModel.id, CategoriaPreguntaModel.categoria_padre_id
        ).where(CategoriaPreguntaModel.materia_id.in_(ids_materia))
    )
    hijos: dict[str, list[str]] = {}
    for cat_id, padre_id in filas.all():
        if padre_id:
            hijos.setdefault(str(padre_id), []).append(str(cat_id))
    return hijos


def _con_descendencia(raiz: str, hijos: dict[str, list[str]]) -> set[str]:
    """La categoría más todas sus subcategorías, a cualquier profundidad."""
    acumulado: set[str] = set()
    pendientes = [raiz]
    while pendientes:
        actual = pendientes.pop()
        if actual in acumulado:
            continue
        acumulado.add(actual)
        pendientes.extend(hijos.get(actual, []))
    return acumulado
