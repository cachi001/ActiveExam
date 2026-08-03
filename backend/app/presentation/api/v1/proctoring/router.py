"""Router principal del modulo slim de proctoring.

Agrega los 3 sub-routers (sessions, events, biometria) y el endpoint de health.
Se monta en main_slim.py bajo el prefijo /api/v1/proctoring.

La session_factory, el adapter de re-inferencia y el embedding_encryption se
inyectan desde main_slim.py para mantener el modulo slim totalmente desacoplado
de SlimSettings.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.moodle.writeback_service import MoodleWritebackService
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.domain.auth.roles import Rol
from app.infrastructure.crypto.embedding_encryption import EmbeddingEncryptionService
from app.presentation.api.v1.auth.dependencies import (
    get_current_principal,
    require_capability,
    require_roles,
)
from app.presentation.api.v1.proctoring.biometria.router import create_biometria_router
from app.presentation.api.v1.proctoring.chat_pausa.router import create_chat_pausa_router
from app.presentation.api.v1.proctoring.events.router import create_events_router
from app.presentation.api.v1.proctoring.sessions.router import create_sessions_router


def create_proctoring_router(
    session_factory: async_sessionmaker[AsyncSession],
    reinferencia: ReinferenciaPort,
    embedding_encryption: EmbeddingEncryptionService | None = None,
    writeback_svc: MoodleWritebackService | None = None,
    evidence_encryption=None,
) -> APIRouter:
    """Factory del router principal de proctoring.

    Args:
        session_factory: Factory de sesiones async de SQLAlchemy (slim engine).
        reinferencia: Adapter del puerto ReinferenciaPort (MediaPipeReinferencia).
        embedding_encryption: Servicio de cifrado de embeddings (C-59). Si se
            provee, se montan los endpoints stateful de verificacion biometrica
            server-side. Inyectado desde main_slim.py (app.state.embedding_encryption).

    Returns:
        APIRouter con todos los endpoints montados.
    """
    router = APIRouter(tags=["proctoring-slim"])

    # --- Dependencias ---

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def get_reinferencia() -> ReinferenciaPort:
        return reinferencia

    # Dependencia de embedding_encryption para C-59 (inyeccion por closure).
    # Solo se define si el servicio fue provisto (evita 500 en modo sin cripto).
    _get_embedding_encryption = None
    if embedding_encryption is not None:
        _enc = embedding_encryption  # captura para closure

        def _get_embedding_encryption() -> EmbeddingEncryptionService:
            return _enc

    # Guard de rol estudiante para los endpoints C-59 (sin importar SlimSettings).
    _require_estudiante = require_roles(Rol.ESTUDIANTE)

    # --- Guards de auth/RBAC de los endpoints compartidos alumno/proctor ---
    # El slim YA tiene auth JWT (app.state.jwt_validator), por lo que estos guards
    # endurecen por rol los endpoints de proctoring sin tocar el flujo del alumno.
    #
    #  - require_autenticado: cualquier token valido (el alumno opera su sesion:
    #    crear, eventos, chat, pausas, finalizar). 401 si falta/invalido.
    #  - require_proctor_o_admin: vista de supervision (lista/detalle de sesiones,
    #    poll de pausas pendientes, aprobar/rechazar). 403 si es estudiante.
    #  - require_admin: cadena de custodia (DELETE de sesion — JAMAS proctor).
    _require_autenticado = get_current_principal
    # Gate por CAPACIDAD: `supervisar_vivo` incluye al REVISOR, que antes quedaba
    # afuera de la lista de roles. No es un detalle: la Cola de revision se arma
    # con GET /proctoring/sessions, asi que el unico rol autorizado a resolver un
    # caso recibia 403 al pedir la lista de casos que tiene que resolver.
    _require_proctor_o_admin = require_capability("supervisar_vivo")
    _require_admin = require_roles(Rol.ADMIN_SISTEMA)

    # --- Health ---

    @router.get("/health", summary="Healthcheck del modulo slim")
    async def health() -> JSONResponse:
        """Verifica que el modulo slim esta vivo y puede conectarse a la DB."""
        db_status = "error"
        async with session_factory() as session:
            try:
                await session.execute(text("SELECT 1"))
                db_status = "ok"
            except Exception:  # noqa: BLE001
                db_status = "error"

        return JSONResponse({"status": "ok", "db": db_status})

    # --- Sub-routers ---

    sessions_router = create_sessions_router(
        get_db,
        require_autenticado=_require_autenticado,
        require_proctor_o_admin=_require_proctor_o_admin,
        require_admin=_require_admin,
        writeback_svc=writeback_svc,
        cipher=evidence_encryption,
    )
    router.include_router(sessions_router)

    events_router = create_events_router(
        get_db,
        get_reinferencia,
        require_autenticado=_require_autenticado,
        cipher=evidence_encryption,
    )
    router.include_router(events_router)

    biometria_router = create_biometria_router(
        get_db,
        get_embedding_encryption=_get_embedding_encryption,
        require_estudiante=_require_estudiante,
    )
    router.include_router(biometria_router)

    # C-15 (slim, tareas 6.x): chat bidireccional + pausa autorizada (REST + polling).
    chat_pausa_router = create_chat_pausa_router(
        get_db,
        require_autenticado=_require_autenticado,
        require_proctor_o_admin=_require_proctor_o_admin,
    )
    router.include_router(chat_pausa_router)

    return router
