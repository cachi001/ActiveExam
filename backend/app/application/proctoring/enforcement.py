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

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def verificar_enforcement(
    db: AsyncSession,
    *,
    examen_contenido_id: str,
    alumno_idnumber: str,
    ahora: datetime,
) -> None:
    """Valida ventana e intentos para el alumno contra el examen vinculado.

    Carga la config del examen (apertura/cierre/intentos_permitidos) y:
      - Si ``apertura`` esta seteada y ``ahora < apertura`` -> FueraDeVentanaError.
      - Si ``cierre`` esta seteada y ``ahora > cierre``     -> FueraDeVentanaError.
      - Cuenta las sesiones FINALIZADAS del alumno para ese examen; si
        ``count >= intentos_permitidos`` -> IntentosAgotadosError.

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
            ).where(ExamenContenidoModel.id == examen_contenido_id)
        )
    ).one_or_none()
    if config is None:
        return

    apertura, cierre, intentos_permitidos = config

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
