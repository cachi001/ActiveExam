"""Router del consentimiento de PERFIL persistido server-side (Ley 25.326, GAP #2).

Endpoints (estudiante autenticado):
- ``POST /``       : otorgar (accion afirmativa explicita SIN default; 422 si falta).
- ``GET  /``       : estado vigente del usuario (otorgado/revocado/via_alternativa/inexistente).
- ``POST /revoke`` : revocar (inserta estado revocado, preserva el historico append-only).

Reglas duras:
- Persistido en BACKEND (fuente de verdad); NUNCA localStorage (cliente = sensor no confiable).
- Append-only + hash de texto + hash de registro (demostrabilidad/integridad).
- ``extra='forbid'`` en los schemas; accion afirmativa sin default True (RN-CO-02).

El consentimiento se ata al ``usuario.id`` resuelto desde ``username`` del
principal (no se confia en un user_id del body).
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit.acciones import EntidadAuditoria, ModuloAuditoria
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.infrastructure.persistence.repositories.consent_perfil import (
    ConsentimientoPerfilSqlRepository,
)
from app.presentation.api.v1.auth.dependencies import get_current_principal

router = APIRouter()

ESTADO_OTORGADO = "otorgado"
ESTADO_REVOCADO = "revocado"
ESTADO_INEXISTENTE = "inexistente"


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OtorgarPerfilRequest(_Strict):
    """Otorgamiento del consentimiento de perfil.

    ``affirmative_action`` SIN default True: la accion afirmativa debe enviarse
    explicita (sin premarcado server-side). El backend la valida (RN-CO-02)."""

    version_texto: str
    affirmative_action: bool = False


class ConsentPerfilResponse(_Strict):
    estado: str
    version_texto: str | None = None
    hash_texto: str | None = None
    timestamp: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _hash_texto(version_texto: str) -> str:
    """Hash del texto consentido. En ola 1 el texto canonico vive en el frontend; se
    sella la version para demostrar QUE version se consintio (ola 2 puede pasar el
    cuerpo completo y recomputar)."""
    return hashlib.sha256(f"consent-perfil:{version_texto}".encode("utf-8")).hexdigest()


async def _resolver_usuario_id(session: AsyncSession, username: str) -> str:
    """Resuelve usuario.id (FK) desde el username del principal. 404 si no existe."""
    result = await session.execute(
        select(UsuarioModel.id).where(
            UsuarioModel.username == username
        )
    )
    uid = result.scalar_one_or_none()
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado para el principal autenticado.",
        )
    return uid


# ---------------------------------------------------------------------------
# POST / — otorgar
# ---------------------------------------------------------------------------


@router.post("", response_model=ConsentPerfilResponse, status_code=status.HTTP_201_CREATED)
async def otorgar(
    body: OtorgarPerfilRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentPerfilResponse:
    """Otorga el consentimiento de perfil; 422 si falta la accion afirmativa."""
    if body.affirmative_action is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El consentimiento requiere una accion afirmativa explicita (RN-CO-02).",
        )
    factory = _get_session_factory(request)
    async with factory() as session:
        uid = await _resolver_usuario_id(session, principal.username)
        fila = await ConsentimientoPerfilSqlRepository(session).registrar(
            usuario_id=uid,
            version_texto=body.version_texto,
            hash_texto=_hash_texto(body.version_texto),
            estado=ESTADO_OTORGADO,
        )
        await session.commit()

    from app.application.audit.service import registrar_seguro

    await registrar_seguro(
        factory,
        actor=principal.username or principal.email,
        accion="consent.otorgado",
        modulo=ModuloAuditoria.CONSENTIMIENTO,
        entidad=EntidadAuditoria.USUARIO,
        entidad_id=str(uid),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        proposito=f"Aceptó el consentimiento (versión {body.version_texto})",
    )

    return ConsentPerfilResponse(
        estado=fila.estado,
        version_texto=fila.version_texto,
        hash_texto=fila.hash_texto,
        timestamp=str(fila.timestamp),
    )


# ---------------------------------------------------------------------------
# GET / — estado vigente
# ---------------------------------------------------------------------------


@router.get("", response_model=ConsentPerfilResponse)
async def estado_vigente(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentPerfilResponse:
    """Estado vigente del consentimiento de perfil del usuario autenticado."""
    factory = _get_session_factory(request)
    async with factory() as session:
        uid = await _resolver_usuario_id(session, principal.username)
        vigente = await ConsentimientoPerfilSqlRepository(session).vigente(uid)
    if vigente is None:
        return ConsentPerfilResponse(estado=ESTADO_INEXISTENTE)
    return ConsentPerfilResponse(
        estado=vigente.estado,
        version_texto=vigente.version_texto,
        hash_texto=vigente.hash_texto,
        timestamp=str(vigente.timestamp),
    )


# ---------------------------------------------------------------------------
# POST /revoke — revocar (append-only)
# ---------------------------------------------------------------------------


@router.post("/revoke", response_model=ConsentPerfilResponse)
async def revocar(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentPerfilResponse:
    """Revoca el consentimiento de perfil insertando una fila ``revocado``.

    Append-only: NO borra el historico (demostrabilidad, Ley 25.326). Reusa la
    ultima ``version_texto`` consentida si existe; si no, la version vigente del
    sistema (``v1`` por defecto)."""
    factory = _get_session_factory(request)
    async with factory() as session:
        uid = await _resolver_usuario_id(session, principal.username)
        repo = ConsentimientoPerfilSqlRepository(session)
        prev = await repo.vigente(uid)
        version = prev.version_texto if prev is not None else "v1"
        fila = await repo.registrar(
            usuario_id=uid,
            version_texto=version,
            hash_texto=_hash_texto(version),
            estado=ESTADO_REVOCADO,
        )
        await session.commit()
        return ConsentPerfilResponse(
            estado=fila.estado,
            version_texto=fila.version_texto,
            hash_texto=fila.hash_texto,
            timestamp=str(fila.timestamp),
        )
