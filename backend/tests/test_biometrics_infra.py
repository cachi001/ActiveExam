"""Tests de los adaptadores de infraestructura de biometria (C-09).

Sin DB ni red: cipher determinista (XOR) y repos en memoria ejercen el cifrado
at-rest del embedding (D5), la lectura descifrada de la referencia y la
re-inferencia server-side abstraida (DD-17).
"""

from __future__ import annotations

import asyncio

from app.domain.biometrics.liveness import (
    EvidenciaLiveness,
    RetoActivo,
    SenalesPasivas,
)
from app.domain.biometrics.ports import ReinferenciaResultado
from app.infrastructure.biometrics.crypto import (
    InjectedKmsCipher,
    VaultSecretProvider,
)
from app.infrastructure.biometrics.reference import (
    EncryptedReferenceReader,
    EncryptingEmbeddingRepository,
    deserializar_vector,
)
from app.infrastructure.vision.engine import ReinferenceVisionEngine

# Reusa el repo de embedding en memoria del test de servicio.
from tests.test_biometrics_service import InMemoryEmbeddingRepo


def _xor_cipher() -> InjectedKmsCipher:
    # Cifrado simetrico de juguete (XOR) para verificar el contrato sin cripto real.
    return InjectedKmsCipher(
        encryptor=lambda b: bytes(x ^ 0x5A for x in b),
        decryptor=lambda b: bytes(x ^ 0x5A for x in b),
    )


def test_embedding_se_persiste_cifrado_y_no_en_claro() -> None:
    async def run() -> None:
        from app.domain.entities.embedding import Embedding
        from app.domain.repositories.ports import EmbeddingRepository

        # Repo interno PLANO (sin cifrado propio): asi se aisla el cifrado del
        # decorador ``EncryptingEmbeddingRepository`` (D5).
        class PlainRepo(EmbeddingRepository):
            def __init__(self) -> None:
                self.items: list[Embedding] = []

            async def add(self, entity: Embedding) -> Embedding:
                self.items.append(entity)
                return entity

            async def get(self, entity_id: str):
                return None

            async def list(self):
                return list(self.items)

            async def update(self, entity: Embedding) -> Embedding:
                return entity

            async def delete(self, entity_id: str) -> None:
                pass

        inner = PlainRepo()
        repo = EncryptingEmbeddingRepository(inner, _xor_cipher())
        plaintext = b"1.0|0.0|0.5"
        await repo.add(Embedding(user_id="u1", vector_cifrado=plaintext, version="v1", fecha=""))
        # Lo persistido es el CIPHERTEXT del decorador, no el plaintext (D5).
        assert inner.items[0].vector_cifrado != plaintext
        assert inner.items[0].vector_cifrado == _xor_cipher().cifrar(plaintext)

    asyncio.run(run())


def test_lectura_de_referencia_descifra_y_deserializa() -> None:
    async def run() -> None:
        from app.domain.entities.embedding import Embedding

        cipher = _xor_cipher()
        inner = InMemoryEmbeddingRepo()
        # Guarda una referencia cifrada directamente (sin doble cifrado del repo de
        # test): ciframos el plaintext una vez y lo metemos sin pasar por su .add.
        plaintext = b"1.0|0.0|0.5"
        inner.items.append(
            Embedding(id="1", user_id="u1", vector_cifrado=cipher.cifrar(plaintext), version="v1", fecha="")
        )
        reader = EncryptedReferenceReader(inner, cipher)
        vector = await reader.leer_referencia(user_id="u1", exam_id="e1")
        assert vector == (1.0, 0.0, 0.5)

    asyncio.run(run())


def test_lectura_sin_referencia_devuelve_none() -> None:
    async def run() -> None:
        reader = EncryptedReferenceReader(InMemoryEmbeddingRepo(), _xor_cipher())
        assert await reader.leer_referencia(user_id="ux", exam_id="e1") is None

    asyncio.run(run())


def test_deserializar_vector_vacio() -> None:
    assert deserializar_vector(b"") == ()
    assert deserializar_vector(b"1.5") == (1.5,)


def test_vault_secret_provider_falla_si_vacio() -> None:
    async def run() -> None:
        provider = VaultSecretProvider(lambda: b"")
        try:
            await provider.secreto_maestro()
            raise AssertionError("debio fallar con secreto vacio")
        except RuntimeError:
            pass

    asyncio.run(run())


def test_reinference_engine_delega_en_inferenciador() -> None:
    async def run() -> None:
        liveness = EvidenciaLiveness(
            pasivas=SenalesPasivas(True, True, True),
            retos_solicitados=(RetoActivo.PARPADEAR,),
            retos_resueltos=(RetoActivo.PARPADEAR,),
        )
        recibido = {}

        async def fake_infer(uri: str, h: str) -> ReinferenciaResultado:
            recibido["uri"] = uri
            recibido["hash"] = h
            return ReinferenciaResultado(embedding=(1.0, 0.0), liveness=liveness)

        engine = ReinferenceVisionEngine(fake_infer)
        res = await engine.reinferir(clip_uri="s3://clip", clip_hash="h" * 64)
        assert res.embedding == (1.0, 0.0)
        assert recibido == {"uri": "s3://clip", "hash": "h" * 64}

    asyncio.run(run())
