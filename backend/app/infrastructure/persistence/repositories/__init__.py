"""Adaptadores SQLAlchemy de los puertos de repositorio (infraestructura).

Cada adaptador implementa un puerto de ``app.domain.repositories.ports`` traduciendo
entre las entidades de dominio (puras) y los modelos ORM. La aplicacion inyecta
estos adaptadores; el dominio depende solo del puerto (Hexagonal, D6).

Invariantes (D1/D5):
- ``AuditLogSqlRepository`` solo expone ``append``/``get``/``list``/``verificar_cadena``
  (sin update/delete) -> coherente con el trigger de la base.
- ``ConsentSqlRepository`` no expone ``update`` -> coherente con la inmutabilidad.
"""

from app.infrastructure.persistence.repositories.audit_log import (
    AuditLogSqlRepository,
)
from app.infrastructure.persistence.repositories.consent import (
    ConsentSqlRepository,
)
from app.infrastructure.persistence.repositories.event import EventSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    AssignmentSqlRepository,
    DisciplinaryCaseSqlRepository,
    EmbeddingSqlRepository,
    EvidenceSqlRepository,
    ExamSqlRepository,
    SessionSqlRepository,
    UserSqlRepository,
)

__all__ = [
    "AssignmentSqlRepository",
    "AuditLogSqlRepository",
    "ConsentSqlRepository",
    "DisciplinaryCaseSqlRepository",
    "EmbeddingSqlRepository",
    "EventSqlRepository",
    "EvidenceSqlRepository",
    "ExamSqlRepository",
    "SessionSqlRepository",
    "UserSqlRepository",
]
