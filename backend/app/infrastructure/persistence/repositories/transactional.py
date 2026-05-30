"""Adaptadores SQLAlchemy de los repositorios transaccionales (infraestructura).

Implementan los puertos de ``app.domain.repositories.ports`` mapeando entre las
entidades de dominio puras y los modelos ORM. Todos heredan de un adaptador base
generico que cubre ``add``/``get``/``list``/``update``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.assignment import Asignacion
from app.domain.entities.disciplinary_case import CasoDisciplinario
from app.domain.entities.embedding import Embedding
from app.domain.entities.evidence import Evidencia
from app.domain.entities.exam import Examen
from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.entities.user import Usuario
from app.domain.repositories.ports import (
    AssignmentRepository,
    DisciplinaryCaseRepository,
    EmbeddingRepository,
    EvidenceRepository,
    ExamRepository,
    SessionRepository,
    UserRepository,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import (
    AsignacionModel,
    CasoDisciplinarioModel,
    EmbeddingModel,
    EstadoSesionDB,
    EvidenciaModel,
    ExamenModel,
    SesionModel,
    UsuarioModel,
)

D = TypeVar("D")
M = TypeVar("M", bound=Base)


class _SqlRepository(Generic[D, M]):
    """Adaptador base: CRUD generico con mappers domain<->ORM inyectados."""

    def __init__(
        self,
        session: AsyncSession,
        model: type[M],
        to_domain: Callable[[M], D],
        to_model: Callable[[D], M],
    ) -> None:
        self._session = session
        self._model = model
        self._to_domain = to_domain
        self._to_model = to_model

    async def add(self, entity: D) -> D:
        row = self._to_model(entity)
        self._session.add(row)
        await self._session.flush()
        return self._to_domain(row)

    async def get(self, entity_id: str) -> D | None:
        row = await self._session.get(self._model, entity_id)
        return self._to_domain(row) if row is not None else None

    async def list(self) -> list[D]:
        result = await self._session.execute(select(self._model))
        return [self._to_domain(r) for r in result.scalars().all()]

    async def update(self, entity: D) -> D:
        row = self._to_model(entity)
        merged = await self._session.merge(row)
        await self._session.flush()
        return self._to_domain(merged)


# --- Mappers domain <-> ORM ---------------------------------------------------


def _user_to_domain(m: UsuarioModel) -> Usuario:
    return Usuario(
        id=m.id,
        id_institucional=m.id_institucional,
        email=m.email,
        roles=tuple(m.roles or ()),
        attrs_federados=dict(m.attrs_federados or {}),
    )


def _user_to_model(u: Usuario) -> UsuarioModel:
    kwargs = dict(
        id_institucional=u.id_institucional,
        email=u.email,
        roles=list(u.roles),
        attrs_federados=u.attrs_federados,
    )
    if u.id is not None:
        kwargs["id"] = u.id
    return UsuarioModel(**kwargs)


def _exam_to_domain(m: ExamenModel) -> Examen:
    return Examen(
        id=m.id,
        nombre=m.nombre,
        umbral_score=m.umbral_score,
        parametros=dict(m.parametros or {}),
        detectores=tuple(m.detectores or ()),
        ventana=dict(m.ventana or {}),
        retencion=dict(m.retencion or {}),
    )


def _exam_to_model(e: Examen) -> ExamenModel:
    kwargs = dict(
        nombre=e.nombre,
        umbral_score=e.umbral_score,
        parametros=e.parametros,
        detectores=list(e.detectores),
        ventana=e.ventana,
        retencion=e.retencion,
    )
    if e.id is not None:
        kwargs["id"] = e.id
    return ExamenModel(**kwargs)


def _session_to_domain(m: SesionModel) -> Sesion:
    return Sesion(
        id=m.id,
        user_id=m.user_id,
        exam_id=m.exam_id,
        clave_sesion=m.clave_sesion,
        estado=EstadoSesion(m.estado.value if isinstance(m.estado, EstadoSesionDB) else m.estado),
        score=m.score,
    )


def _session_to_model(s: Sesion) -> SesionModel:
    kwargs = dict(
        user_id=s.user_id,
        exam_id=s.exam_id,
        clave_sesion=s.clave_sesion,
        estado=EstadoSesionDB(s.estado.value),
        score=s.score,
    )
    if s.id is not None:
        kwargs["id"] = s.id
    return SesionModel(**kwargs)


def _assignment_to_domain(m: AsignacionModel) -> Asignacion:
    return Asignacion(id=m.id, proctor_id=m.proctor_id, exam_id=m.exam_id)


def _assignment_to_model(a: Asignacion) -> AsignacionModel:
    kwargs = dict(proctor_id=a.proctor_id, exam_id=a.exam_id)
    if a.id is not None:
        kwargs["id"] = a.id
    return AsignacionModel(**kwargs)


def _embedding_to_domain(m: EmbeddingModel) -> Embedding:
    return Embedding(
        id=m.id,
        user_id=m.user_id,
        vector_cifrado=bytes(m.vector_cifrado),
        version=m.version,
        fecha=str(m.fecha),
    )


def _embedding_to_model(e: Embedding) -> EmbeddingModel:
    kwargs = dict(user_id=e.user_id, vector_cifrado=e.vector_cifrado, version=e.version)
    if e.id is not None:
        kwargs["id"] = e.id
    return EmbeddingModel(**kwargs)


def _evidence_to_domain(m: EvidenciaModel) -> Evidencia:
    return Evidencia(
        id=m.id,
        session_id=m.session_id,
        uri_bucket=m.uri_bucket,
        hash_cliente=m.hash_cliente,
        firma_cliente=m.firma_cliente,
        hash_backend=m.hash_backend,
        firma_maestra=m.firma_maestra,
        output_reinferencia=dict(m.output_reinferencia or {}),
        meta=dict(m.meta or {}),
    )


def _evidence_to_model(e: Evidencia) -> EvidenciaModel:
    kwargs = dict(
        session_id=e.session_id,
        uri_bucket=e.uri_bucket,
        hash_cliente=e.hash_cliente,
        firma_cliente=e.firma_cliente,
        hash_backend=e.hash_backend,
        firma_maestra=e.firma_maestra,
        output_reinferencia=e.output_reinferencia,
        meta=e.meta,
    )
    if e.id is not None:
        kwargs["id"] = e.id
    return EvidenciaModel(**kwargs)


def _case_to_domain(m: CasoDisciplinarioModel) -> CasoDisciplinario:
    return CasoDisciplinario(
        id=m.id,
        session_id=m.session_id,
        estado=m.estado,
        refs_evidencia=tuple(m.refs_evidencia or ()),
        decisiones=tuple(m.decisiones or ()),
        vinculo_externo=m.vinculo_externo,
        hold=bool(m.hold),
    )


def _case_to_model(c: CasoDisciplinario) -> CasoDisciplinarioModel:
    kwargs = dict(
        session_id=c.session_id,
        estado=c.estado,
        refs_evidencia=list(c.refs_evidencia),
        decisiones=list(c.decisiones),
        vinculo_externo=c.vinculo_externo,
        hold=c.hold,
    )
    if c.id is not None:
        kwargs["id"] = c.id
    return CasoDisciplinarioModel(**kwargs)


# --- Adaptadores concretos (implementan los puertos del dominio) --------------


class UserSqlRepository(_SqlRepository[Usuario, UsuarioModel], UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UsuarioModel, _user_to_domain, _user_to_model)

    async def get_by_id_institucional(self, id_institucional: str) -> Usuario | None:
        result = await self._session.execute(
            select(UsuarioModel).where(
                UsuarioModel.id_institucional == id_institucional
            )
        )
        row = result.scalar_one_or_none()
        return _user_to_domain(row) if row is not None else None


class ExamSqlRepository(_SqlRepository[Examen, ExamenModel], ExamRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ExamenModel, _exam_to_domain, _exam_to_model)


class SessionSqlRepository(_SqlRepository[Sesion, SesionModel], SessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SesionModel, _session_to_domain, _session_to_model)


class AssignmentSqlRepository(
    _SqlRepository[Asignacion, AsignacionModel], AssignmentRepository
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session, AsignacionModel, _assignment_to_domain, _assignment_to_model
        )


class EmbeddingSqlRepository(
    _SqlRepository[Embedding, EmbeddingModel], EmbeddingRepository
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session, EmbeddingModel, _embedding_to_domain, _embedding_to_model
        )

    async def delete(self, entity_id: str) -> None:
        row = await self._session.get(EmbeddingModel, entity_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class EvidenceSqlRepository(
    _SqlRepository[Evidencia, EvidenciaModel], EvidenceRepository
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session, EvidenciaModel, _evidence_to_domain, _evidence_to_model
        )


class DisciplinaryCaseSqlRepository(
    _SqlRepository[CasoDisciplinario, CasoDisciplinarioModel],
    DisciplinaryCaseRepository,
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session, CasoDisciplinarioModel, _case_to_domain, _case_to_model
        )
