"""Repositorio de audit log NO-OPERATIVO para el modulo slim (C-63).

En el modulo slim (Railway) la tabla ``audit_log`` no existe — el schema slim
no incluye las tablas del schema full (proctoring enterprise con TimescaleDB +
tablas transaccionales principales).

Este adaptador provee una implementacion en memoria para que el ``ConsentService``
pueda correr en slim sin necesitar la tabla ``audit_log``. Las entradas se guardan
en memoria (sin persistencia) — no hay cadena de custodia en slim.

NOTA: esto es apropiado para el modulo slim de Railway que es demo/PoC.
En produccion full, el audit log real (con trigger de encadenamiento) aplica.
"""

from __future__ import annotations

from app.domain.audit_chain import AuditEntry, construir_cadena, verificar_cadena
from app.domain.repositories.ports import AuditLogRepository


class InMemoryAuditLogRepository(AuditLogRepository):
    """Audit log en memoria para el modulo slim.

    Implementa el contrato append-only sin persistencia. Util para entornos
    sin la tabla ``audit_log`` (slim / tests unitarios).
    """

    def __init__(self) -> None:
        self._items: list[AuditEntry] = []

    async def append(self, entity: AuditEntry) -> AuditEntry:
        encadenada = construir_cadena(self._items + [entity])[-1]
        self._items.append(encadenada)
        return encadenada

    async def get(self, entity_id: str) -> AuditEntry | None:
        return None

    async def list(self) -> list[AuditEntry]:
        return list(self._items)

    async def verificar_cadena(self) -> bool:
        return verificar_cadena(self._items)
