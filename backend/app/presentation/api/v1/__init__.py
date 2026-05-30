"""Router base de la API v1 (``/api/v1``).

Agrega los sub-routers de la version 1. En C-04 solo registra el router de
healthchecks; los routers de dominio se suman en C-05+.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.auth.router import router as auth_router
from app.presentation.api.v1.biometrics.router import router as biometrics_router
from app.presentation.api.v1.consent.router import router as consent_router
from app.presentation.api.v1.events.router import router as events_router
from app.presentation.api.v1.evidence.router import router as evidence_router
from app.presentation.api.v1.exams.router import router as exams_router
from app.presentation.api.v1.health import router as health_router
from app.presentation.api.v1.sessions.router import router as sessions_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(exams_router, prefix="/exams", tags=["exams"])
api_v1_router.include_router(consent_router, prefix="/consent", tags=["consent"])
api_v1_router.include_router(biometrics_router, prefix="/identity", tags=["identity"])
api_v1_router.include_router(events_router, prefix="/events", tags=["events"])
api_v1_router.include_router(evidence_router, prefix="/evidence", tags=["evidence"])
api_v1_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
