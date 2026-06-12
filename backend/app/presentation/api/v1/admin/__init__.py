"""Endpoints administrativos del sistema (solo admin_sistema).

Hoy contiene el trigger manual del motor de retencion (c-19). En el futuro
puede albergar otros endpoints de gobernanza (jobs, holds, cleanup, etc.).
"""

from app.presentation.api.v1.admin.retention_router import (
    router as admin_retention_router,
)

__all__ = ["admin_retention_router"]
