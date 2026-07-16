"""Tests puros de `require_capability` (c-71 slice 2, D8).

Se invoca el guard directamente (sin FastAPI real, igual que el resto del
RBAC contextual de C-06): pasando el ``principal`` explicito se evita el
default `Depends(...)`, quedando testeable como funcion pura + async.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.presentation.api.v1.auth.dependencies import require_capability


def _principal(*roles: Rol) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(id_institucional="u1", email="u1@uni.edu", roles=roles)


@pytest.mark.asyncio
async def test_revisor_pasa_el_guard_de_resolver_caso() -> None:
    guard = require_capability("resolver_caso")
    principal = _principal(Rol.REVISOR)
    result = await guard(principal=principal)
    assert result is principal


@pytest.mark.asyncio
async def test_estudiante_no_pasa_el_guard_de_resolver_caso() -> None:
    guard = require_capability("resolver_caso")
    principal = _principal(Rol.ESTUDIANTE)
    with pytest.raises(HTTPException) as exc:
        await guard(principal=principal)
    assert exc.value.status_code == 403
