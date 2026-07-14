"""Servicio de aplicacion para sesiones de proctoring slim.

Orquesta la creacion, listado y detalle de sesiones. No depende de Keycloak,
Vault ni MinIO. La logica de scoring se delega a scoring.py para evitar
duplicacion con el repositorio.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.scoring import calcular_score
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.proctoring import (
    ProctoringRepository,
    SesionResumenData,
)


async def crear_sesion(
    db: AsyncSession,
    modo: str,
    exam_id: str | None = None,
    etiqueta: str | None = None,
    examen_contenido_id: str | None = None,
    alumno_idnumber: str | None = None,
    alumno_email: str | None = None,
) -> ProctoringSessionModel:
    """Crea una nueva sesion de proctoring slim.

    ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
    importado de Moodle XML (NULLABLE). ``alumno_idnumber``/``alumno_email``
    persisten la identidad del alumno (C-69, enforcement de intentos).
    """
    repo = ProctoringRepository(db)
    return await repo.crear_sesion(
        modo=modo,
        exam_id=exam_id,
        etiqueta=etiqueta,
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
    )


async def crear_o_reanudar_sesion(
    db: AsyncSession,
    modo: str,
    exam_id: str | None = None,
    etiqueta: str | None = None,
    examen_contenido_id: str | None = None,
    alumno_idnumber: str | None = None,
    alumno_email: str | None = None,
) -> ProctoringSessionModel:
    """Crea una sesion, o REANUDA la activa existente (anti-zombie, reload durante examen).

    Solo aplica la busqueda de reanudacion cuando hay ``examen_contenido_id`` Y
    ``alumno_idnumber`` (la sesion 'test' sin vinculo no tiene forma de identificar
    "la misma rendicion" — cada POST crea una fila nueva, como antes).

    Si el alumno ya tiene una sesion ACTIVA (``finalizada_en IS NULL``) para ese
    examen, se devuelve ESA MISMA fila (misma id, misma creada_en) en vez de crear
    una nueva. Esto es lo que rompe el ciclo "F5 -> sesion zombie": recargar la
    pagina vuelve a pasar por acá y encuentra la sesion ya abierta, así que el
    timer (creada_en) y las respuestas ya guardadas (via GET .../respuestas) se
    pueden restaurar en el cliente en vez de perderse.
    """
    repo = ProctoringRepository(db)
    if examen_contenido_id is not None and alumno_idnumber:
        activa = await repo.obtener_sesion_activa(alumno_idnumber, examen_contenido_id)
        if activa is not None:
            return activa
    return await repo.crear_sesion(
        modo=modo,
        exam_id=exam_id,
        etiqueta=etiqueta,
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
    )


async def listar_sesiones(db: AsyncSession) -> list[SesionResumenData]:
    """Lista todas las sesiones con total_eventos, total_discrepancias y score."""
    repo = ProctoringRepository(db)
    return await repo.listar_sesiones()


async def detalle_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Obtiene el detalle completo de una sesion (con eventos y biometria)."""
    repo = ProctoringRepository(db)
    return await repo.obtener_sesion(session_id)


async def finalizar_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Setea finalizada_en = now() si es NULL (idempotente). None si no existe."""
    repo = ProctoringRepository(db)
    return await repo.finalizar_sesion(session_id)


async def cerrar_forzado(
    db: AsyncSession,
    session_id: str,
    motivo: str,
    proctor_actor: str | None = None,
) -> ProctoringSessionModel | None:
    """Cierre forzado de la sesion por el proctor (operativo, NO disciplinario).

    Idempotente: si ya estaba cerrada de forma forzada, no muta el audit. None si
    la sesion no existe. Ver ProctoringRepository.cerrar_forzado."""
    repo = ProctoringRepository(db)
    return await repo.cerrar_forzado(session_id, motivo=motivo, proctor_actor=proctor_actor)


async def eliminar_sesion(db: AsyncSession, session_id: str) -> bool:
    """Elimina una sesion por ID. Devuelve True si existia, False si no."""
    repo = ProctoringRepository(db)
    return await repo.eliminar_sesion(session_id)
