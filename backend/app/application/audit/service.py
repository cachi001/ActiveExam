"""Servicio de auditoría (registro de actividad, `04` Audit log).

Dos responsabilidades:
- ``registrar``: appendea una acción al ``audit_log`` (cadena de hash append-only;
  el motor encadena el hash vía trigger — este servicio NO toca la inmutabilidad).
- ``listar_auditoria``: lee el registro con filtros + paginación y reporta si la
  cadena de custodia sigue íntegra (verificación extremo a extremo).

L2.5 / DD-07: el audit log es tamper-evident; acá solo se AGREGA y se LEE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import AuditEntry
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuditFiltros:
    actor: str | None = None
    accion: str | None = None
    desde: str | None = None  # ISO 8601 (timestamp >=)
    hasta: str | None = None  # ISO 8601 (timestamp <=)


@dataclass(frozen=True, slots=True)
class AuditEvento:
    id: str
    actor: str
    accion: str
    timestamp: str
    ip: str | None
    user_agent: str | None
    proposito: str | None
    actor_nombre: str | None = None  # "Nombre Apellido" resuelto del usuario (si existe)


@dataclass(frozen=True, slots=True)
class AuditPagina:
    items: list[AuditEvento]
    total: int
    cadena_valida: bool


def _parse_dt(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


async def registrar(
    session: AsyncSession,
    *,
    actor: str,
    accion: str,
    ip: str | None = None,
    user_agent: str | None = None,
    proposito: str | None = None,
    evidencia_id: str | None = None,
) -> None:
    """Registra una acción en el audit log (append-only, el motor encadena el hash).

    Best-effort para el caller: no debería tumbar la operación auditada. El repo
    ya normaliza la IP; acá dejamos que el trigger complete la cadena.
    """
    await AuditLogSqlRepository(session).append(
        AuditEntry(
            actor=actor,
            timestamp="",  # lo pone el server_default (now()); el trigger encadena
            ip=ip or "",
            user_agent=user_agent or "",
            accion=accion,
            evidencia_id=evidencia_id,
            proposito=proposito or "",
        )
    )


async def registrar_seguro(
    session_factory,
    *,
    actor: str,
    accion: str,
    ip: str | None = None,
    user_agent: str | None = None,
    proposito: str | None = None,
) -> bool:
    """Registra una acción en una sesión PROPIA, best-effort.

    Desacoplado de la transacción de la acción auditada: si el registro falla
    (tabla ausente en un entorno, error transitorio…) NUNCA rompe la operación
    del usuario (p. ej. no bloquea un login por un problema del audit log).
    Devuelve True si registró, False si no. La acción auditada ya se commiteó
    aparte, así que perder una entrada acá no deja el sistema inconsistente.
    """
    try:
        async with session_factory() as session:
            await registrar(
                session,
                actor=actor,
                accion=accion,
                ip=ip,
                user_agent=user_agent,
                proposito=proposito,
            )
            await session.commit()
        return True
    except Exception:
        # Best-effort para el caller, PERO no silencioso: un fallo de auditoría es
        # un evento serio (se pierde una entrada de la cadena de custodia). Se loguea
        # a ERROR con la acción/actor para que sea observable (nunca se propaga).
        logger.exception(
            "Fallo al registrar auditoría (accion=%s, actor=%s) — la operación no se bloquea",
            accion,
            actor,
        )
        return False


def _conditions(filtros: AuditFiltros) -> list:
    conds: list = []
    if filtros.actor:
        conds.append(AuditLogModel.actor.ilike(f"%{filtros.actor}%"))
    if filtros.accion:
        # Una "entidad" del filtro puede agrupar varios tipos de acción: se pasan
        # separados por coma y se combinan con OR (los códigos nunca llevan coma).
        patrones = [p.strip() for p in filtros.accion.split(",") if p.strip()]
        if len(patrones) == 1:
            conds.append(AuditLogModel.accion.ilike(f"%{patrones[0]}%"))
        elif patrones:
            conds.append(or_(*(AuditLogModel.accion.ilike(f"%{p}%") for p in patrones)))
    desde = _parse_dt(filtros.desde)
    hasta = _parse_dt(filtros.hasta)
    if desde is not None:
        conds.append(AuditLogModel.timestamp >= desde)
    if hasta is not None:
        conds.append(AuditLogModel.timestamp <= hasta)
    return conds


async def listar_auditoria(
    session: AsyncSession,
    filtros: AuditFiltros | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditPagina:
    """Lista el audit log (más reciente primero) con filtros + paginación, y
    reporta si la cadena de custodia sigue íntegra."""
    filtros = filtros or AuditFiltros()
    conds = _conditions(filtros)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    total = int(
        (
            await session.execute(
                select(func.count()).select_from(AuditLogModel).where(*conds)
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            select(AuditLogModel)
            .where(*conds)
            .order_by(AuditLogModel.timestamp.desc(), AuditLogModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    # Resolver actor → "Nombre Apellido" (el actor es email o id_institucional).
    nombres = await _resolver_nombres(session, {r.actor for r in rows})

    items = [
        AuditEvento(
            id=str(r.id),
            actor=r.actor,
            accion=r.accion,
            timestamp=str(r.timestamp),
            ip=str(r.ip) if r.ip is not None else None,
            user_agent=r.user_agent,
            proposito=r.proposito,
            actor_nombre=nombres.get(r.actor),
        )
        for r in rows
    ]

    cadena_valida = await AuditLogSqlRepository(session).verificar_cadena()

    return AuditPagina(items=items, total=total, cadena_valida=cadena_valida)


async def _resolver_nombres(session: AsyncSession, actores: set[str]) -> dict[str, str]:
    """Mapa actor → 'Nombre Apellido'. El actor puede ser email o id_institucional;
    se busca por ambos. Usuarios sin nombre (seed/federados) quedan fuera del mapa.

    Best-effort dentro de un SAVEPOINT: si la tabla `usuario` no está disponible
    (entorno acotado / test aislado), degrada a mapa vacío sin romper la lectura
    del audit log ni la sesión."""
    if not actores:
        return {}
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    try:
        async with session.begin_nested():
            rows = (
                await session.execute(
                    select(
                        UsuarioModel.email,
                        UsuarioModel.id_institucional,
                        UsuarioModel.nombre,
                        UsuarioModel.apellido,
                    ).where(
                        UsuarioModel.email.in_(actores)
                        | UsuarioModel.id_institucional.in_(actores)
                    )
                )
            ).all()
    except Exception:
        return {}
    mapa: dict[str, str] = {}
    for email, idinst, nombre, apellido in rows:
        completo = " ".join(p for p in (nombre, apellido) if p).strip()
        if not completo:
            continue
        if email in actores:
            mapa[email] = completo
        if idinst in actores:
            mapa[idinst] = completo
    return mapa
