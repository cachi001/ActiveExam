"""Informe de devolución al alumno (c-71 slice 2 D12, modelo de un solo paso).

Disclosure de debido proceso: se expone al alumno la evidencia AUTORITATIVA
server-side de SU sesión ÚNICAMENTE cuando la nota fue `anulado` (minimización,
Ley 25.326). El informe incluye: análisis por señal (qué indicó cada detector,
re-inferido server-side — NUNCA el buffer del cliente, regla #6), capturas vía
URL firmada 15 min, la decisión y el motivo.

Las capturas se filtran a la evidencia ESTRUCTURADA que el revisor eligió al
decidir (`decision_evidencia_ids`, lista de `proctoring_event.id`) — NO a
todos los eventos de la sesión. Antes de este cambio el informe mostraba
TODA la evidencia de la sesión sin importar qué había elegido el revisor,
lo que revelaba señales que el veredicto ni siquiera invocó.

Scope: SOLO la sesión del propio titular (RBAC estudiante, `03`). Sesión ajena
o sin anulación efectiva → None (el endpoint traduce a 404, sin revelar la
existencia de evidencia).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.moodle.resultados_query import _sesiones_con_restitucion
from app.application.verify_chain.service import VerifyChainService
from app.domain.review.decision import DecisionSesion, nota_esta_anulada
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.verify_chain import (
    SqlChainVerificationAuditor,
    SqlEventMaterialRepository,
)
from app.infrastructure.storage.presign import DOWNLOAD_EXPIRES_SECONDS, PresignService


@dataclass(frozen=True, slots=True)
class SenalAnalisis:
    """Una señal (detector) re-inferida server-side, agregada por tipo."""

    tipo: str
    severidad: str
    ocurrencias: int
    face_count_servidor: int | None
    veredicto_reinferencia: str


@dataclass(frozen=True, slots=True)
class CapturaFirmada:
    """Una captura de evidencia accesible por URL firmada.

    Lleva DE QUÉ EVENTO salió: una lista de "Ver captura 1, 2, 3" no le sirve a
    nadie para defenderse — el alumno necesita saber qué señal disparó cada
    imagen y en qué momento, que es justamente lo que se le está imputando.
    """

    object_key: str
    url: str
    expires_in: int
    tipo_evento: str | None = None
    severidad: str | None = None
    ocurrio_en: object | None = None  # datetime tz-aware; lo serializa Pydantic
    # Cadena de custodia (c-18 verify-chain, reutilizado tal cual — sin duplicar
    # lógica): recalculado server-side en CADA carga del informe, no cacheado, para
    # que la garantía sea "verificado ahora", no "verificado alguna vez". El alumno
    # no puede leer un hash por sí solo — por eso el badge en UI es la etiqueta
    # ('intact'/...), y estos 4 campos son el material para el certificado
    # descargable (defendible ante un tercero: abogado, comisión de apelaciones).
    integridad_estado: str = "no_verificado"
    integridad_algoritmo: str | None = None
    integridad_hash_esperado: str | None = None
    integridad_hash_actual: str | None = None
    integridad_verificado_en: str | None = None


@dataclass(frozen=True, slots=True)
class InformeDevolucion:
    """Informe de devolución completo (solo para sesión anulada del titular)."""

    session_id: str
    decision: str  # 'anulado'
    motivo: str | None
    senales: list[SenalAnalisis]
    capturas: list[CapturaFirmada]


async def build_informe_devolucion(
    *,
    db: AsyncSession,
    session_id: str,
    titular_idnumber: str,
    presign: PresignService,
) -> InformeDevolucion | None:
    """Construye el informe si — y solo si — la sesión es del titular y su nota
    fue anulada por fraude (efecto derivado del último acto). En cualquier otro
    caso devuelve None (minimización / scope).

    `titular_idnumber` también identifica al actor que dispara el verify-chain
    (queda auditado como acceso del propio titular, igual patrón que el resto
    del informe)."""
    row = (
        await db.execute(
            select(
                ProctoringSessionModel.id,
                ProctoringSessionModel.alumno_idnumber,
                ProctoringSessionModel.decision,
                ProctoringSessionModel.decision_motivo,
                ProctoringSessionModel.decision_evidencia_ids,
            ).where(ProctoringSessionModel.id == session_id)
        )
    ).first()
    if row is None:
        return None

    # Scope al titular: un alumno solo ve SU sesión (403/404 desde el endpoint).
    if not titular_idnumber or row[1] != titular_idnumber:
        return None

    try:
        decision = DecisionSesion(row[2]) if row[2] is not None else DecisionSesion.PENDIENTE
    except ValueError:
        decision = DecisionSesion.PENDIENTE

    restituidas = await _sesiones_con_restitucion(db, [session_id])
    if not nota_esta_anulada(decision, session_id in restituidas):
        # Minimización (Ley 25.326): sin anulación efectiva no se expone evidencia.
        return None

    evidencia_ids = set(row[4] or [])

    # Análisis por señal: re-inferencia server-side ya persistida (regla #6).
    ev_rows = (
        await db.execute(
            select(
                ProctoringEventModel.id,
                ProctoringEventModel.tipo,
                ProctoringEventModel.severidad,
                ProctoringEventModel.face_count_servidor,
                ProctoringEventModel.veredicto_reinferencia,
                ProctoringEventModel.screenshot_sha256,
                # Momento del evento: sin esto la captura no se puede ubicar en
                # la línea de tiempo del examen.
                ProctoringEventModel.ts_backend,
            )
            .where(ProctoringEventModel.session_id == session_id)
            .order_by(ProctoringEventModel.ts_backend)
        )
    ).all()

    # Reusa el servicio de c-18 tal cual (sin duplicar la lógica de re-hasheo):
    # el admin lo usa para peritar un evento puntual, acá se corre automático
    # sobre CADA captura que ya se le muestra al alumno.
    verify_service = VerifyChainService(
        event_repo=SqlEventMaterialRepository(db),
        auditor=SqlChainVerificationAuditor(db),
    )
    actor = f"{titular_idnumber}:informe-devolucion"

    agregado: dict[str, dict] = {}
    capturas: list[CapturaFirmada] = []
    for evento_id, tipo, severidad, face_count, veredicto, sha, ts in ev_rows:
        clave = f"{tipo}|{severidad}"
        acc = agregado.setdefault(
            clave,
            {
                "tipo": tipo,
                "severidad": severidad,
                "ocurrencias": 0,
                "face_count_servidor": face_count,
                "veredicto_reinferencia": veredicto,
            },
        )
        acc["ocurrencias"] += 1
        # Solo se muestran las capturas ELEGIDAS por el revisor como evidencia
        # del veredicto — no todo lo que ocurrió en la sesión.
        if sha and evento_id in evidencia_ids:
            firmada = presign.presign_download(
                object_key=sha, expires_in=DOWNLOAD_EXPIRES_SECONDS
            )
            cert = await verify_service.verify(evento_id, actor=actor)
            stage = cert.stages[0] if cert.stages else None
            capturas.append(
                CapturaFirmada(
                    object_key=firmada.object_key,
                    url=firmada.url,
                    expires_in=firmada.expires_in,
                    tipo_evento=tipo,
                    severidad=severidad,
                    ocurrio_en=ts,
                    integridad_estado=cert.status.value,
                    integridad_algoritmo=cert.algorithm,
                    integridad_hash_esperado=stage.expected if stage else None,
                    integridad_hash_actual=stage.actual if stage else None,
                    integridad_verificado_en=cert.verified_at,
                )
            )

    senales = [
        SenalAnalisis(
            tipo=a["tipo"],
            severidad=a["severidad"],
            ocurrencias=a["ocurrencias"],
            face_count_servidor=a["face_count_servidor"],
            veredicto_reinferencia=a["veredicto_reinferencia"],
        )
        for a in agregado.values()
    ]

    return InformeDevolucion(
        session_id=session_id,
        decision=row[2] or "",
        motivo=row[3],
        senales=senales,
        capturas=capturas,
    )
