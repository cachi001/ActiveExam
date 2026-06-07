"""Application service: verificacion biometrica 1:1 server-side (C-59).

Lee el embedding de referencia VIGENTE del usuario desde la DB, lo descifra
server-side con EmbeddingEncryptionService (C-56), y lo compara con el
embedding vivo mediante distancia coseno (C-45 / matching.py).

El embedding descifrado:
- NUNCA se loguea.
- NUNCA se devuelve al cliente.
- NUNCA se persiste en claro.
- Vive SOLO en el scope del request (variable local).

Ley 25.326 (regla dura #7): el embedding es dato sensible.
Regla #5: el sistema NUNCA emite veredicto disciplinario; la verificacion
prioriza / informa; la decision es siempre humana.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.biometrics.matching import (
    UMBRAL_COSENO_DEFECTO,
    EmbeddingInvalidoError,
    comparar_identidad,
)
from app.infrastructure.crypto.embedding_encryption import (
    EmbeddingEncryptionError,
    EmbeddingEncryptionService,
)
from app.infrastructure.persistence.repositories.biometric_reference import (
    EmbeddingReferenciaRepository,
)


class SinReferenciaVigenteError(RuntimeError):
    """El usuario no tiene embedding de referencia vigente en la DB.

    Mapeable a HTTP 404: el cliente debe derivar al flujo de enrollment
    (no es un error del embedding vivo ni de la comparacion).
    """


@dataclass(frozen=True, slots=True)
class ResultadoVerificacionReferencia:
    """DTO de resultado de la verificacion 1:1 server-side.

    Contiene solo los datos que pueden viajar al cliente:
    distancia, es_match y umbral. El embedding descifrado NO forma
    parte de este DTO (nunca sale del scope del service).
    """

    distancia: float
    es_match: bool
    umbral: float


class VerificarReferenciaVigenteService:
    """Verificacion biometrica 1:1 autenticada: backend busca referencia por JWT.

    Dependencias inyectadas (no se importa SlimSettings aqui):
    - session: AsyncSession (transaccion activa del request)
    - encryption: EmbeddingEncryptionService (instanciado en main_slim.py)

    Flujo (D2 del design):
    1. Buscar el embedding vigente del usuario via EmbeddingReferenciaRepository.
    2. Si no hay -> SinReferenciaVigenteError (-> 404).
    3. Descifrar con encryption.decrypt (Fernet). El plaintext vive solo aqui.
    4. Comparar con comparar_identidad (distancia coseno).
    5. Devolver ResultadoVerificacionReferencia (sin el embedding).
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        encryption: EmbeddingEncryptionService,
    ) -> None:
        self._session = session
        self._encryption = encryption

    async def ejecutar(
        self,
        usuario_id: str,
        embedding_vivo: list[float],
        umbral: float | None = None,
    ) -> ResultadoVerificacionReferencia:
        """Verifica el embedding vivo contra la referencia vigente del usuario.

        Args:
            usuario_id: str(UUID) del usuario, tomado del sub del JWT.
            embedding_vivo: vector 128-d capturado en vivo por el cliente.
            umbral: umbral coseno opcional; si None usa UMBRAL_COSENO_DEFECTO (0.35).

        Returns:
            ResultadoVerificacionReferencia con distancia, es_match, umbral.

        Raises:
            SinReferenciaVigenteError: si el usuario no tiene embedding vigente.
            EmbeddingInvalidoError: si el embedding_vivo es de dimension invalida.
            EmbeddingEncryptionError: si el ciphertext esta corrupto/clave rotada.
        """
        umbral_efectivo = umbral if umbral is not None else UMBRAL_COSENO_DEFECTO

        # 1. Buscar el embedding vigente en la DB (sin descifrar).
        repo = EmbeddingReferenciaRepository(self._session)
        modelo = await repo.obtener_vigente(usuario_id)

        if modelo is None:
            raise SinReferenciaVigenteError(
                f"El usuario {usuario_id!r} no tiene embedding de referencia vigente. "
                "Complete el enrollment biometrico antes de la verificacion."
            )

        # 2. Descifrar server-side. El plaintext vive SOLO en esta variable local.
        # Si falla (clave rotada / ciphertext corrupto) -> EmbeddingEncryptionError -> 500.
        # NO se loguea el embedding descifrado (regla dura #7).
        referencia_descifrada: list[float] = self._encryption.decrypt(modelo.embedding_cifrado)

        # 3. Comparar por distancia coseno (puro, sin DB ni cripto).
        # EmbeddingInvalidoError si dimension invalida -> 422.
        comparacion = comparar_identidad(
            embedding_vivo,
            referencia_descifrada,
            umbral=umbral_efectivo,
        )

        # 4. El embedding descifrado sale de scope aqui. Devolver solo el DTO.
        return ResultadoVerificacionReferencia(
            distancia=comparacion.distancia,
            es_match=comparacion.es_match,
            umbral=comparacion.umbral,
        )


class EstadoReferenciaService:
    """Consulta si el usuario tiene embedding de referencia vigente (C-59, D3).

    NO descifra. NO devuelve el embedding. Solo responde el booleano
    necesario para que el frontend pueda mostrar el gate de enrollment
    antes de intentar la verificacion.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def tiene_referencia_vigente(self, usuario_id: str) -> bool:
        """Devuelve True si el usuario tiene embedding de referencia vigente.

        Args:
            usuario_id: str(UUID) del usuario, tomado del sub del JWT.

        Returns:
            True si existe al menos un registro vigente; False si no.
        """
        repo = EmbeddingReferenciaRepository(self._session)
        modelo = await repo.obtener_vigente(usuario_id)
        return modelo is not None
