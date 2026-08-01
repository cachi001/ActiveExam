"""Entidad de dominio ActividadAuditoria (PURA).

Registro de actividad auditada del sistema. Append-only con cadena de custodia
criptográfica (hash encadenado via trigger DB). Sin SQLAlchemy (dominio puro / D1).

modulo / entidad / tipo_accion son strings que en práctica contienen los valores
de ModuloAuditoria / EntidadAuditoria / TipoAccionAuditoria. El dominio usa strings
puros para no depender de la capa de aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActividadAuditoria:
    """Actividad registrada en el audit log (`04` Audit log)."""

    id: str
    actor: str                  # email o id_institucional del actor
    actor_nombre: str | None    # "Nombre Apellido" resuelto (best-effort)
    actor_email: str | None     # email resuelto (best-effort) — el legajo solo no alcanza para dar seguimiento
    timestamp: str              # ISO 8601
    accion: str                 # detalle dot-notation (user.create, materia.delete…)
    tipo_accion: str | None     # CREAR / EDITAR / ELIMINAR / CAMBIO_ESTADO
    modulo: str | None          # USUARIOS / MATERIAS / EXAMENES / …
    entidad: str | None         # USUARIO / EXAMEN / SESION / …
    entidad_id: str | None      # UUID de la entidad afectada (para navegación al detalle)
    ip: str | None = None
    user_agent: str | None = None
    proposito: str | None = None
