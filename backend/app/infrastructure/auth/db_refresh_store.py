"""Implementacion persistente de RefreshTokenStore sobre Postgres (C-55, D4).

``DbRefreshTokenStore`` es la implementacion de produccion para el provider JWT
propio. Persiste los refresh tokens en la tabla ``refresh_tokens`` (migracion 0006)
usando SQLAlchemy async.

Semantica de rotacion (igual que ``InMemoryRefreshTokenStore``):
- ``issue(usuario_id)``: emite un nuevo token, registra en DB.
- ``is_valid(jti)``: comprueba que el jti exista, no este rotado y no haya expirado.
- ``rotate(old_jti, usuario_id)``: marca ``rotado_en = now()`` en el viejo, emite
  uno nuevo. Si ``old_jti`` ya estaba rotado o expirado -> ``RefreshTokenError``.

``InMemoryRefreshTokenStore`` se conserva para tests unitarios (sin DB).

NOTA: la interfaz base ``RefreshTokenStore`` define ``issue() -> str`` (sin usuario_id).
Para el provider propio necesitamos asociar el token a un usuario; por eso este
store extiende la interfaz con una sobrecarga ``issue_for_usuario``. El contrato
del puerto (issue/is_valid/rotate) se respeta para compatibilidad.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.refresh_store import RefreshTokenError, RefreshTokenStore
from app.infrastructure.persistence.models.transactional import RefreshTokenModel


class DbRefreshTokenStore(RefreshTokenStore):
    """Refresh token store persistente en Postgres (C-55).

    Recibe una ``AsyncSession`` por llamada (sin estado propio de sesion) para
    ser compatible con el patron de session-per-request de FastAPI.
    """

    def __init__(self, session: AsyncSession, ttl_seconds: int = 604800) -> None:
        self._session = session
        self._ttl = timedelta(seconds=ttl_seconds)

    # -------------------------------------------------------------------------
    # Interfaz base RefreshTokenStore (compatibilidad de puerto)
    # -------------------------------------------------------------------------

    def issue(self) -> str:
        """Solo para compatibilidad de puerto. En produccion usar ``issue_para_usuario``."""
        raise NotImplementedError(
            "DbRefreshTokenStore requiere usuario_id. Usar issue_para_usuario()."
        )

    def is_valid(self, token: str) -> bool:
        """Sincrono — no soportado en implementacion async. Usar is_valid_async()."""
        raise NotImplementedError(
            "DbRefreshTokenStore es async. Usar is_valid_async()."
        )

    def rotate(self, old: str) -> str:
        """Sincrono — no soportado. Usar rotate_async()."""
        raise NotImplementedError(
            "DbRefreshTokenStore es async. Usar rotate_async()."
        )

    # -------------------------------------------------------------------------
    # API async (para uso desde endpoints FastAPI async)
    # -------------------------------------------------------------------------

    async def issue_para_usuario(self, usuario_id: str) -> str:
        """Emite un nuevo refresh token y lo persiste en DB.

        Retorna el jti opaco (secrets.token_urlsafe(32)).
        """
        jti = secrets.token_urlsafe(32)
        ahora = datetime.now(UTC)
        registro = RefreshTokenModel(
            jti=jti,
            usuario_id=usuario_id,
            expires_at=ahora + self._ttl,
            rotado_en=None,
        )
        self._session.add(registro)
        await self._session.flush()
        return jti

    async def is_valid_async(self, jti: str) -> bool:
        """True si el jti existe, no esta rotado y no ha expirado."""
        ahora = datetime.now(UTC)
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.jti == jti,
                RefreshTokenModel.rotado_en.is_(None),
                RefreshTokenModel.expires_at > ahora,
            )
        )
        return result.scalar_one_or_none() is not None

    async def rotate_async(self, old_jti: str, nuevo_usuario_id: str) -> str:
        """Invalida old_jti y emite uno nuevo.

        Levanta ``RefreshTokenError`` si old_jti no esta vigente (reuso detectado,
        expirado, o no existe).
        """
        ahora = datetime.now(UTC)
        # Verificar que el token viejo sea valido antes de rotar.
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.jti == old_jti,
                RefreshTokenModel.rotado_en.is_(None),
                RefreshTokenModel.expires_at > ahora,
            )
        )
        registro_viejo = result.scalar_one_or_none()
        if registro_viejo is None:
            raise RefreshTokenError("Refresh token invalido, expirado o ya rotado.")

        # Marcar el viejo como rotado (rotado_en != NULL = ya fue usado).
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.jti == old_jti)
            .values(rotado_en=ahora)
        )

        # Emitir nuevo token.
        return await self.issue_para_usuario(nuevo_usuario_id)
