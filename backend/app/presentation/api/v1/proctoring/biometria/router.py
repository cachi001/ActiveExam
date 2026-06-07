"""Router de biometria de proctoring slim.

Endpoints:
- POST /sessions/{id}/biometria         → 200/404 (sin auth, demo)
- POST /biometria/verificar             → 200 (stateless, demo-only, sin auth)
- POST /biometria/verificar-referencia  → 200/404/422/500 (stateful, auth estudiante, C-59)
- GET  /biometria/referencia/estado     → 200 (auth estudiante, C-59)

Ley 25.326: el embedding se trata como dato sensible en toda la capa.
Regla dura #5: el sistema NUNCA emite veredicto disciplinario; la verificacion
informa/prioriza; la decision siempre es humana.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.biometrics.verificar_referencia_vigente import (
    EstadoReferenciaService,
    SinReferenciaVigenteError,
    VerificarReferenciaVigenteService,
)
from app.application.proctoring import biometria_service
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.biometrics.matching import (
    UMBRAL_COSENO_DEFECTO,
    EmbeddingInvalidoError,
    comparar_identidad,
)
from app.infrastructure.crypto.embedding_encryption import (
    EmbeddingEncryptionError,
    EmbeddingEncryptionService,
)
from app.presentation.api.v1.proctoring.biometria.schemas import (
    BiometriaOut,
    EstadoReferenciaOut,
    GuardarBiometriaIn,
    VerificarIdentidadIn,
    VerificarIdentidadOut,
    VerificarReferenciaIn,
    VerificarReferenciaOut,
)


def create_biometria_router(
    get_db,
    get_embedding_encryption=None,
    require_estudiante=None,
) -> APIRouter:
    """Factory del router de biometria.

    Args:
        get_db: dependencia FastAPI que devuelve AsyncSession.
        get_embedding_encryption: dependencia FastAPI que devuelve
            EmbeddingEncryptionService (inyectado desde el state, patron slim).
            Si es None, los endpoints stateful C-59 no estaran disponibles.
        require_estudiante: dependencia FastAPI que exige rol ESTUDIANTE
            (inyectada desde create_proctoring_router, sin importar SlimSettings).
            Si es None, los endpoints stateful C-59 no estaran disponibles.
    """
    router = APIRouter()

    # -------------------------------------------------------------------------
    # POST /sessions/{id}/biometria — sin auth (demo/PoC, D7)
    # -------------------------------------------------------------------------

    @router.post(
        "/sessions/{session_id}/biometria",
        response_model=BiometriaOut,
        summary="Guardar resultado biometrico de la sesion",
    )
    async def guardar_biometria(
        session_id: str,
        body: GuardarBiometriaIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> BiometriaOut:
        """Persiste el resultado del liveness challenge y verificacion biometrica.

        Ley 25.326: el embedding facial es dato sensible. PRODUCCION: cifrar con
        KMS antes de persistir; purgar al egreso del estudiante (DD-13, DSR).
        """
        await biometria_service.guardar_biometria(
            db=db,
            session_id=session_id,
            liveness_ok=body.liveness_ok,
            retos_resueltos=body.retos_resueltos,
            resultado=body.resultado,
            embedding=body.embedding,
        )
        return BiometriaOut(ok=True)

    # -------------------------------------------------------------------------
    # POST /biometria/verificar — DEMO-ONLY, stateless, sin auth, sin DB
    #
    # Conservado para retrocompat (C-45). El cliente manda ambos embeddings.
    # NO usar en produccion: el embedding de referencia viaja al cliente,
    # lo que viola Ley 25.326 / regla dura #7.
    # Para produccion usar POST /biometria/verificar-referencia (C-59).
    # -------------------------------------------------------------------------

    @router.post(
        "/biometria/verificar",
        response_model=VerificarIdentidadOut,
        summary="[DEMO-ONLY] Verificacion biometrica 1:1 stateless (sin DB, sin auth)",
        description=(
            "Endpoint stateless de retrocompat (C-45). Recibe ambos embeddings del cliente "
            "y compara por distancia coseno sin consultar la DB. "
            "**SOLO para modo demo** (VITE_USE_REAL_BACKEND=0). "
            "En produccion usar POST /biometria/verificar-referencia (C-59, stateful, autenticado)."
        ),
    )
    async def verificar_identidad(
        body: VerificarIdentidadIn,
    ) -> VerificarIdentidadOut:
        """Compara dos embeddings faciales por distancia coseno (RN-BIO-01/02/03).

        Endpoint stateless: no persiste ni consulta la DB.
        Ley 25.326: ambos embeddings son dato sensible; no se loguean.
        """
        umbral = body.umbral if body.umbral is not None else UMBRAL_COSENO_DEFECTO
        try:
            resultado = comparar_identidad(
                body.embedding_vivo,
                body.embedding_referencia,
                umbral=umbral,
            )
        except EmbeddingInvalidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return VerificarIdentidadOut(
            distancia=resultado.distancia,
            es_match=resultado.es_match,
            umbral=resultado.umbral,
        )

    # -------------------------------------------------------------------------
    # C-59: endpoints stateful autenticados (solo si se inyectaron las deps)
    # -------------------------------------------------------------------------

    if get_embedding_encryption is not None and require_estudiante is not None:

        # POST /biometria/verificar-referencia — stateful, auth estudiante
        @router.post(
            "/biometria/verificar-referencia",
            response_model=VerificarReferenciaOut,
            summary="Verificacion biometrica 1:1 server-side (stateful, autenticada)",
            description=(
                "El backend identifica al usuario por el JWT (sub = str(usuario.id)), "
                "busca el embedding de referencia VIGENTE en la DB, lo descifra server-side "
                "y compara con el embedding vivo. "
                "El embedding de referencia NUNCA viaja al cliente (Ley 25.326, regla dura #7). "
                "La verificacion informa/prioriza; la decision disciplinaria es siempre humana "
                "(regla dura #5, L2.5)."
            ),
        )
        async def verificar_referencia(
            body: VerificarReferenciaIn,
            db: Annotated[AsyncSession, Depends(get_db)],
            encryption: Annotated[EmbeddingEncryptionService, Depends(get_embedding_encryption)],
            principal: Annotated[AuthenticatedPrincipal, Depends(require_estudiante)],
        ) -> VerificarReferenciaOut:
            """Verifica el embedding vivo contra la referencia cifrada del usuario.

            - 200: verificacion ejecutada (es_match=true o false).
            - 401: sin Bearer / token invalido.
            - 403: rol incorrecto.
            - 404: el usuario no tiene embedding de referencia vigente -> enrollment pendiente.
            - 422: embedding_vivo de dimension invalida o campo extra en el body.
            - 500: error de descifrado (clave rotada / ciphertext corrupto).

            Ley 25.326: el embedding descifrado NO se incluye en la respuesta ni en los logs.
            Regla #5: es_match=false NO es una sancion; prioriza para revision humana.
            """
            if not principal.subject:
                raise HTTPException(
                    status_code=401,
                    detail="Token no porta un subject (sub) valido.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            service = VerificarReferenciaVigenteService(session=db, encryption=encryption)
            try:
                resultado = await service.ejecutar(
                    usuario_id=principal.subject,
                    embedding_vivo=body.embedding_vivo,
                    umbral=body.umbral,
                )
            except SinReferenciaVigenteError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=str(exc),
                ) from exc
            except EmbeddingInvalidoError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc
            except EmbeddingEncryptionError:
                # NO exponer detalle de cripto al cliente (regla dura #7).
                raise HTTPException(
                    status_code=500,
                    detail="Error interno al procesar la referencia biometrica.",
                )

            return VerificarReferenciaOut(
                distancia=resultado.distancia,
                es_match=resultado.es_match,
                umbral=resultado.umbral,
            )

        # GET /biometria/referencia/estado — auth estudiante
        @router.get(
            "/biometria/referencia/estado",
            response_model=EstadoReferenciaOut,
            summary="Estado de referencia biometrica del usuario autenticado",
            description=(
                "Devuelve si el usuario tiene un embedding de referencia vigente. "
                "Solo el booleano; NUNCA el embedding ni el referencia_id "
                "(Ley 25.326, regla dura #7). "
                "Usar este endpoint para el gate de enrollment en el frontend "
                "antes de intentar la verificacion."
            ),
        )
        async def estado_referencia(
            db: Annotated[AsyncSession, Depends(get_db)],
            principal: Annotated[AuthenticatedPrincipal, Depends(require_estudiante)],
        ) -> EstadoReferenciaOut:
            """Informa si el usuario tiene embedding de referencia vigente.

            - 200: estado consultado (tiene_referencia_vigente=true/false).
            - 401: sin Bearer / token invalido.
            - 403: rol incorrecto.
            """
            if not principal.subject:
                raise HTTPException(
                    status_code=401,
                    detail="Token no porta un subject (sub) valido.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            service = EstadoReferenciaService(session=db)
            vigente = await service.tiene_referencia_vigente(principal.subject)
            return EstadoReferenciaOut(tiene_referencia_vigente=vigente)

    return router
