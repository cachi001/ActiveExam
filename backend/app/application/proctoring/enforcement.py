"""Enforcement SERVER-SIDE de ventana e intentos al crear una sesion (C-69).

El frontend ya gatea "Rendir" (ventana de apertura/cierre e intentos permitidos),
pero el cliente es un sensor NO confiable (regla dura de dominio #6). Este modulo
es el BACKSTOP duro: revalida server-side, con la hora del servidor
(``datetime.now(timezone.utc)``), contra la configuracion del examen
(``examen_contenido``).

Solo aplica cuando la sesion se vincula a un ``examen_contenido_id``. Una sesion
sin contenido (modo 'test') NO se gatea.

L2.5 / regla dura #5: esto NO sanciona ni emite veredicto. Solo decide si la
rendicion puede ARRANCAR segun la configuracion academica del examen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exam_content.deadline import deadline_efectivo, vencido
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


class EnforcementError(Exception):
    """Base de los rechazos de enforcement al crear la sesion."""


@dataclass
class FueraDeVentanaError(EnforcementError):
    """La rendicion esta fuera de la ventana [apertura, cierre] del examen."""

    apertura: datetime | None
    cierre: datetime | None
    mensaje: str


@dataclass
class IntentosAgotadosError(EnforcementError):
    """El alumno ya agoto los intentos permitidos para ese examen."""

    intentos_permitidos: int
    rendidos: int
    mensaje: str


@dataclass
class ExamenDadoDeBajaError(EnforcementError):
    """El examen fue dado de baja del catalogo: ya no se puede rendir (c-78).

    Es el BACKSTOP server-side de la baja logica. Sin esto, la baja solo sacaba
    el examen de los LISTADOS: un alumno que ya tuviera la URL (link guardado,
    pestana abierta, historial) podia seguir iniciando la rendicion de un examen
    retirado, y esa sesion despues generaba nota y entraba a la cola de revision.
    """

    examen_contenido_id: str
    mensaje: str


@dataclass
class ExamenEnBorradorError(EnforcementError):
    """El examen todavia no se habilito (c-78 E-07).

    El docente lo esta probando antes de soltarlo. Igual que la baja logica, es el
    BACKSTOP server-side: sacarlo de los listados no alcanza, porque un alumno con
    la URL guardada podria iniciar la rendicion igual.

    NO aplica al staff: el punto del borrador es justamente que el docente pueda
    rendirlo entero para ver que funciona.
    """

    examen_contenido_id: str
    mensaje: str


@dataclass
class NoInscriptoError(EnforcementError):
    """El alumno no esta inscripto en la comision del examen (gate C-71)."""

    examen_contenido_id: str
    mensaje: str


@dataclass
class TiempoAgotadoError(EnforcementError):
    """El plazo de la rendicion vencio (deadline efectivo pasado + gracia, C-72)."""

    deadline: datetime
    mensaje: str


def gracia_seg_default() -> int:
    """Gracia (seg) del deadline, desde el env ``DEADLINE_GRACIA_SEG`` (default 60).

    Mismo contrato que ``SlimSettings.deadline_gracia_seg`` (misma variable de
    entorno), pero resoluble SIN instanciar los Settings completos — el hot path de
    la rendicion no debe depender de toda la config de arranque. Tolerancia a
    latencia, NO tiempo de examen; nunca se lee del cliente (regla dura #6)."""
    try:
        return int(os.getenv("DEADLINE_GRACIA_SEG", "60"))
    except ValueError:
        return 60


async def verificar_plazo(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    creada_en: datetime,
    ahora: datetime,
    gracia_seg: int | None = None,
) -> None:
    """Revalida el PLAZO de una rendicion en curso (C-72 §2, H-1/H-2).

    A diferencia de ``verificar_enforcement`` (que corre al CREAR la sesion), esto
    se llama en cada mutacion de la rendicion (enviar respuestas, finalizar). El
    deadline efectivo = min(cierre, creada_en + tiempo_limite_min); si ``ahora``
    (hora del servidor) paso el deadline mas la gracia -> ``TiempoAgotadoError``.

    Solo aplica cuando el examen tiene ``cierre`` (ventana definida). ``ahora`` y
    ``creada_en`` deben ser timezone-aware en UTC; ``ahora`` NUNCA es la hora del
    cliente (regla dura #6). Si el examen no existe, no aplica plazo.
    """
    config = (
        await db.execute(
            select(
                ExamenContenidoModel.tiempo_limite_min,
                ExamenContenidoModel.cierre,
            ).where(ExamenContenidoModel.id == examen_contenido_id)
        )
    ).one_or_none()
    if config is None:
        return
    tiempo_limite_min, cierre = config
    if cierre is None:
        return
    if gracia_seg is None:
        gracia_seg = gracia_seg_default()
    deadline = deadline_efectivo(
        creada_en=creada_en, tiempo_limite_min=tiempo_limite_min, cierre=cierre
    )
    if vencido(deadline=deadline, ahora=ahora, gracia_seg=gracia_seg):
        raise TiempoAgotadoError(
            deadline=deadline,
            mensaje="Se agoto el tiempo de esta rendicion. Ya no se pueden enviar respuestas.",
        )


async def verificar_inscripcion(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    alumno_idnumber: str,
) -> None:
    """Backstop server-side de inscripcion (C-71): el alumno debe estar inscripto
    en la comision del examen para poder rendirlo.

    Resuelve la comision del ``examen_contenido`` y verifica que exista inscripcion
    para el ``alumno_idnumber`` (username del principal). Si el examen no
    tiene comision (comision_id NULL) NO se exige inscripcion (edge case: examen
    suelto sin comision). ``NoInscriptoError`` -> 403 en el caller. El cliente es
    sensor no confiable: este control es independiente del filtrado del catalogo.
    """
    comision_id = (
        await db.execute(
            select(ExamenContenidoModel.comision_id).where(
                ExamenContenidoModel.id == examen_contenido_id
            )
        )
    ).scalar_one_or_none()
    if comision_id is None:
        return

    from app.infrastructure.persistence.repositories.exam_content import (
        InscripcionSqlRepository,
    )

    inscripto = await InscripcionSqlRepository(db).esta_inscripto_institucional(
        alumno_idnumber, comision_id
    )
    if not inscripto:
        raise NoInscriptoError(
            examen_contenido_id=examen_contenido_id,
            mensaje=(
                "No estas inscripto en la comision de este examen. Matriculate con "
                "el codigo de la comision para poder rendir."
            ),
        )


async def verificar_enforcement(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    alumno_idnumber: str,
    ahora: datetime,
    es_prueba_de_staff: bool = False,
) -> None:
    """Valida ventana e intentos para el alumno contra el examen vinculado.

    Carga la config del examen (apertura/cierre/intentos_permitidos) y:
      - Si el examen esta DADO DE BAJA (``eliminado_en``) -> ExamenDadoDeBajaError
        (c-78: se chequea primero; un examen retirado no se rinde).
      - Si el examen esta EN BORRADOR -> ExamenEnBorradorError (c-78 E-07).
      - Si ``apertura`` esta seteada y ``ahora < apertura`` -> FueraDeVentanaError.
      - Si ``cierre`` esta seteada y ``ahora > cierre``     -> FueraDeVentanaError.
      - Cuenta las sesiones FINALIZADAS del alumno para ese examen; si
        ``count >= intentos_permitidos`` -> IntentosAgotadosError.

    ``es_prueba_de_staff`` (c-78 E-07): el docente probando su propio examen. Saltea
    el borrador Y la ventana — el sentido del borrador es poder rendirlo ANTES de la
    apertura, que es justo cuando la ventana lo bloquearia. NO saltea la baja logica
    (un examen retirado no se rinde ni de prueba) ni el tope de intentos.

    Si el examen no existe (config None) NO aplica enforcement: la FK de la sesion
    resolvera el caso (o quedara sin vinculo). ``ahora`` debe ser timezone-aware en
    UTC (responsabilidad del llamador — nunca la hora del cliente).
    """
    config = (
        await db.execute(
            select(
                ExamenContenidoModel.apertura,
                ExamenContenidoModel.cierre,
                ExamenContenidoModel.intentos_permitidos,
                ExamenContenidoModel.eliminado_en,
                ExamenContenidoModel.borrador,
            ).where(ExamenContenidoModel.id == examen_contenido_id)
        )
    ).one_or_none()
    if config is None:
        return

    apertura, cierre, intentos_permitidos, eliminado_en, borrador = config

    # c-78: PRIMERO que nada. Un examen dado de baja no se rinde, punto — antes
    # que la ventana y antes que los intentos, porque no importa si esta abierto
    # ni cuantos intentos le quedan: ese examen ya no esta en el catalogo.
    if eliminado_en is not None:
        raise ExamenDadoDeBajaError(
            examen_contenido_id=examen_contenido_id,
            mensaje=(
                "Este examen ya no esta disponible. Si creias que tenias que "
                "rendirlo, avisale a tu docente."
            ),
        )

    # c-78 E-07: el examen todavia no se habilito. Backstop server-side, igual que
    # la baja logica: sacarlo de los listados no alcanza contra una URL guardada.
    if borrador and not es_prueba_de_staff:
        raise ExamenEnBorradorError(
            examen_contenido_id=examen_contenido_id,
            mensaje=(
                "Este examen todavia no esta disponible. Si creias que tenias que "
                "rendirlo, avisale a tu docente."
            ),
        )

    # La prueba del staff corre ANTES de la apertura a proposito: es justo cuando
    # tiene sentido probar el examen, y es cuando la ventana lo bloquearia.
    if not es_prueba_de_staff:
        if apertura is not None and ahora < apertura:
            raise FueraDeVentanaError(
                apertura=apertura,
                cierre=cierre,
                mensaje="El examen todavia no abrio. Aun no podes rendir.",
            )
        if cierre is not None and ahora > cierre:
            raise FueraDeVentanaError(
                apertura=apertura,
                cierre=cierre,
                mensaje="El examen ya cerro. La ventana de rendicion termino.",
            )

    if intentos_permitidos is not None:
        rendidos = (
            await db.execute(
                select(func.count())
                .select_from(ProctoringSessionModel)
                .where(
                    ProctoringSessionModel.alumno_idnumber == alumno_idnumber,
                    ProctoringSessionModel.examen_contenido_id == examen_contenido_id,
                    ProctoringSessionModel.finalizada_en.is_not(None),
                )
            )
        ).scalar_one()
        if rendidos >= intentos_permitidos:
            raise IntentosAgotadosError(
                intentos_permitidos=intentos_permitidos,
                rendidos=rendidos,
                mensaje="Agotaste los intentos permitidos para este examen.",
            )
