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

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import AuditEntry
from app.domain.entities.actividad_auditoria import ActividadAuditoria
from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuditFiltros:
    actor: str | None = None
    modulo: str | None = None
    entidad: str | None = None
    tipo_accion: str | None = None
    accion: str | None = None  # búsqueda libre en el campo detalle (dot-notation)
    desde: str | None = None  # ISO 8601 (timestamp >=)
    hasta: str | None = None  # ISO 8601 (timestamp <=)


@dataclass(frozen=True, slots=True)
class AuditPagina:
    items: list[ActividadAuditoria]
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
    modulo: str | None = None,
    entidad: str | None = None,
    entidad_id: str | None = None,
    tipo_accion: str | None = None,
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
            modulo=modulo,
            entidad=entidad,
            entidad_id=entidad_id,
            tipo_accion=tipo_accion,
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
    modulo: str | None = None,
    entidad: str | None = None,
    entidad_id: str | None = None,
    tipo_accion: str | None = None,
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
                modulo=modulo,
                entidad=entidad,
                entidad_id=entidad_id,
                tipo_accion=tipo_accion,
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
    if filtros.modulo:
        conds.append(AuditLogModel.modulo == filtros.modulo)
    if filtros.entidad:
        conds.append(AuditLogModel.entidad == filtros.entidad)
    if filtros.tipo_accion:
        conds.append(AuditLogModel.tipo_accion == filtros.tipo_accion)
    if filtros.accion:
        # Una opción del filtro de la UI puede agrupar varias acciones dot-notation
        # (p. ej. "Crear" en Materias = materia.create + comision.create + …). Se
        # aceptan varios patrones separados por coma y se combinan con OR.
        patrones = [p.strip() for p in filtros.accion.split(",") if p.strip()]
        if patrones:
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
        ActividadAuditoria(
            id=str(r.id),
            actor=r.actor,
            actor_nombre=nombres.get(r.actor),
            timestamp=str(r.timestamp),
            accion=r.accion,
            tipo_accion=r.tipo_accion,
            modulo=r.modulo,
            entidad=r.entidad,
            entidad_id=r.entidad_id,
            ip=str(r.ip) if r.ip is not None else None,
            user_agent=r.user_agent,
            proposito=r.proposito,
        )
        for r in rows
    ]

    cadena_valida = await AuditLogSqlRepository(session).verificar_cadena()

    return AuditPagina(items=items, total=total, cadena_valida=cadena_valida)


async def listar_modulos(session: AsyncSession) -> list[str]:
    """Devuelve los módulos distintos que tienen al menos una entrada en el audit log."""
    result = await session.execute(
        select(distinct(AuditLogModel.modulo))
        .where(AuditLogModel.modulo.isnot(None))
        .order_by(AuditLogModel.modulo)
    )
    return [row for (row,) in result.all()]


async def _resolver_nombres(session: AsyncSession, actores: set[str]) -> dict[str, str]:
    """Mapa actor → 'Nombre Apellido'. El actor puede ser email, id_institucional o UUID;
    se busca por los tres. Usuarios sin nombre (seed/federados) quedan fuera del mapa.

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
                        UsuarioModel.id,
                        UsuarioModel.email,
                        UsuarioModel.id_institucional,
                        UsuarioModel.nombre,
                        UsuarioModel.apellido,
                    ).where(
                        UsuarioModel.email.in_(actores)
                        | UsuarioModel.id_institucional.in_(actores)
                        | UsuarioModel.id.in_(actores)
                    )
                )
            ).all()
    except Exception:
        return {}
    mapa: dict[str, str] = {}
    for uid, email, idinst, nombre, apellido in rows:
        completo = " ".join(p for p in (nombre, apellido) if p).strip()
        if not completo:
            continue
        if email in actores:
            mapa[email] = completo
        if idinst in actores:
            mapa[idinst] = completo
        if uid in actores:
            mapa[uid] = completo
    return mapa
