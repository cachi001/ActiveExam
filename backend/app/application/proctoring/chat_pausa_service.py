"""Servicio de aplicacion activeexam para chat bidireccional + pausa autorizada (C-15 6.x).

Sin Keycloak/Vault/MinIO. Transporte REST + polling. Toda la persistencia va contra
la DB real (sin mocks, regla dura de codigo).

L2.5 (regla #5 y #6): aprobar/rechazar una pausa NUNCA sanciona ni exime — solo
deja rastro persistente (tutor_actor + timestamps) y, al aprobar, abre la ventana
que el calculo de score usara para CONTEXTUALIZAR (excluir, no borrar) eventos.

AUDIT LOG: en el activeexam NO hay middleware de audit_log por-request cableado (la tabla
``audit_log`` de migracion 0012 solo la escriben servicios puntuales como review).
Por eso la propia tabla ``pausa_autorizada`` ES el audit trail persistente de la
resolucion: ``tutor_actor`` + ``resuelta_en`` registran quien y cuando. Decision
documentada (ver tasks 6.3.3).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events.schema import Severidad, TipoEvento
from app.infrastructure.persistence.models.chat_pausa import (
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)


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


class AlumnoNoPuedeIniciarError(Exception):
    """El alumno intento enviar el PRIMER mensaje del hilo (mapea a 403).

    C-76 bloque 6 (D4): el alumno no puede crear el hilo de chat — solo puede
    responder si ya existe al menos un mensaje del tutor en esa sesion. Regla
    server-side (regla dura #6: no se confia en que el cliente oculte el boton)."""


async def _tutor_ya_escribio(db: AsyncSession, session_id: str) -> bool:
    result = await db.execute(
        select(MensajeChatModel.id)
        .where(
            MensajeChatModel.session_id == session_id,
            MensajeChatModel.autor == "tutor",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def crear_mensaje(
    db: AsyncSession,
    session_id: str,
    autor: str,
    texto: str,
    actor: str | None = None,
) -> MensajeChatModel | None:
    """Persiste un mensaje de chat. Devuelve None si la sesion no existe.

    Lanza ``AlumnoNoPuedeIniciarError`` si ``autor='alumno'`` y todavia no hay
    ningun mensaje de 'tutor' en la sesion (D4: el alumno no inicia el hilo)."""
    if not await _sesion_existe(db, session_id):
        return None
    if autor == "alumno" and not await _tutor_ya_escribio(db, session_id):
        raise AlumnoNoPuedeIniciarError(
            f"La sesion {session_id!r} todavia no tiene mensajes del tutor; "
            "el alumno no puede iniciar el chat."
        )
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


async def obtener_pausa(db: AsyncSession, pausa_id: str) -> PausaAutorizadaModel | None:
    """Lee una pausa por id (sin mutar). Usada para resolver scoping ANTES de
    autorizar la resolucion (C-76 bloque 6.3/8: acotar por comision del tutor)."""
    return await db.get(PausaAutorizadaModel, pausa_id)


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


class LimitePausasExcedido(Exception):
    """La sesion ya alcanzo el limite de pausas aprobada+finalizada (mapea a 409).

    C-76 bloque 4 (D5 design): el limite se consume al APROBAR, no al solicitar —
    el alumno siempre puede pedir; el rechazo por limite queda como rastro."""


# Estados que cuentan contra el limite de pausas por sesion (D5 / Open Question Q2
# del design c-76): solo las que efectivamente ocurrieron (se aprobaron), esten en
# curso ('aprobada') o ya cerradas ('finalizada'). 'rechazada'/'expirada' NO cuentan.
_ESTADOS_QUE_CUENTAN_PARA_LIMITE = ("aprobada", "finalizada")


async def _contar_pausas_consumidas(db: AsyncSession, session_id: str) -> int:
    """Cuenta las pausas 'aprobada'/'finalizada' de una sesion (para el limite)."""
    result = await db.execute(
        select(func.count())
        .select_from(PausaAutorizadaModel)
        .where(
            PausaAutorizadaModel.session_id == session_id,
            PausaAutorizadaModel.estado.in_(_ESTADOS_QUE_CUENTAN_PARA_LIMITE),
        )
    )
    return int(result.scalar_one())


async def resolver_pausa(
    db: AsyncSession,
    pausa_id: str,
    accion: str,
    tutor_actor: str | None,
    motivo_rechazo: str | None = None,
    limite_pausas: int | None = None,
) -> PausaAutorizadaModel | None:
    """Aprueba o rechaza una pausa 'solicitada'.

    aprobar  → estado='aprobada', resuelta_en=now, inicio_en=now, tutor_actor set,
               motivo_rechazo=None (no aplica al aprobar).
    rechazar → estado='rechazada', resuelta_en=now, tutor_actor set, motivo_rechazo
               persistido (se muestra al alumno). NO abre ventana.

    ``limite_pausas`` (C-76 bloque 4): si viene y ``accion='aprobar'``, cuenta las
    pausas 'aprobada'/'finalizada' YA existentes de la sesion; si el conteo ya
    alcanzo el limite, lanza ``LimitePausasExcedido`` SIN aprobar (la pausa queda
    'solicitada', el proctor/tutor debe rechazarla explicitamente). El alumno
    SIEMPRE puede solicitar — el limite se aplica solo al aprobar (D5).

    Devuelve None si la pausa no existe. Lanza EstadoInvalido si estado != 'solicitada'.

    AUDIT (L2.5): la resolucion queda registrada en la propia fila (tutor_actor +
    resuelta_en + motivo_rechazo) — audit trail persistente. La pausa NUNCA sanciona
    ni exime. La obligatoriedad/validez del motivo se valida en el schema (422)."""
    pausa = await db.get(PausaAutorizadaModel, pausa_id)
    if pausa is None:
        return None
    if pausa.estado != "solicitada":
        raise EstadoInvalido(
            f"La pausa {pausa_id!r} esta en estado {pausa.estado!r}, no 'solicitada'."
        )
    if accion == "aprobar" and limite_pausas is not None:
        consumidas = await _contar_pausas_consumidas(db, pausa.session_id)
        if consumidas >= limite_pausas:
            raise LimitePausasExcedido(
                f"La sesion {pausa.session_id!r} ya alcanzo el limite de "
                f"{limite_pausas} pausas aprobadas."
            )
    ahora = _ahora()
    pausa.resuelta_en = ahora
    pausa.tutor_actor = tutor_actor
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


async def _hubo_captura_en_ventana(
    db: AsyncSession, session_id: str, inicio_en, fin_en
) -> bool:
    """True si existe al menos un evento 'captura_pausa' con ts_backend dentro de
    [inicio_en, fin_en] (C-76 bloque 5: screenshots subidos durante la pausa)."""
    result = await db.execute(
        select(ProctoringEventModel.id)
        .where(
            ProctoringEventModel.session_id == session_id,
            ProctoringEventModel.tipo == TipoEvento.CAPTURA_PAUSA.value,
            ProctoringEventModel.ts_backend >= inicio_en,
            ProctoringEventModel.ts_backend <= fin_en,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def finalizar_pausa(
    db: AsyncSession, pausa_id: str
) -> PausaAutorizadaModel | None:
    """Cierra la ventana de una pausa 'aprobada': estado='finalizada', fin_en=now.

    None si no existe. Lanza EstadoInvalido si estado != 'aprobada'.

    C-76 bloque 5 (D6): al cerrar la ventana, si NO hubo ninguna captura de
    'captura_pausa' durante [inicio_en, fin_en], se emite SERVER-SIDE un evento
    'pausa_sin_captura' (BASELINE, no suma sola al score — L2.5). Es una SEÑAL
    para el revisor humano, no un veredicto ni una sanción; el cliente no puede
    suprimirla (regla dura #6, el sistema mismo la genera al cerrar la ventana)."""
    pausa = await db.get(PausaAutorizadaModel, pausa_id)
    if pausa is None:
        return None
    if pausa.estado != "aprobada":
        raise EstadoInvalido(
            f"La pausa {pausa_id!r} esta en estado {pausa.estado!r}, no 'aprobada'."
        )
    pausa.estado = "finalizada"
    ahora = _ahora()
    pausa.fin_en = ahora
    await db.commit()
    await db.refresh(pausa)

    if pausa.inicio_en is not None and not await _hubo_captura_en_ventana(
        db, pausa.session_id, pausa.inicio_en, pausa.fin_en
    ):
        evento = ProctoringEventModel(
            session_id=pausa.session_id,
            tipo=TipoEvento.PAUSA_SIN_CAPTURA.value,
            severidad=Severidad.BASELINE.value,
            ts_cliente=ahora,  # server-side: no hay reporte del cliente
            payload={"pausa_id": pausa.id, "origen": "server"},
        )
        db.add(evento)
        await db.commit()

    return pausa
