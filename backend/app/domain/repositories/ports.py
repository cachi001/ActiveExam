"""Puertos de repositorio POR DOMINIO (PUROS).

Una interfaz por entidad del modelo (`04`), codificando las invariantes:
- ``AuditLogRepository`` es SOLO-APPEND (sin update/delete) -> trigger de motor.
- ``ConsentRepository`` NO expone update -> inmutabilidad del consentimiento.
- el resto admite update (``MutableRepository``).

El dominio depende de ESTOS puertos; los adaptadores SQLAlchemy viven en
``app.infrastructure.persistence.repositories`` (Hexagonal, D6).
"""

from __future__ import annotations

from abc import abstractmethod

from app.domain.audit_chain import AuditEntry
from app.domain.entities.assignment import Asignacion
from app.domain.entities.consent import Consentimiento
from app.domain.entities.disciplinary_case import CasoDisciplinario
from app.domain.entities.embedding import Embedding
from app.domain.entities.event import Evento
from app.domain.entities.evidence import Evidencia
from app.domain.entities.exam import Examen
from app.domain.entities.session import Sesion
from app.domain.entities.user import Usuario
from app.domain.repositories.base import (
    AppendOnlyRepository,
    MutableRepository,
    Repository,
)


class UserRepository(MutableRepository[Usuario]):
    """Puerto del repositorio de Usuario (JIT desde IdP)."""

    @abstractmethod
    async def get_by_id_institucional(self, id_institucional: str) -> Usuario | None:
        """Busca por identificador institucional (clave del JIT provisioning)."""


class ExamRepository(MutableRepository[Examen]):
    """Puerto del repositorio de Examen."""


class SessionRepository(MutableRepository[Sesion]):
    """Puerto del repositorio de Sesion (entidad central)."""


class AssignmentRepository(MutableRepository[Asignacion]):
    """Puerto del repositorio de Asignacion proctor↔examen."""


class ConsentRepository(Repository[Consentimiento]):
    """Puerto del repositorio de Consentimiento.

    INMUTABLE: hereda solo ``add``/``get``/``list`` de ``Repository`` y NO expone
    ``update`` (no extiende ``MutableRepository``), coherente con D5.
    """


class EmbeddingRepository(MutableRepository[Embedding]):
    """Puerto del repositorio de Embedding (cifrado at-rest, borrable al egreso).

    Admite ``delete`` por la eliminacion al egreso del estudiante (DD-13)."""

    @abstractmethod
    async def delete(self, entity_id: str) -> None:
        """Elimina el embedding (egreso del estudiante / DSR, DD-13)."""


class EvidenceRepository(MutableRepository[Evidencia]):
    """Puerto del repositorio de Evidencia (cadena de custodia)."""


class DisciplinaryCaseRepository(MutableRepository[CasoDisciplinario]):
    """Puerto del repositorio de Caso disciplinario (hold de retencion)."""


class EventRepository(AppendOnlyRepository[Evento]):
    """Puerto del repositorio de Evento (telemetria).

    SOLO-APPEND: los eventos son inmutables una vez ingeridos; la limpieza la hace
    la politica de retencion/compresion de la hypertable, no un update de fila."""


class AuditLogRepository(AppendOnlyRepository[AuditEntry]):
    """Puerto del repositorio del Audit log.

    SOLO-APPEND (sin update/delete): coherente con el trigger de la base que
    rechaza UPDATE/DELETE (DD-07). Ademas expone la verificacion de la cadena."""

    @abstractmethod
    async def verificar_cadena(self) -> bool:
        """Verifica el encadenamiento de hash extremo a extremo (validacion diaria)."""
