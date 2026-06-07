"""Repositorios SQLAlchemy para foto_referencia y embedding_referencia (C-56).

Cada repositorio encapsula el acceso a la DB para su respectiva tabla. La
logica de marcar registros anteriores como no vigentes garantiza que solo
haya un registro ``vigente = TRUE`` por usuario en cada momento.

Convencion del proyecto: snake_case en todos los metodos y columnas.
Tests sin mocks de DB (testcontainers / DB real).
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.transactional import (
    EmbeddingReferenciaModel,
    FotoReferenciaModel,
)


# ---------------------------------------------------------------------------
# FotoReferenciaRepository
# ---------------------------------------------------------------------------


class FotoReferenciaRepository:
    """Repositorio de fotos de perfil de referencia del alumno.

    Invariante: solo un registro ``vigente = TRUE`` por ``usuario_id``.
    Al crear uno nuevo, se llama primero a ``marcar_anteriores_no_vigentes``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def marcar_anteriores_no_vigentes(self, usuario_id: str) -> None:
        """Marca todos los registros vigentes del usuario como no vigentes.

        Se llama ANTES de crear el nuevo registro (garantia de invariante).
        """
        await self._session.execute(
            update(FotoReferenciaModel)
            .where(
                FotoReferenciaModel.usuario_id == usuario_id,
                FotoReferenciaModel.vigente == True,  # noqa: E712
            )
            .values(vigente=False)
        )

    async def crear(
        self,
        *,
        usuario_id: str,
        uri_storage: str,
        hash_sha256: str,
        bucket: str,
    ) -> FotoReferenciaModel:
        """Crea un nuevo registro vigente de foto de referencia.

        PRE-CONDICION: llamar a ``marcar_anteriores_no_vigentes`` en la misma
        transaccion antes de invocar este metodo.

        Args:
            usuario_id: UUID del usuario (FK a usuario.id).
            uri_storage: clave / key del objeto en el bucket MinIO/S3.
            hash_sha256: hash SHA-256 del contenido de la foto (integridad).
            bucket: nombre del bucket donde se almacena la foto.

        Returns:
            El modelo ORM recien creado, con ``id`` asignado por la DB.
        """
        row = FotoReferenciaModel(
            usuario_id=usuario_id,
            uri_storage=uri_storage,
            hash_sha256=hash_sha256,
            bucket=bucket,
            vigente=True,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def obtener_vigente(self, usuario_id: str) -> FotoReferenciaModel | None:
        """Devuelve el registro vigente del usuario, o None si no existe."""
        result = await self._session.execute(
            select(FotoReferenciaModel).where(
                FotoReferenciaModel.usuario_id == usuario_id,
                FotoReferenciaModel.vigente == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# EmbeddingReferenciaRepository
# ---------------------------------------------------------------------------


class EmbeddingReferenciaRepository:
    """Repositorio del embedding biometrico de referencia del alumno.

    Invariante: solo un registro ``vigente = TRUE`` por ``usuario_id``.
    Al crear uno nuevo, se llama primero a ``marcar_anteriores_no_vigentes``.

    IMPORTANTE: el ``embedding_cifrado`` que recibe este repositorio YA esta
    cifrado con Fernet (lo hace ``GuardarEmbeddingReferenciaService``). Este
    repositorio NO cifra ni descifra: solo persiste el ciphertext opaco.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def marcar_anteriores_no_vigentes(self, usuario_id: str) -> None:
        """Marca todos los embeddings vigentes del usuario como no vigentes."""
        await self._session.execute(
            update(EmbeddingReferenciaModel)
            .where(
                EmbeddingReferenciaModel.usuario_id == usuario_id,
                EmbeddingReferenciaModel.vigente == True,  # noqa: E712
            )
            .values(vigente=False)
        )

    async def crear(
        self,
        *,
        usuario_id: str,
        embedding_cifrado: str,
        algoritmo: str = "face-api-128d",
    ) -> EmbeddingReferenciaModel:
        """Crea un nuevo registro vigente de embedding de referencia.

        PRE-CONDICION: llamar a ``marcar_anteriores_no_vigentes`` en la misma
        transaccion antes de invocar este metodo.

        Args:
            usuario_id: UUID del usuario (FK a usuario.id).
            embedding_cifrado: Fernet token (ciphertext del embedding 128-d).
                NUNCA debe ser el vector en claro.
            algoritmo: identificador del motor de embedding (trazabilidad).
                Default: 'face-api-128d' (face-api 128 dimensiones).

        Returns:
            El modelo ORM recien creado, con ``id`` asignado por la DB.
        """
        row = EmbeddingReferenciaModel(
            usuario_id=usuario_id,
            embedding_cifrado=embedding_cifrado,
            algoritmo=algoritmo,
            vigente=True,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def obtener_vigente(self, usuario_id: str) -> EmbeddingReferenciaModel | None:
        """Devuelve el embedding vigente del usuario, o None si no existe.

        Usado por C-09 para obtener la referencia de comparacion 1:1.
        """
        result = await self._session.execute(
            select(EmbeddingReferenciaModel).where(
                EmbeddingReferenciaModel.usuario_id == usuario_id,
                EmbeddingReferenciaModel.vigente == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()
