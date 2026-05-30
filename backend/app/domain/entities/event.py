"""Entidad de dominio Evento (PURA): telemetria de la sesion.

Esquema de `04` Evento. Se persiste como HYPERTABLE TimescaleDB (migracion 002)
por la escala (SU-06: ~5.000 inserts/s, 4-5M filas por examen). La validacion de
la firma HMAC de produccion y el esquema versionado definitivo son scope de C-10;
aqui se modelan las columnas (``firma`` y ``schema_version`` presentes, sin
validacion de produccion). Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Evento:
    """Evento de telemetria (`04` Evento). Denormaliza ``exam_id`` para indexar
    por examen sin join contra Sesion (panel a escala, CQRS-lite)."""

    session_id: str
    exam_id: str
    tipo: str
    severidad: str
    timestamp_cliente: str
    timestamp_backend: str
    payload: dict[str, object] = field(default_factory=dict)
    firma: str | None = None
    schema_version: int = 1
    id: str | None = None
