"""Servicio de versiones del texto de consentimiento (C-08 ext, Ley 25.326).

Gestiona la tabla ``consent_texto_version``:
- ``get_version(version)`` — devuelve una version especifica o levanta 404.
- ``get_vigente(consent_version_vigente)`` — devuelve la version vigente segun config;
  si no existe en la tabla, hace fallback a v1 desde text_catalog (nunca rompe el flujo).
- ``list_versions()`` — lista todas las versiones (para panel de admin).
- ``create_version(version, bloques)`` — crea nueva version; 409 si ya existe.

El hash se computa deterministicamente: SHA-256 de JSON canonico (sorted keys,
sin whitespace, ensure_ascii=False) del objeto {version, bloques: [{titulo, cuerpo}]}.
Misma version + mismos bloques => mismo hash. Texto nuevo => nueva version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.transactional import ConsentTextoVersionModel


# ---------------------------------------------------------------------------
# Vistas (DTOs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BloqueConsentimiento:
    titulo: str
    cuerpo: str


@dataclass(frozen=True, slots=True)
class ConsentTextoVersionView:
    """Vista completa de una version del texto (para respuesta HTTP)."""
    version: str
    bloques: list[BloqueConsentimiento]
    hash_texto: str


@dataclass(frozen=True, slots=True)
class ConsentVersionListItem:
    """Item para el listado de versiones disponibles (admin)."""
    version: str
    hash_texto: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Hash canonico
# ---------------------------------------------------------------------------


def compute_hash(version: str, bloques: list[dict]) -> str:
    """SHA-256 deterministico de version+bloques.

    El canonical JSON usa sorted_keys=True y separators=(',', ':') para
    garantizar el mismo resultado independientemente del orden de claves."""
    canonical = json.dumps(
        {
            "version": version,
            "bloques": [
                {"titulo": b["titulo"], "cuerpo": b["cuerpo"]} for b in bloques
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------


class ConsentTextoVersionService:
    """Servicio de gestion de versiones del texto de consentimiento."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_version(self, version: str) -> ConsentTextoVersionView:
        """Devuelve la version pedida; levanta ``KeyError`` si no existe (-> 404)."""
        row = await self._session.get(ConsentTextoVersionModel, version)
        if row is None:
            raise KeyError(f"Version de texto de consentimiento no encontrada: {version!r}")
        return self._to_view(row)

    async def get_vigente(
        self, consent_version_vigente: str
    ) -> ConsentTextoVersionView:
        """Devuelve la version vigente segun la config.

        Fallback: si la version vigente no existe en la tabla, usa v1 del
        catalogo en memoria (nunca rompe el flujo del estudiante).
        """
        row = await self._session.get(ConsentTextoVersionModel, consent_version_vigente)
        if row is not None:
            return self._to_view(row)

        # Fallback: intentar v1 en la tabla
        row_v1 = await self._session.get(ConsentTextoVersionModel, "v1")
        if row_v1 is not None:
            return self._to_view(row_v1)

        # Fallback ultimo recurso: catalogo en memoria (text_catalog.py _V1)
        from app.domain.consent_flow.text_catalog import get_texto
        texto = get_texto(consent_version_vigente) or get_texto("v1")
        if texto is None:
            raise KeyError(
                f"Version {consent_version_vigente!r} no encontrada y no hay fallback."
            )
        bloques_dict = [
            {"titulo": "¿Qué datos recolectamos?", "cuerpo": texto.que_se_recolecta},
            {"titulo": "¿Cómo los recolectamos?", "cuerpo": texto.como_se_recolecta},
            {"titulo": "¿Dónde se guardan?", "cuerpo": texto.donde_se_almacena},
            {"titulo": "¿Cuánto tiempo los conservamos?", "cuerpo": texto.cuanto_tiempo},
            {"titulo": "Tus derechos", "cuerpo": texto.derechos_titular},
        ]
        return ConsentTextoVersionView(
            version=texto.version,
            bloques=[BloqueConsentimiento(**b) for b in bloques_dict],
            hash_texto=compute_hash(texto.version, bloques_dict),
        )

    async def list_versions(self) -> list[ConsentVersionListItem]:
        """Lista todas las versiones publicadas, ordenadas por created_at."""
        result = await self._session.execute(
            select(ConsentTextoVersionModel).order_by(
                ConsentTextoVersionModel.created_at
            )
        )
        rows = result.scalars().all()
        return [
            ConsentVersionListItem(
                version=row.version,
                hash_texto=row.hash_texto,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def create_version(
        self, version: str, bloques: list[dict]
    ) -> ConsentTextoVersionView:
        """Crea una nueva version del texto.

        Levanta ``ValueError`` si la version ya existe (-> 409).
        Bloques deben ser lista de dicts con claves 'titulo' y 'cuerpo'.
        """
        existing = await self._session.get(ConsentTextoVersionModel, version)
        if existing is not None:
            raise ValueError(
                f"La version {version!r} ya existe (append-only: el texto no muta)."
            )
        hash_texto = compute_hash(version, bloques)
        row = ConsentTextoVersionModel(
            version=version,
            bloques=bloques,
            hash_texto=hash_texto,
        )
        self._session.add(row)
        await self._session.flush()  # asigna created_at server-side
        await self._session.refresh(row)
        return self._to_view(row)

    async def version_exists(self, version: str) -> bool:
        """Retorna True si la version existe en la tabla."""
        row = await self._session.get(ConsentTextoVersionModel, version)
        return row is not None

    # ---------------------------------------------------------------------------
    # helpers privados
    # ---------------------------------------------------------------------------

    def _to_view(self, row: ConsentTextoVersionModel) -> ConsentTextoVersionView:
        bloques = [
            BloqueConsentimiento(titulo=b["titulo"], cuerpo=b["cuerpo"])
            for b in row.bloques
        ]
        return ConsentTextoVersionView(
            version=row.version,
            bloques=bloques,
            hash_texto=row.hash_texto,
        )
