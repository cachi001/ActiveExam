"""Servicio de aplicacion slim para chat bidireccional + pausa autorizada (C-15 6.x).

Sin Keycloak/Vault/MinIO. Transporte REST + polling. Toda la persistencia va contra
la DB real (sin mocks, regla dura de codigo).

L2.5 (regla #5 y #6): aprobar/rechazar una pausa NUNCA sanciona ni exime — solo
deja rastro persistente (proctor_actor + timestamps) y, al aprobar, abre la ventana
que el calculo de score usara para CONTEXTUALIZAR (excluir, no borrar) eventos.

AUDIT LOG: en el slim NO hay middleware de audit_log por-request cableado (la tabla
``audit_log`` de migracion 0012 solo la escriben servicios puntuales como review).
Por eso la propia tabla ``pausa_autorizada`` ES el audit trail persistente de la
resolucion: ``proctor_actor`` + ``resuelta_en`` registran quien y cuando. Decision
documentada (ver tasks 6.3.3).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.chat_pausa import (
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


async def _sesion_existe(db: AsyncSession, session_id: str) -> bool:
    result = await db.execute(
        select(ProctoringSessionModel.id).where(
            ProctoringSessionModel.id == session_id
        )
    )
    return result.scalar_one_or_none() is not None


def _ahora() -> datetime:
    return datetime.now(tz=timezone.utc)


# --- Chat ---


async def crear_mensaje(
    db: AsyncSession,
    session_id: str,
    autor: str,
    texto: str,
    actor: str | None = None,
) -> MensajeChatModel | None:
    """Persiste un mensaje de chat. Devuelve None si la sesion no existe."""
    if not await _sesion_existe(db, session_id):
        return None
    mensaje = MensajeChatModel(
        session_id=session_id, autor=autor, texto=texto, actor=actor
    )
    db.add(mensaje)
    await db.commit()
    await db.refresh(mensaje)
    return mensaje


async def listar_mensajes(
    db: AsyncSession, session_id: str, desde: datetime | None = None
) -> list[MensajeChatModel] | None:
    """Lista los mensajes de la sesion (asc por creado_en). None si no existe la sesion.

    Si ``desde`` viene, solo mensajes con ``creado_en > desde`` (polling incremental)."""
    if not await _sesion_existe(db, session_id):
        return None
    stmt = select(MensajeChatModel).where(MensajeChatModel.session_id == session_id)
    if desde is not None:
        stmt = stmt.where(MensajeChatModel.creado_en > desde)
    stmt = stmt.order_by(MensajeChatModel.creado_en.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- Pausa autorizada ---


async def solicitar_pausa(
    db: AsyncSession, session_id: str, motivo: str
) -> PausaAutorizadaModel | None:
    """Crea una pausa en estado 'solicitada'. None si la sesion no existe."""
    if not await _sesion_existe(db, session_id):
        return None
    pausa = PausaAutorizadaModel(
        session_id=session_id, motivo=motivo, estado="solicitada"
    )
    db.add(pausa)
    await db.commit()
    await db.refresh(pausa)
    return pausa


async def listar_pausas_de_sesion(
    db: AsyncSession, session_id: str
) -> list[PausaAutorizadaModel] | None:
    """Lista las pausas de una sesion (desc por solicitada_en). None si no existe."""
    if not await _sesion_existe(db, session_id):
        return None
    stmt = (
        select(PausaAutorizadaModel)
        .where(PausaAutorizadaModel.session_id == session_id)
        .order_by(PausaAutorizadaModel.solicitada_en.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _timeout_pausa_seg() -> int:
    """Timeout (seg) del PEDIDO de pausa sin responder, desde env
    ``PAUSA_REQUEST_TIMEOUT_SEG`` (default 120). Distinto de ``pausa_max_min``, que
    limita la DURACION de una pausa YA aprobada."""
    try:
        return int(os.getenv("PAUSA_REQUEST_TIMEOUT_SEG", "120"))
    except ValueError:
        return 120


async def expirar_solicitudes_vencidas(
    db: AsyncSession, *, ahora: datetime | None = None, timeout_seg: int | None = None
) -> int:
    """Expira las pausas 'solicitada' mas viejas que el timeout -> 'expirada' (C-72
    seccion 12). Devuelve cuantas expiro. Es un acto del SISTEMA: NO aprueba ni
    rechaza (L2.5, regla #5) — solo limpia la cola del proctor. Idempotente."""
    ahora = ahora or _ahora()
    if timeout_seg is None:
        timeout_seg = _timeout_pausa_seg()
    limite = ahora - timedelta(seconds=timeout_seg)
    result = await db.execute(
        update(PausaAutorizadaModel)
        .where(
            PausaAutorizadaModel.estado == "solicitada",
            PausaAutorizadaModel.solicitada_en < limite,
        )
        .values(estado="expirada", resuelta_en=ahora)
    )
    await db.commit()
    return result.rowcount


async def cancelar_solicitudes_de_sesion(db: AsyncSession, session_id: str) -> int:
    """Cancela ('expirada') las pausas 'solicitada' pendientes de una sesion al
    finalizar (manual o auto). Una sesion cerrada no debe dejar pausas colgadas en
    el panel del proctor. Idempotente (solo toca 'solicitada')."""
    result = await db.execute(
        update(PausaAutorizadaModel)
        .where(
            PausaAutorizadaModel.session_id == session_id,
            PausaAutorizadaModel.estado == "solicitada",
        )
        .values(estado="expirada", resuelta_en=_ahora())
    )
    await db.commit()
    return result.rowcount


async def listar_pausas_pendientes(
    db: AsyncSession,
) -> list[tuple[PausaAutorizadaModel, str | None]]:
    """Lista las pausas 'solicitada' de TODAS las sesiones (poll del proctor).

    Antes de listar, EXPIRA las vencidas por timeout (C-72 seccion 12): las que el
    proctor no respondio a tiempo salen de la cola. Devuelve tuplas (pausa,
    etiqueta_de_la_sesion) ordenadas por solicitada_en asc (las mas antiguas
    primero — la cola del proctor las resuelve por antiguedad)."""
    await expirar_solicitudes_vencidas(db)
    stmt = (
        select(PausaAutorizadaModel, ProctoringSessionModel.etiqueta)
        .join(
            ProctoringSessionModel,
            ProctoringSessionModel.id == PausaAutorizadaModel.session_id,
        )
        .where(PausaAutorizadaModel.estado == "solicitada")
        .order_by(PausaAutorizadaModel.solicitada_en.asc())
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


class EstadoInvalido(Exception):
    """La transicion de estado solicitada no es valida (mapea a 409)."""


async def resolver_pausa(
    db: AsyncSession,
    pausa_id: str,
    accion: str,
    proctor_actor: str | None,
    motivo_rechazo: str | None = None,
) -> PausaAutorizadaModel | None:
    """Aprueba o rechaza una pausa 'solicitada'.

    aprobar  → estado='aprobada', resuelta_en=now, inicio_en=now, proctor_actor set,
               motivo_rechazo=None (no aplica al aprobar).
    rechazar → estado='rechazada', resuelta_en=now, proctor_actor set, motivo_rechazo
               persistido (se muestra al alumno). NO abre ventana.

    Devuelve None si la pausa no existe. Lanza EstadoInvalido si estado != 'solicitada'.

    AUDIT (L2.5): la resolucion queda registrada en la propia fila (proctor_actor +
    resuelta_en + motivo_rechazo) — audit trail persistente. La pausa NUNCA sanciona
    ni exime. La obligatoriedad/validez del motivo se valida en el schema (422)."""
    pausa = await db.get(PausaAutorizadaModel, pausa_id)
    if pausa is None:
        return None
    if pausa.estado != "solicitada":
        raise EstadoInvalido(
            f"La pausa {pausa_id!r} esta en estado {pausa.estado!r}, no 'solicitada'."
        )
    ahora = _ahora()
    pausa.resuelta_en = ahora
    pausa.proctor_actor = proctor_actor
    if accion == "aprobar":
        pausa.estado = "aprobada"
        pausa.inicio_en = ahora
        pausa.motivo_rechazo = None
    else:  # rechazar
        pausa.estado = "rechazada"
        pausa.motivo_rechazo = motivo_rechazo
    await db.commit()
    await db.refresh(pausa)
    return pausa


async def finalizar_pausa(
    db: AsyncSession, pausa_id: str
) -> PausaAutorizadaModel | None:
    """Cierra la ventana de una pausa 'aprobada': estado='finalizada', fin_en=now.

    None si no existe. Lanza EstadoInvalido si estado != 'aprobada'."""
    pausa = await db.get(PausaAutorizadaModel, pausa_id)
    if pausa is None:
        return None
    if pausa.estado != "aprobada":
        raise EstadoInvalido(
            f"La pausa {pausa_id!r} esta en estado {pausa.estado!r}, no 'aprobada'."
        )
    pausa.estado = "finalizada"
    pausa.fin_en = _ahora()
    await db.commit()
    await db.refresh(pausa)
    return pausa
