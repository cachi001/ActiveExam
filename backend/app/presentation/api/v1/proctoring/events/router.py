"""Router de ingestión de eventos de proctoring activeexam.

POST /sessions/{id}/events → 201/403/404

Exige token valido Y que la sesion pertenezca al principal (H1, IDOR — antes
cualquier alumno autenticado podia postear en la sesion de otro). Inyecta el
adapter ReinferenciaPort via Depends para mantener el desacople puerto/adapter
(DD-17).

L2.5: la respuesta incluye el veredicto 'coincide'/'discrepancia'/'no_evaluado'
pero NUNCA sanciona — es informacion para el revisor humano.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.proctoring.events.schemas import (
    IngestEventoIn,
    IngestEventoOut,
    IngestLoteIn,
    IngestLoteOut,
)


def create_events_router(
    get_db, get_reinferencia, *, require_autenticado, cipher=None, worm_storage=None
) -> APIRouter:
    """Factory del router de eventos. Recibe dependencias de DB y re-inferencia.

    ``require_autenticado``: guard de auth (cualquier token valido) — el alumno
    ingesta sus eventos de deteccion. Lo inyecta el router padre.
    ``cipher``: EvidenceCipher para cifrar el screenshot at-rest (Ley 25.326). None
    → se persiste en claro (tests/legacy).
    ``worm_storage``: puerto WORM (c-77). None (default) cuando MinIO no esta
    configurado — el screenshot se persiste UNICAMENTE en Postgres, sin cambios.
    """
    router = APIRouter()

    @router.post(
        "/sessions/{session_id}/events",
        status_code=http_status.HTTP_201_CREATED,
        response_model=IngestEventoOut,
        summary="Ingestar evento de deteccion con re-inferencia server-side",
    )
    async def ingestar_evento(
        session_id: str,
        body: IngestEventoIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        reinferencia: Annotated[ReinferenciaPort, Depends(get_reinferencia)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> IngestEventoOut:
        """Ingesta un evento de deteccion.

        Re-detecta rostros con MediaPipe server-side (mismo motor que el cliente),
        calcula SHA-256 del screenshot y persiste todo en proctoring_event.

        Responde con el veredicto de re-inferencia para que el frontend pueda
        mostrar alertas en tiempo real de discrepancias.

        L2.5: 'discrepancia' solo enriquece la evidencia — no sanciona.

        H1 (IDOR, pentest): antes cualquier token valido bastaba para postear en
        CUALQUIER sesion. Ahora ``event_service.ingestar_evento`` exige que la
        sesion pertenezca al principal (403 si no).
        """
        evento = await event_service.ingestar_evento(
            db=db,
            session_id=session_id,
            tipo=body.tipo,
            severidad=body.severidad.value,
            ts_cliente=body.ts_cliente,
            reinferencia=reinferencia,
            principal=principal,
            payload=body.payload,
            screenshot_base64=body.screenshot_base64,
            face_count_cliente=body.face_count_cliente,
            cipher=cipher,
            worm_storage=worm_storage,
            # c-78: el schema aceptaba este campo desde C-64 y el servicio lo
            # descartaba (no habia columna). Ahora se persiste y se contrasta.
            screenshot_sha256_cliente=body.screenshot_sha256_cliente,
        )
        return IngestEventoOut(
            evento_id=evento.id,
            veredicto_reinferencia=evento.veredicto_reinferencia,
            face_count_servidor=evento.face_count_servidor,
            screenshot_sha256=evento.screenshot_sha256,
        )

    @router.post(
        "/sessions/{session_id}/events/lote",
        status_code=http_status.HTTP_201_CREATED,
        response_model=IngestLoteOut,
        summary="Ingestar un LOTE de eventos (drenaje del buffer al reconectar)",
    )
    async def ingestar_lote(
        session_id: str,
        body: IngestLoteIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        reinferencia: Annotated[ReinferenciaPort, Depends(get_reinferencia)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> IngestLoteOut:
        """Ingesta varios eventos en un solo request, EN ORDEN.

        Es el camino del drenaje: cuando al alumno se le corta la conexion, lo
        que pasa mientras tanto queda en el buffer de IndexedDB y se reenvia al
        volver. De a uno, eso tardaba 35 s de media contra Render para una caida
        de 30 s (medido el 26/8/2026) — el plan free responde a 3 a 5 s por
        request y el drenaje los paga en serie.

        Mismas reglas que la ingesta de a uno, sin excepciones: misma
        re-inferencia, misma guarda de pertenencia (H1, IDOR) y mismo contrato de
        ack. Es el MISMO ``event_service.ingestar_evento``, no una copia — un
        segundo camino con reglas propias se desalinea con el tiempo.

        Los eventos se procesan en secuencia porque el orden de produccion es
        parte del contrato del replay, y el ack vuelve en la misma posicion.
        """
        resultados: list[IngestEventoOut] = []
        for item in body.eventos:
            evento = await event_service.ingestar_evento(
                db=db,
                session_id=session_id,
                tipo=item.tipo,
                severidad=item.severidad.value,
                ts_cliente=item.ts_cliente,
                reinferencia=reinferencia,
                principal=principal,
                payload=item.payload,
                screenshot_base64=item.screenshot_base64,
                face_count_cliente=item.face_count_cliente,
                cipher=cipher,
                worm_storage=worm_storage,
                screenshot_sha256_cliente=item.screenshot_sha256_cliente,
            )
            resultados.append(
                IngestEventoOut(
                    evento_id=evento.id,
                    veredicto_reinferencia=evento.veredicto_reinferencia,
                    face_count_servidor=evento.face_count_servidor,
                    screenshot_sha256=evento.screenshot_sha256,
                )
            )
        return IngestLoteOut(resultados=resultados)

    return router
