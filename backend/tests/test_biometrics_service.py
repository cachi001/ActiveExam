"""Tests del VerifyIdentityService con puertos EN MEMORIA (C-09, sin DB).

Cubre el pipeline re-inferido server-side:
- exito -> emite clave de sesion rotativa + persiste embedding cifrado + habilita.
- cliente "verificado" pero re-inferencia no coincide -> NO habilita (RN-GLB-01).
- liveness fallido -> no compara, cuenta como fallo.
- 3 fallos -> evento critico + escalacion a proctor, sin abort ni sancion (L2.5).
- referencia leida via puerto (cifrada en infra); embedding persistido no en claro.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.biometrics.service import (
    SEVERIDAD_CRITICA,
    TIPO_EVENTO_FALLO_BIO,
    TOPIC_ESCALACION_PROCTOR_BIO,
    VerifyIdentityService,
)
from app.application.consent.service import ConsentService
from app.application.exam_config.service import ExamConfigInput, ExamConfigService
from app.domain.biometrics.liveness import (
    EvidenciaLiveness,
    RetoActivo,
    SenalesPasivas,
)
from app.domain.biometrics.ports import (
    ReferenceEmbeddingPort,
    ReinferenciaResultado,
    SecretProviderPort,
    VisionEnginePort,
)
from app.domain.biometrics.retries import EstadoVerificacion, VeredictoIntento
from app.domain.entities.embedding import Embedding
from app.domain.entities.event import Evento
from app.domain.entities.session import EstadoSesion, Sesion
from app.domain.repositories.ports import (
    EmbeddingRepository,
    EventRepository,
    SessionRepository,
)
from app.infrastructure.messaging.port import MessageQueuePort, QueuedMessage

# Importa los dobles en memoria del test de consent (mismo contrato de puertos).
from tests.test_consent_service import (
    FakeQueue,
    InMemoryAuditRepo,
    InMemoryConsentRepo,
)

_PASIVO_OK = SenalesPasivas(
    parpadeo_detectado=True, micro_movimientos=True, profundidad_3d_coherente=True
)


def _liveness_ok() -> EvidenciaLiveness:
    return EvidenciaLiveness(
        pasivas=_PASIVO_OK,
        retos_solicitados=(RetoActivo.PARPADEAR,),
        retos_resueltos=(RetoActivo.PARPADEAR,),
    )


def _liveness_falla() -> EvidenciaLiveness:
    return EvidenciaLiveness(
        pasivas=SenalesPasivas(False, False, False),
        retos_solicitados=(RetoActivo.PARPADEAR,),
        retos_resueltos=(),
    )


class FakeVision(VisionEnginePort):
    """Motor de vision server-side fake: devuelve embedding + liveness fijados."""

    def __init__(self, embedding: tuple[float, ...], liveness: EvidenciaLiveness) -> None:
        self._res = ReinferenciaResultado(embedding=embedding, liveness=liveness)
        self.clips_reinferidos: list[str] = []

    async def reinferir(self, *, clip_uri: str, clip_hash: str) -> ReinferenciaResultado:
        self.clips_reinferidos.append(clip_uri)
        return self._res


class FakeReferences(ReferenceEmbeddingPort):
    def __init__(self, vector: tuple[float, ...] | None) -> None:
        self._vector = vector

    async def leer_referencia(self, *, user_id: str, exam_id: str):
        return self._vector


class FakeSecrets(SecretProviderPort):
    async def secreto_maestro(self) -> bytes:
        return b"secreto-maestro-inyectado"


class InMemoryEmbeddingRepo(EmbeddingRepository):
    def __init__(self) -> None:
        self.items: list[Embedding] = []

    async def add(self, entity: Embedding) -> Embedding:
        # Simula el cifrado at-rest del adaptador KMS: el repo guarda ciphertext.
        cifrado = bytes(b ^ 0x5A for b in entity.vector_cifrado)
        guardado = Embedding(
            id=str(len(self.items) + 1),
            user_id=entity.user_id,
            vector_cifrado=cifrado,
            version=entity.version,
            fecha="2026-05-30",
        )
        self.items.append(guardado)
        return guardado

    async def get(self, entity_id: str):
        return next((e for e in self.items if e.id == entity_id), None)

    async def list(self):
        return list(self.items)

    async def update(self, entity: Embedding) -> Embedding:
        return entity

    async def delete(self, entity_id: str) -> None:
        self.items = [e for e in self.items if e.id != entity_id]


class InMemoryEventRepo(EventRepository):
    def __init__(self) -> None:
        self.items: list[Evento] = []

    async def append(self, entity: Evento) -> Evento:
        guardado = Evento(
            id=str(len(self.items) + 1),
            session_id=entity.session_id,
            exam_id=entity.exam_id,
            tipo=entity.tipo,
            severidad=entity.severidad,
            timestamp_cliente=entity.timestamp_cliente,
            timestamp_backend=entity.timestamp_backend,
            payload=entity.payload,
            firma=entity.firma,
            schema_version=entity.schema_version,
        )
        self.items.append(guardado)
        return guardado

    async def get(self, entity_id: str):
        return next((e for e in self.items if e.id == entity_id), None)

    async def list(self):
        return list(self.items)


class InMemorySessionRepo(SessionRepository):
    def __init__(self, sesion: Sesion) -> None:
        self.sesion = sesion

    async def add(self, entity: Sesion) -> Sesion:
        self.sesion = entity
        return entity

    async def get(self, entity_id: str):
        return self.sesion if self.sesion.id == entity_id else None

    async def list(self):
        return [self.sesion]

    async def update(self, entity: Sesion) -> Sesion:
        self.sesion = entity
        return entity


async def _build_service(
    *,
    embedding_capturado: tuple[float, ...],
    referencia: tuple[float, ...] | None,
    liveness: EvidenciaLiveness,
    consentido: bool = True,
):
    if True:
        consents, audit, queue = InMemoryConsentRepo(), InMemoryAuditRepo(), FakeQueue()
        consent = ConsentService(consents, audit, queue)
        exams_repo, assigns_repo = _ExamRepoMem(), _AssignRepoMem()
        exam_cfg = ExamConfigService(exams_repo, assigns_repo)
        examen = await exam_cfg.create_exam(
            ExamConfigInput(
                nombre="Examen", inicio="2026-01-01T00:00:00Z",
                fin="2026-12-31T00:00:00Z", umbral_score=0.5,
                detectores=("face_mesh",), exige_biometria=True,
            )
        )
        if consentido:
            await consent.record_consent(
                user_id="u1", exam_id=examen.id, version_texto=None,
                affirmative_action=True, timestamp="t",
            )
        # Referencia presente para que reference_missing sea False cuando aplica.
        if referencia is not None:
            await exam_cfg.register_reference(
                examen.id, "u1", uri="s3://ref", hash_binario="h", precomputada=True
            )

        vision = FakeVision(embedding_capturado, liveness)
        refs = FakeReferences(referencia)
        emb_repo = InMemoryEmbeddingRepo()
        evt_repo = InMemoryEventRepo()
        ses = Sesion(id="sess-1", user_id="u1", exam_id=examen.id, clave_sesion="provisional")
        ses_repo = InMemorySessionRepo(ses)

        svc = VerifyIdentityService(
            vision=vision, referencias=refs, secretos=FakeSecrets(),
            embeddings=emb_repo, eventos=evt_repo, sesiones=ses_repo,
            consent=consent, exam_config=exam_cfg, queue=queue,
        )
        return svc, ses, emb_repo, evt_repo, ses_repo, queue, vision


# Repos en memoria minimos para Examen/Asignacion (contrato de C-05/C-07).
from app.domain.entities.assignment import Asignacion  # noqa: E402
from app.domain.entities.exam import Examen  # noqa: E402
from app.domain.repositories.ports import (  # noqa: E402
    AssignmentRepository,
    ExamRepository,
)


class _ExamRepoMem(ExamRepository):
    def __init__(self) -> None:
        self.items: dict[str, Examen] = {}
        self._seq = 0

    async def add(self, entity: Examen) -> Examen:
        self._seq += 1
        e = Examen(
            id=str(self._seq), nombre=entity.nombre, umbral_score=entity.umbral_score,
            parametros=entity.parametros, detectores=entity.detectores,
            ventana=entity.ventana, retencion=entity.retencion,
        )
        self.items[e.id] = e
        return e

    async def get(self, entity_id: str):
        return self.items.get(entity_id)

    async def list(self):
        return list(self.items.values())

    async def update(self, entity: Examen) -> Examen:
        self.items[entity.id] = entity
        return entity


class _AssignRepoMem(AssignmentRepository):
    def __init__(self) -> None:
        self.items: list[Asignacion] = []

    async def add(self, entity: Asignacion) -> Asignacion:
        self.items.append(entity)
        return entity

    async def get(self, entity_id: str):
        return None

    async def list(self):
        return list(self.items)

    async def update(self, entity: Asignacion) -> Asignacion:
        return entity


def test_verificacion_exitosa_emite_clave_y_persiste_embedding_cifrado() -> None:
    async def run() -> None:
        svc, ses, emb_repo, evt_repo, ses_repo, queue, vision = await _build_service(
            embedding_capturado=(1.0, 0.0, 0.0),
            referencia=(0.999, 0.01, 0.0),  # casi identico -> match
            liveness=_liveness_ok(),
        )
        estado, outcome = await svc.verify(
            sesion=ses, estado=EstadoVerificacion.inicial(),
            clip_uri="s3://clip", clip_hash="h", timestamp="t",
        )
        assert outcome.veredicto == VeredictoIntento.VERIFICADO
        assert outcome.clave_sesion_emitida is True
        # Re-inferencia server-side ocurrio sobre el clip (RN-GLB-01).
        assert vision.clips_reinferidos == ["s3://clip"]
        # Clave de sesion rotativa emitida en la sesion (no la provisional).
        assert ses_repo.sesion.clave_sesion != "provisional"
        assert len(ses_repo.sesion.clave_sesion) == 64
        # Sesion habilitada (transiciono a ACTIVA).
        assert ses_repo.sesion.estado == EstadoSesion.ACTIVA
        # Embedding persistido CIFRADO (no en claro): el repo guardo ciphertext.
        assert len(emb_repo.items) == 1
        guardado = emb_repo.items[0]
        en_claro = "|".join(repr(x) for x in (1.0, 0.0, 0.0)).encode("utf-8")
        assert guardado.vector_cifrado != en_claro  # cifrado at-rest (D5)

    asyncio.run(run())


def test_cliente_verificado_pero_reinferencia_no_coincide_no_habilita() -> None:
    async def run() -> None:
        # El cliente "dice" verificado, pero el embedding RE-INFERIDO no coincide
        # con la referencia -> el backend NO habilita (RN-GLB-01, D2).
        svc, ses, emb_repo, evt_repo, ses_repo, queue, _ = await _build_service(
            embedding_capturado=(0.0, 1.0),  # ortogonal a la referencia
            referencia=(1.0, 0.0),
            liveness=_liveness_ok(),
        )
        estado, outcome = await svc.verify(
            sesion=ses, estado=EstadoVerificacion.inicial(),
            clip_uri="s3://clip", clip_hash="h", timestamp="t",
        )
        assert outcome.clave_sesion_emitida is False
        assert outcome.veredicto == VeredictoIntento.REINTENTO_DISPONIBLE
        assert ses_repo.sesion.clave_sesion == "provisional"  # no se emitio clave
        assert emb_repo.items == []  # no se persistio embedding

    asyncio.run(run())


def test_liveness_fallido_no_ejecuta_comparacion() -> None:
    async def run() -> None:
        svc, ses, emb_repo, evt_repo, ses_repo, queue, _ = await _build_service(
            embedding_capturado=(1.0, 0.0),
            referencia=(1.0, 0.0),  # coincidiria, pero liveness falla
            liveness=_liveness_falla(),
        )
        estado, outcome = await svc.verify(
            sesion=ses, estado=EstadoVerificacion.inicial(),
            clip_uri="s3://clip", clip_hash="h", timestamp="t",
        )
        # Liveness fallido cuenta como fallo del intento; no emite clave.
        assert outcome.clave_sesion_emitida is False
        assert outcome.distancia is None  # nunca llego a comparar

    asyncio.run(run())


def test_tercer_fallo_emite_evento_critico_y_escala_sin_sancion() -> None:
    async def run() -> None:
        svc, ses, emb_repo, evt_repo, ses_repo, queue, _ = await _build_service(
            embedding_capturado=(0.0, 1.0),  # no-match
            referencia=(1.0, 0.0),
            liveness=_liveness_ok(),
        )
        estado = EstadoVerificacion.inicial()
        for _ in range(2):
            estado, outcome = await svc.verify(
                sesion=ses, estado=estado,
                clip_uri="s3://clip", clip_hash="h", timestamp="t",
            )
            assert outcome.escalado_a_proctor is False
        # 3.º fallo -> escala.
        estado, outcome = await svc.verify(
            sesion=ses, estado=estado,
            clip_uri="s3://clip", clip_hash="h", timestamp="t",
        )
        assert outcome.veredicto == VeredictoIntento.ESCALAR_A_PROCTOR
        assert outcome.escalado_a_proctor is True
        # Evento CRITICO emitido (consumible por panel C-15).
        assert len(evt_repo.items) == 1
        assert evt_repo.items[0].tipo == TIPO_EVENTO_FALLO_BIO
        assert evt_repo.items[0].severidad == SEVERIDAD_CRITICA
        # Escalacion por la cola al proctor.
        assert queue.enqueued[-1][0] == TOPIC_ESCALACION_PROCTOR_BIO
        # NUNCA aborta ni sanciona: la sesion no quedo cerrada/sancionada.
        assert ses_repo.sesion.estado != EstadoSesion.CERRADA

    asyncio.run(run())


def test_sin_consentimiento_no_verifica() -> None:
    async def run() -> None:
        from app.domain.consent_flow.errors import ConsentNotResolvedError

        svc, ses, *_ = await _build_service(
            embedding_capturado=(1.0, 0.0), referencia=(1.0, 0.0),
            liveness=_liveness_ok(), consentido=False,
        )
        with pytest.raises(ConsentNotResolvedError):
            await svc.verify(
                sesion=ses, estado=EstadoVerificacion.inicial(),
                clip_uri="s3://clip", clip_hash="h", timestamp="t",
            )

    asyncio.run(run())
