"""Tests puros de `require_capability` (c-71 slice 2, D8; modelo de un solo
paso — el guard de revision cubre TODO el acto, no hay guard separado para
anular).

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
    return AuthenticatedPrincipal(username="u1", email="u1@uni.edu", roles=roles)


@pytest.mark.asyncio
async def test_coordinador_pasa_el_guard_de_revisar_sesion() -> None:
    # c-76: el rol REVISOR fue eliminado; el COORDINADOR absorbe el veredicto.
    guard = require_capability("revisar_sesion")
    principal = _principal(Rol.COORDINADOR)
    result = await guard(principal=principal)
    assert result is principal


@pytest.mark.asyncio
async def test_estudiante_no_pasa_el_guard_de_revisar_sesion() -> None:
    guard = require_capability("revisar_sesion")
    principal = _principal(Rol.ESTUDIANTE)
    with pytest.raises(HTTPException) as exc:
        await guard(principal=principal)
    assert exc.value.status_code == 403
