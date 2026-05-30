"""Healthchecks: liveness y readiness (DD-10).

- ``/api/v1/health/live``: liveness. Responde OK si el proceso esta vivo.
  Nginx lo usa para sacar instancias caidas del pool.
- ``/api/v1/health/ready``: readiness. Reporta el estado de las dependencias
  (DB, storage, IdP). Devuelve 503 si alguna no esta lista. En C-04 los checks
  concretos son livianos; el cableado real a los pools llega con el dominio.

Pydantic con ``extra='forbid'`` en los modelos de respuesta (regla dura).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class LivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """El proceso esta vivo. No verifica dependencias externas."""
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    """Readiness: estado de dependencias.

    En C-04 no hay pools cableados a DB/storage/IdP (eso es C-05/C-06), por lo
    que los checks reportan ``False`` de forma EXPLICITA (sin fingir salud). El
    endpoint igual responde para que Nginx/orquestador puedan poolear (DD-10).
    """
    checks = {
        "database": False,
        "storage": False,
        "identity_provider": False,
    }
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=checks,
    )
