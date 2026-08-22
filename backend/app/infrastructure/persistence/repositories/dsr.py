"""Adaptadores SQL activeexam para DSR (c-17).

- SqlUserDsrRepository: lee/actualiza/anonimiza usuario, lista sesiones, borra biometria.
- SqlDsrAuditor: escribe al audit_log con triggers de cadena hash.

ActiveExam: la asociacion usuario↔proctoring_session NO existe a nivel de FK en
activeexam (proctoring_session.exam_id es texto libre). Para encontrar sesiones
del usuario en activeexam usamos una heuristica conservadora: por ahora
``list_sessions_for_user`` devuelve [] (no hay forma confiable de
asociarlas). Esto es honesto al estado activeexam — el frontend del proctor sigue
la sesion por su id directamente, no via usuario.

Cuando llegue c-69 con tabla `caso_disciplinario` y FKs reales, el
``SqlUserDsrRepository`` cambia ``list_sessions_for_user`` para devolver
sesiones reales del titular.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.acciones import EntidadAuditoria, ModuloAuditoria
from app.domain.audit_chain import AuditEntry
from app.domain.dsr.ports import DsrAuditor, UserDsrRepository
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.models.transactional import (
    ConsentimientoPerfilModel,
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository


class SqlUserDsrRepository(UserDsrRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user(self, usuario_id: str) -> dict | None:
        result = await self._session.execute(
            select(UsuarioModel).where(UsuarioModel.id == usuario_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "username": row.username,
            "email": row.email,
            "nombre": row.nombre,
            "apellido": row.apellido,
            "roles": list(row.roles or []),
            "eliminado_en": row.eliminado_en,
        }

    async def update_user_fields(
        self,
        usuario_id: str,
        *,
        email: str | None,
        nombre: str | None,
        apellido: str | None,
    ) -> None:
        values = {}
        if email is not None:
            values["email"] = email
        if nombre is not None:
            values["nombre"] = nombre
        if apellido is not None:
            values["apellido"] = apellido
        if not values:
            return
        await self._session.execute(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(**values)
        )

    async def list_sessions_for_user(self, usuario_id: str) -> list[str]:
        """ActiveExam: sin FK usuario↔proctoring_session. Devuelve [].

        c-69 sucesor agrega la asociacion via tabla `asignacion` o columna
        nueva en proctoring_session, y aqui se reemplaza por una query real.
        """
        del usuario_id
        return []

    async def delete_session(self, session_id: str) -> None:
        await self._session.execute(
            delete(ProctoringSessionModel).where(
                ProctoringSessionModel.id == session_id
            )
        )

    async def delete_embeddings(self, usuario_id: str) -> int:
        result = await self._session.execute(
            delete(EmbeddingReferenciaModel).where(
                EmbeddingReferenciaModel.usuario_id == usuario_id
            )
        )
        return int(result.rowcount or 0)

    async def delete_fotos(self, usuario_id: str) -> int:
        result = await self._session.execute(
            delete(FotoReferenciaModel).where(
                FotoReferenciaModel.usuario_id == usuario_id
            )
        )
        return int(result.rowcount or 0)

    async def delete_consent_perfil(self, usuario_id: str) -> int:
        """Purga el consentimiento de perfil (eliminacion al egreso, Ley 25.326)."""
        result = await self._session.execute(
            delete(ConsentimientoPerfilModel).where(
                ConsentimientoPerfilModel.usuario_id == usuario_id
            )
        )
        return int(result.rowcount or 0)

    async def anonymize_user(self, usuario_id: str) -> None:
        """Anonimiza: setea eliminado_en, blanquea PII directa.

        Conserva ``username`` como seudonimo opaco (no es PII directa
        bajo la regla del proyecto — es un identificador interno).
        """
        await self._session.execute(
            update(UsuarioModel)
            .where(UsuarioModel.id == usuario_id)
            .values(
                eliminado_en=datetime.now(timezone.utc),
                email=f"anon-{str(usuario_id)[:8]}@anon.local",
                nombre=None,
                apellido=None,
            )
        )


class SqlDsrAuditor(DsrAuditor):
    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditLogSqlRepository(session)

    async def log_dsr(
        self, usuario_id: str, *, actor: str, tipo: str, proposito: str
    ) -> None:
        await self._audit.append(
            AuditEntry(
                actor=actor,
                timestamp="",
                ip="",
                user_agent="",
                accion=f"dsr.{tipo}",
                evidencia_id=usuario_id,
                proposito=proposito,
                hash_prev="",
                # El titular del DSR es el usuario afectado — con esto, "Ver detalle"
                # en Auditoría lleva a SU perfil en vez de caer al registro genérico
                # de sesiones (donde el DSR no tiene nada que mostrar).
                modulo=ModuloAuditoria.EVIDENCIA,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
            )
        )
