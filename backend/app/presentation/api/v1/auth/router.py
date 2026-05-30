"""Router de auth: ``POST /api/v1/auth/refresh`` y ``GET /api/v1/auth/me`` (C-06).

- ``/auth/refresh``: rota el refresh token (D2). Opera CON token (no es
  estrictamente publica, `03` §Rutas publicas): un refresh ya rotado o invalido se
  rechaza con 401, sin emitir tokens nuevos.
- ``/auth/me``: devuelve el principal autenticado (util para el front y para
  verificar el JIT provisioning); exige Bearer valido.

El grant real contra Keycloak (intercambio del refresh por un nuevo access) es
operacion del IdP; aqui se modela la ROTACION local (el contrato que los tests
ejercen sin red). Pydantic con ``extra='forbid'`` (regla dura).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.auth.refresh_store import RefreshTokenError, RefreshTokenStore
from app.presentation.api.v1.auth.dependencies import get_current_principal

router = APIRouter()


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class RefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class PrincipalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_institucional: str
    email: str
    roles: list[str]
    mfa_satisfecho: bool
    jurisdiccion: str | None = None


def _get_refresh_store(request: Request) -> RefreshTokenStore:
    store = getattr(request.app.state, "refresh_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Store de refresh no inicializado.",
        )
    return store


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
) -> RefreshResponse:
    """Rota el refresh token: invalida el usado y emite uno nuevo (D2).

    Un refresh ya rotado o invalido -> 401 (rotacion: no se reusa)."""
    store = _get_refresh_store(request)
    try:
        nuevo_refresh = store.rotate(body.refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    # El access token lo emite Keycloak en produccion; aqui se devuelve el contrato
    # de rotacion (nuevo par). El access concreto se intercambia contra el IdP.
    access = getattr(request.app.state, "issue_access_token", lambda: nuevo_refresh)()
    return RefreshResponse(access_token=access, refresh_token=nuevo_refresh)


@router.get("/me", response_model=PrincipalResponse)
async def me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PrincipalResponse:
    """Devuelve el principal autenticado (Bearer requerido)."""
    return PrincipalResponse(
        id_institucional=principal.id_institucional,
        email=principal.email,
        roles=[r.value for r in principal.roles],
        mfa_satisfecho=principal.mfa_satisfecho,
        jurisdiccion=principal.jurisdiccion,
    )
