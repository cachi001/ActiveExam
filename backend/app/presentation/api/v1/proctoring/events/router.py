"""Router de ingestión de eventos de proctoring activeexam.

POST /sessions/{id}/events → 201/403/404

Exige token valido Y que la sesion pertenezca al principal (H1, IDOR — antes
cualquier alumno autenticado podia postear en la sesion de otro). Inyecta el
adapter ReinferenciaPort via Depends para mantener el desacople puerto/adapter
(DD-17).

L2.5: la respuesta incluye el veredicto 'coincide'/'discrepancia'/'no_evaluado'
pero NUNCA sanciona — es informacion para el revisor humano.
"""

import base64
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
from app.application.proctoring.captura_almacenada import reconstruir_data_url
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.proctoring.events.schemas import (
    IngestEventoIn,
    IngestEventoOut,
    IngestLoteIn,
    IngestLoteOut,
    normalizar_severidad,
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
        "/sessions/{session_id}/events/binario",
        status_code=http_status.HTTP_201_CREATED,
        response_model=IngestEventoOut,
        summary="Ingestar evento con la captura BINARIA (sin inflarla en base64)",
    )
    async def ingestar_evento_binario(  # noqa: PLR0913 — es un form, no una firma de dominio
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        reinferencia: Annotated[ReinferenciaPort, Depends(get_reinferencia)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
        tipo: Annotated[str, Form()],
        severidad: Annotated[str, Form()],
        ts_cliente: Annotated[datetime, Form()],
        captura: Annotated[UploadFile | None, File()] = None,
        screenshot_prefijo: Annotated[str | None, Form()] = None,
        face_count_cliente: Annotated[int | None, Form()] = None,
        screenshot_sha256_cliente: Annotated[str | None, Form()] = None,
    ) -> IngestEventoOut:
        """Misma ingesta que el endpoint JSON, con la imagen viajando CRUDA.

        c-78 §16.5: mandar la captura como data URL dentro del JSON la infla un
        tercio (base64 son 4 bytes de texto por cada 3 de imagen, y encima el JSON
        escapa el string). Con 100 alumnos subiendo capturas durante dos horas por el
        enlace de su casa, ese tercio se paga en tiempo de subida.

        El endpoint JSON NO se toca: sigue siendo el camino soportado. Este es
        aditivo, para que un cliente a medio migrar nunca quede sin poder mandar
        evidencia.

        **El data URL se reconstruye exacto** y se delega en la MISMA función de
        ingesta. Por eso `screenshot_sha256` da idéntico por los dos caminos, que es
        la condición que no se puede romper: ese hash sostiene la cadena de custodia
        y verify-chain compara contra él toda la evidencia histórica.
        """
        binario = await captura.read() if captura is not None else None

        # El prefijo canónico va SIN la coma final: `separar_data_url` la deja fuera
        # y `reconstruir_data_url` la vuelve a poner. Pero un cliente que parta su
        # data URL de la forma obvia (`url.split("base64,")` o quedarse con todo
        # hasta la coma inclusive) la manda incluida, y ahí saldría
        # `...base64,,AAAA`: un hash distinto, o sea evidencia que no verifica, sin
        # ningún error visible. Se acepta con coma o sin ella.
        if screenshot_prefijo and screenshot_prefijo.endswith(","):
            screenshot_prefijo = screenshot_prefijo[:-1]

        # `reconstruir_data_url` es el inverso exacto de lo que hace el guardado, y
        # respeta el mime TAL CUAL vino (no lo normaliza): un 'image/jpeg' que
        # volviera como 'image/png' cambiaría el hash de ese evento.
        screenshot_base64 = reconstruir_data_url(screenshot_prefijo, binario)
        if binario is not None and screenshot_base64 is None:
            # Llegó la imagen pero sin prefijo declarado. Se asume PNG en vez de
            # descartar la evidencia: perder la captura de un evento es peor que
            # guardarla con un mime supuesto, y el hash sigue siendo consistente con
            # lo que se guarda.
            screenshot_base64 = "data:image/png;base64," + base64.b64encode(
                binario
            ).decode("ascii")

        evento = await event_service.ingestar_evento(
            db=db,
            session_id=session_id,
            tipo=tipo,
            severidad=str(normalizar_severidad(severidad)),
            ts_cliente=ts_cliente,
            reinferencia=reinferencia,
            principal=principal,
            payload=None,
            screenshot_base64=screenshot_base64,
            face_count_cliente=face_count_cliente,
            cipher=cipher,
            worm_storage=worm_storage,
            screenshot_sha256_cliente=screenshot_sha256_cliente,
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
