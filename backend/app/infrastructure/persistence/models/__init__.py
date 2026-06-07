"""Modelos ORM de persistencia (SQLAlchemy) del modelo de datos de dominio (`04`).

Aqui VIVE la dependencia de SQLAlchemy (la infraestructura puede acoplarse al ORM;
el dominio NO, regla dura D1/D6). Estos modelos mapean las entidades transaccionales
y el audit log. El Evento (hypertable TimescaleDB) se mapea aparte en ``event.py``
porque su DDL especial (hypertable, compresion, agregados) la materializa la
migracion 002 a mano, no la metadata declarativa.
"""

from app.infrastructure.persistence.models.audit_log import AuditLogModel
from app.infrastructure.persistence.models.event import EventModel
from app.infrastructure.persistence.models.transactional import (
    AsignacionModel,
    CasoDisciplinarioModel,
    ConsentimientoModel,
    EmbeddingModel,
    EmbeddingReferenciaModel,
    EstadoSesionDB,
    EvidenciaModel,
    ExamenModel,
    FotoReferenciaModel,
    SesionModel,
    UsuarioModel,
)

__all__ = [
    "AsignacionModel",
    "AuditLogModel",
    "CasoDisciplinarioModel",
    "ConsentimientoModel",
    "EmbeddingModel",
    "EmbeddingReferenciaModel",
    "EstadoSesionDB",
    "EventModel",
    "EvidenciaModel",
    "ExamenModel",
    "FotoReferenciaModel",
    "SesionModel",
    "UsuarioModel",
]
