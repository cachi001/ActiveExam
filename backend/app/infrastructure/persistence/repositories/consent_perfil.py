"""Repositorio del consentimiento de perfil — APPEND-ONLY (Ley 25.326).

Cada otorgamiento/revocacion/via-alternativa INSERTA una fila nueva (nunca update):
el historico es demostrable. El estado VIGENTE es la fila mas reciente por
``usuario_id`` (por timestamp; desempate por id).

``hash_registro`` = SHA-256 de ``usuario_id|version_texto|timestamp|estado`` para
integridad del registro (no se puede alterar sin que el hash cambie).

La eliminacion al egreso (``purgar_por_usuario``) borra TODAS las filas del usuario;
la decision de SI purgar (hold/no-hold) la toma el servicio de retencion/DSR.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.transactional import (
    ConsentimientoPerfilModel,
)

# Estados validos del consentimiento de perfil.
ESTADOS_VALIDOS: frozenset[str] = frozenset({"otorgado", "revocado", "via_alternativa"})


def hash_registro(
    *, usuario_id: str, version_texto: str, timestamp: str, estado: str
) -> str:
    """SHA-256 canonico del registro (integridad demostrable, RN-CO-01)."""
    payload = "|".join([usuario_id, version_texto, timestamp, estado])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> datetime:
    """Instante actual con precision de microsegundos.

    Se setea explicito por fila (no via server_default now()) porque ``now()`` es
    constante DENTRO de una transaccion en Postgres: dos inserts en la misma tx
    quedarian con el mismo timestamp y el orden "mas reciente" seria ambiguo. Con
    el reloj de la app cada fila tiene un timestamp monotonico distinto -> el estado
    vigente (la fila mas reciente) es deterministico."""
    return datetime.now(timezone.utc)


class ConsentimientoPerfilSqlRepository:
    """Acceso append-only al consentimiento de perfil."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(
        self,
        *,
        usuario_id: str,
        version_texto: str,
        hash_texto: str,
        estado: str,
        timestamp: datetime | None = None,
    ) -> ConsentimientoPerfilModel:
        """Inserta una fila nueva (append-only). No actualiza ni borra."""
        ts = timestamp or _now()
        fila = ConsentimientoPerfilModel(
            usuario_id=usuario_id,
            version_texto=version_texto,
            hash_texto=hash_texto,
            estado=estado,
            timestamp=ts,
            hash_registro=hash_registro(
                usuario_id=usuario_id,
                version_texto=version_texto,
                timestamp=ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                estado=estado,
            ),
        )
        self._session.add(fila)
        await self._session.flush()
        await self._session.refresh(fila)
        return fila

    async def vigente(self, usuario_id: str) -> ConsentimientoPerfilModel | None:
        """Estado vigente = fila mas reciente por ``usuario_id`` (None si no hay)."""
        result = await self._session.execute(
            select(ConsentimientoPerfilModel)
            .where(ConsentimientoPerfilModel.usuario_id == usuario_id)
            .order_by(
                ConsentimientoPerfilModel.timestamp.desc(),
                ConsentimientoPerfilModel.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def purgar_por_usuario(self, usuario_id: str) -> int:
        """Borra TODAS las filas del usuario (eliminacion al egreso). Devuelve el conteo."""
        result = await self._session.execute(
            delete(ConsentimientoPerfilModel).where(
                ConsentimientoPerfilModel.usuario_id == usuario_id
            )
        )
        return result.rowcount or 0
