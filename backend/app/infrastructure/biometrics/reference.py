"""Lectura del embedding de referencia cifrado y persistencia cifrada (C-09, D5).

- ``EncryptedReferenceReader`` (implementa ``ReferenceEmbeddingPort``): lee el
  embedding de referencia (cargado en C-07) cifrado de la DB via ``EmbeddingRepository``,
  lo descifra con el ``KmsCipher`` y deserializa el vector para la comparacion
  server-side. El ciphertext y la clave NUNCA salen de infraestructura.
- ``EncryptingEmbeddingRepository``: decorador del ``EmbeddingRepository`` que CIFRA
  el embedding capturado at-rest en ``add`` (D5): el dominio entrega la
  representacion canonica (bytes), el adaptador la cifra antes de persistir.

La serializacion del vector usa el mismo formato que el dominio
(``_serializar_para_cifrado``: floats separados por '|').
"""

from __future__ import annotations

from app.domain.biometrics.ports import ReferenceEmbeddingPort
from app.domain.entities.embedding import Embedding
from app.domain.repositories.ports import EmbeddingRepository
from app.infrastructure.biometrics.crypto import KmsCipher


def deserializar_vector(plaintext: bytes) -> tuple[float, ...]:
    """Convierte la representacion canonica '|'-separada a tupla de floats."""
    if not plaintext:
        return ()
    return tuple(float(x) for x in plaintext.decode("utf-8").split("|"))


class EncryptedReferenceReader(ReferenceEmbeddingPort):
    """Lee y descifra el embedding de referencia del estudiante (C-07, D5).

    Estrategia de busqueda: el embedding de referencia se identifica por
    ``user_id``; la seleccion del mas reciente la decide el repositorio (aqui se
    toma el primero que matchea por usuario). El ``exam_id`` se acepta para
    finalidad acotada y trazabilidad, sin ampliar el alcance de la lectura."""

    def __init__(self, embeddings: EmbeddingRepository, cipher: KmsCipher) -> None:
        self._embeddings = embeddings
        self._cipher = cipher

    async def leer_referencia(
        self, *, user_id: str, exam_id: str
    ) -> tuple[float, ...] | None:
        candidatos = [
            e for e in await self._embeddings.list() if e.user_id == user_id
        ]
        if not candidatos:
            return None
        # El ciphertext nunca se expone al cliente: se descifra server-side y solo
        # el vector en claro vive el tiempo de la comparacion.
        plaintext = self._cipher.descifrar(candidatos[-1].vector_cifrado)
        return deserializar_vector(plaintext)


class EncryptingEmbeddingRepository(EmbeddingRepository):
    """Decorador que CIFRA el embedding capturado at-rest antes de persistir (D5).

    Envuelve un ``EmbeddingRepository`` concreto: en ``add`` cifra
    ``vector_cifrado`` (que el dominio entrega como plaintext canonico) con el KMS;
    en ``get``/``list`` devuelve el ciphertext tal cual (el descifrado es explicito
    via el reader). Asi nunca se persiste el embedding en claro."""

    def __init__(self, inner: EmbeddingRepository, cipher: KmsCipher) -> None:
        self._inner = inner
        self._cipher = cipher

    async def add(self, entity: Embedding) -> Embedding:
        cifrado = Embedding(
            id=entity.id,
            user_id=entity.user_id,
            vector_cifrado=self._cipher.cifrar(entity.vector_cifrado),
            version=entity.version,
            fecha=entity.fecha,
        )
        return await self._inner.add(cifrado)

    async def get(self, entity_id: str) -> Embedding | None:
        return await self._inner.get(entity_id)

    async def list(self) -> list[Embedding]:
        return await self._inner.list()

    async def update(self, entity: Embedding) -> Embedding:
        return await self._inner.update(entity)

    async def delete(self, entity_id: str) -> None:
        await self._inner.delete(entity_id)
