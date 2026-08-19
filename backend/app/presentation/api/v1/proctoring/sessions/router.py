"""Router de sesiones de proctoring activeexam.

POST /sessions → 201
GET  /sessions → 200
GET  /sessions/{id} → 200/404

Sin auth (D7 — alcance demo). La session_factory y el db_dependency se
inyectan desde el router padre para evitar acoplar este router a ActiveExamSettings.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.acciones import AccionAuditoria, ModuloAuditoria
from app.application.audit.service import registrar
from app.application.proctoring import observacion_service, session_service
from app.application.proctoring.auto_finalizacion import auto_finalizar_si_vencida
from app.application.proctoring.enforcement import (
    FueraDeVentanaError,
    IntentosAgotadosError,
    NoInscriptoError,
    TiempoAgotadoError,
    verificar_enforcement,
    verificar_inscripcion,
    verificar_plazo,
)
from app.application.proctoring.finalizar_con_writeback import (
    finalizar_sesion_con_writeback,
)
from app.application.proctoring.scoring import (
    calcular_score,
    desactivados_de_snapshot,
    eventos_en_pausa_autorizada,
    nivel_riesgo as _nivel_riesgo_de_score,
    pesos_de_snapshot,
    umbral_de_snapshot,
)
from app.application.moodle.grade_calculator import RespuestaAlumno, calcular_nota_academica
from app.application.moodle.writeback_service import MoodleWritebackService
from app.domain.auth.authorization import autorizar_supervision_vivo_sobre_sesion
from app.domain.auth.errors import ForbiddenError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.persistence.models.moodle_writeback import RespuestaAlumnoModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.moodle_writeback import (
    RespuestaAlumnoRepository,
)
from app.presentation.api.v1.proctoring.sessions.schemas import (
    BiometriaDetalle,
    CerrarForzadoIn,
    CerrarForzadoOut,
    CrearSesionIn,
    CrearSesionOut,
    EventoDetalle,
    ExamenConSesionesOut,
    FinalizarSesionOut,
    ListarRespuestasOut,
    ObservacionIn,
    ObservacionOut,
    RegistroSesionesOut,
    RespuestaGuardadaOut,
    SesionDetalle,
    SesionResumen,
    SubmitRespuestasIn,
    SubmitRespuestasOut,
)

_NIVELES_RIESGO_VALIDOS = frozenset({"bajo", "medio", "alto"})


def _principal_es_dueno(
    sesion: ProctoringSessionModel, principal: AuthenticatedPrincipal
) -> bool:
    """True si la sesion pertenece al principal autenticado (H1, IDOR).

    Los endpoints de respuestas/finalizar son del ALUMNO: solo el dueno de la
    sesion puede operarla. La identidad del alumno se persiste server-side al
    CREAR la sesion (``alumno_idnumber``/``alumno_email`` desde el JWT), por lo
    que aca se compara contra el principal del request.

    - Coincide por ``username`` O por ``email`` → es el dueno.
    - Sesion SIN identidad almacenada (legacy/modo 'test' previo a la persistencia
      de identidad) → se permite: no hay a quien atribuirla y no expone notas de
      nadie. Toda sesion nueva guarda identidad, asi que este caso no aplica al
      flujo normal de examen.
    """
    idn = sesion.alumno_idnumber
    email = sesion.alumno_email
    if not idn and not email:
        return True
    if idn and principal.username and idn == principal.username:
        return True
    if email and principal.email and email == principal.email:
        return True
    return False


async def _pesos_vivos_por_tipo(db: AsyncSession) -> dict[str, int] | None:
    """Lee los pesos vivos por tipo de evento desde evento_score_config (activos).

    Devuelve None si la tabla no esta disponible (degradacion graceful, RN-GLB-03):
    en ese caso calcular_score cae al fallback por severidad. Cierra GAP #1
    (consumo server-side de la config, no constantes hardcodeadas)."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.transactional import (
        EventoScoreConfigModel,
    )

    try:
        result = await db.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
            ).where(EventoScoreConfigModel.activo.is_(True))
        )
        return {row.tipo_evento: row.peso for row in result.all()}
    except Exception:  # noqa: BLE001 — degradacion: sin config, fallback por severidad
        return None


async def _umbral_vivo(db: AsyncSession) -> int:
    """Umbral de cola de revision VIVO (``configuracion_sistema.umbral_cola_revision``).

    Fallback cuando una sesion no tiene ``config_snapshot`` (pre-migracion 0083 o
    config no disponible al crearla) — ver ``umbral_de_snapshot``. Mismo criterio
    que ``ProctoringRepository._umbral_vivo`` (listados); el detalle lo necesita
    aparte porque no pasa por ``_armar_resumenes``."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
    )

    try:
        result = await db.execute(select(ConfiguracionSistemaModel.umbral_cola_revision))
        val = result.scalars().first()
    except Exception:  # noqa: BLE001 — degradacion: sin config, piso de producto
        return 70
    return int(val) if val is not None else 70


async def _tipos_desactivados(db: AsyncSession) -> frozenset[str]:
    """Tipos con fila en evento_score_config pero ``activo=False`` (pesan 0).

    Apagado != desconocido: el apagado lo decidio el admin y vale 0; el tipo sin
    fila degrada por severidad (RN-GLB-03). Sin esta lista los dos se veian igual.
    Set vacio si la tabla no esta disponible (no se apaga nada)."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.transactional import (
        EventoScoreConfigModel,
    )

    try:
        result = await db.execute(
            select(EventoScoreConfigModel.tipo_evento).where(
                EventoScoreConfigModel.activo.is_(False)
            )
        )
        return frozenset(result.scalars().all())
    except Exception:  # noqa: BLE001 — sin config, no se apaga nada
        return frozenset()


async def _ventanas_pausa_aprobada(db: AsyncSession, session_id: str) -> list:
    """Ventanas de pausa APROBADA de la sesion (estados 'aprobada' y 'finalizada').

    Devuelve filas con estado/inicio_en/fin_en que el helper puro
    ``eventos_en_pausa_autorizada`` usa para contextualizar el score (C-15 6.4).
    Si la tabla no esta disponible (degradacion graceful) devuelve lista vacia:
    el score se calcula sin exclusiones."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.chat_pausa import PausaAutorizadaModel

    try:
        result = await db.execute(
            select(PausaAutorizadaModel).where(
                PausaAutorizadaModel.session_id == session_id,
                PausaAutorizadaModel.estado.in_(("aprobada", "finalizada")),
            )
        )
        return list(result.scalars().all())
    except Exception:  # noqa: BLE001 — sin tabla de pausas, no se excluye nada
        return []


def create_sessions_router(
    get_db,
    *,
    require_autenticado,
    require_supervision_vivo,
    require_admin=None,
    writeback_svc: MoodleWritebackService | None = None,
    cipher=None,
) -> APIRouter:
    """Factory del router de sesiones. Recibe la dependencia de DB inyectada.

    Guards de auth/RBAC (endurecimiento por rol — los inyecta el router padre):
      - ``require_autenticado``: cualquier token valido (flujo del alumno).
      - ``require_supervision_vivo``: vista de supervision (lista/detalle de sesiones).
      - ``require_admin`` (C-76 tarea 20.1): admin-only, para el DELETE acotado a
        sesiones ``modo='test'``.

    DELETE /sessions/{session_id}: SOLO admin_sistema, y SOLO si la sesion es
    ``modo='test'`` (diagnostico, sin examen real). Las sesiones ``modo='examen'``
    (evidencia academica real) siguen PERMANENTEMENTE protegidas — regla dura
    #6/#7, cadena de custodia (c-76 tarea 16). No hay excepcion, ni siquiera admin.
    """
    router = APIRouter()

    @router.post(
        "/sessions",
        status_code=http_status.HTTP_201_CREATED,
        response_model=CrearSesionOut,
        summary="Crear sesion de proctoring",
    )
    async def crear_sesion(
        body: CrearSesionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> CrearSesionOut:
        """Crea una nueva sesion de proctoring activeexam.

        C-69 (backstop server-side): si la sesion se vincula a un examen
        (``examen_contenido_id``), se ENFORCEA la ventana de rendicion
        (apertura/cierre) y los intentos permitidos contra ``examen_contenido``,
        con la hora del servidor. El cliente ya gatea "Rendir" pero es un sensor
        no confiable (regla dura #6); esto es el backstop duro. Sin
        ``examen_contenido_id`` (modo 'test') NO se aplica enforcement.

        La identidad del alumno (username/email del JWT) se persiste SIEMPRE
        en la fila — el enforcement de intentos la usa para contar las rendiciones.
        """
        from datetime import datetime, timezone

        if body.examen_contenido_id is not None:
            try:
                await verificar_enforcement(
                    db,
                    examen_contenido_id=body.examen_contenido_id,
                    alumno_idnumber=principal.username,
                    ahora=datetime.now(timezone.utc),
                )
            except FueraDeVentanaError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "fuera_de_ventana",
                        "mensaje": exc.mensaje,
                        "apertura": exc.apertura.isoformat() if exc.apertura else None,
                        "cierre": exc.cierre.isoformat() if exc.cierre else None,
                    },
                ) from exc
            except IntentosAgotadosError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail={
                        "error": "intentos_agotados",
                        "mensaje": exc.mensaje,
                        "intentos_permitidos": exc.intentos_permitidos,
                        "rendidos": exc.rendidos,
                    },
                ) from exc

            # Gate de inscripción (C-71): backstop server-side — el alumno debe estar
            # inscripto en la comisión del examen para poder crear la sesión.
            try:
                await verificar_inscripcion(
                    db,
                    examen_contenido_id=body.examen_contenido_id,
                    alumno_idnumber=principal.username,
                )
            except NoInscriptoError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": "no_inscripto", "mensaje": exc.mensaje},
                ) from exc

        try:
            sesion = await session_service.crear_o_reanudar_sesion(
                db=db,
                modo=body.modo,
                exam_id=body.exam_id,
                etiqueta=body.etiqueta,
                examen_contenido_id=body.examen_contenido_id,
                alumno_idnumber=principal.username or None,
                alumno_email=principal.email or None,
            )
        except session_service.ConfigSnapshotNoDisponibleError as exc:
            # migration 0083: nunca se crea una sesion sin foto de config — sin
            # ella, un cambio posterior podria evaluar retroactivamente eventos
            # que el alumno vio con otro valor en pantalla. 503: reintentable,
            # no es un error del alumno ni de su pedido.
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "config_no_disponible",
                    "mensaje": "No se pudo iniciar el examen: la configuración del sistema no está disponible en este momento. Reintentá en unos segundos.",
                },
            ) from exc
        # Auto-finalización lazy (C-72 §4, H-3): si el alumno "vuelve" a una sesión
        # cuyo deadline ya venció (aunque la ventana siga abierta), se cierra sola y
        # se puntúa con lo respondido. No puede seguir rindiendo una sesión vencida.
        await auto_finalizar_si_vencida(db, sesion, writeback_svc=writeback_svc)
        return CrearSesionOut(
            id=sesion.id,
            creada_en=sesion.creada_en,
            examen_contenido_id=sesion.examen_contenido_id,
        )

    @router.get(
        "/sessions",
        response_model=list[SesionResumen],
        summary="Listar sesiones con score y discrepancias",
    )
    async def listar_sesiones(
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_supervision_vivo)],
    ) -> list[SesionResumen]:
        """Lista las sesiones con total_eventos, total_discrepancias y score.

        C-76 bloque 8 (D2): el TUTOR ve SOLO las sesiones de examenes cuya comision
        tiene a su usuario como docente a cargo (asignar_docente, C-73 §9).
        COORDINADOR/ADMIN_SISTEMA son de alcance institucional (global) — REVISOR
        fue eliminado del dominio (c-76) y el COORDINADOR absorbio su alcance.
        """
        sesiones = await session_service.listar_sesiones(db)
        if not principal.tiene_algun_rol({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}):
            sesiones = [s for s in sesiones if s.docente_id == principal.subject]
        return [
            SesionResumen(
                id=s.id,
                modo=s.modo,
                exam_id=s.exam_id,
                etiqueta=s.etiqueta,
                creada_en=s.creada_en,
                finalizada_en=s.finalizada_en,
                ultimo_evento_en=s.ultimo_evento_en,
                total_eventos=s.total_eventos,
                total_discrepancias=s.total_discrepancias,
                score=s.score,
                umbral_cola_revision_efectivo=s.umbral_cola_revision_efectivo,
                examen_contenido_id=s.examen_contenido_id,
                examen_titulo=s.examen_titulo,
                comision_nombre=s.comision_nombre,
                materia_nombre=s.materia_nombre,
            )
            for s in sesiones
        ]

    # C-76 tarea 17: Registro de sesiones — tabla con paginacion real + filtros
    # server-side (alumno, examen, rango de fecha, nivel de riesgo). Registrado
    # ANTES de "/sessions/{session_id}" para que "registro" no sea capturado como
    # session_id (FastAPI matchea por orden de registro).
    @router.get(
        "/sessions/registro",
        response_model=RegistroSesionesOut,
        summary="Registro de sesiones finalizadas: paginado + filtros (C-76 tarea 17)",
    )
    async def listar_registro_sesiones(
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_supervision_vivo)],
        q: str | None = None,
        exam_id: str | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        nivel_riesgo: str | None = None,
        materia_id: str | None = None,
        comision_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> RegistroSesionesOut:
        """Registro de sesiones FINALIZADAS: tabla paginada con filtros server-side.

        - ``q``: busqueda por alumno (idnumber/email/nombre/apellido).
        - ``exam_id``: filtra por ``examen_contenido_id`` (catalogo: GET
          /sessions/registro/examenes — nunca hardcodeado en el frontend).
        - ``fecha_desde``/``fecha_hasta``: rango sobre ``finalizada_en``.
        - ``nivel_riesgo``: 'bajo' | 'medio' | 'alto', derivado del score con el
          MISMO umbral que la Cola de revision (``umbral_cola_revision`` vivo) —
          no un umbral reinventado.
        - ``materia_id``/``comision_id`` (C-76 tarea 20.3): filtro en cascada
          Materia -> Comision (mismo patron que Notas).

        Mismo scoping por comision que el resto del panel (C-76 bloque 8, D2): el
        TUTOR ve solo las sesiones de examenes cuya comision lo tiene como docente
        a cargo; COORDINADOR/ADMIN_SISTEMA son de alcance institucional.
        """
        if nivel_riesgo is not None and nivel_riesgo not in _NIVELES_RIESGO_VALIDOS:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "nivel_riesgo_invalido",
                    "mensaje": f"nivel_riesgo debe ser uno de {sorted(_NIVELES_RIESGO_VALIDOS)}",
                },
            )

        sesiones = await session_service.listar_sesiones_finalizadas(
            db,
            q=q,
            exam_id=exam_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            materia_id=materia_id,
            comision_id=comision_id,
        )
        if not principal.tiene_algun_rol({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}):
            sesiones = [s for s in sesiones if s.docente_id == principal.subject]
        # migration 0083: el umbral es POR SESION (`umbral_cola_revision_efectivo`,
        # de su config_snapshot o el vivo como fallback) — ya NO uno global aplicado
        # a todas por igual, para que un cambio de config no reclasifique
        # retroactivamente sesiones que arrancaron con otro umbral.
        if nivel_riesgo:
            sesiones = [
                s
                for s in sesiones
                if _nivel_riesgo_de_score(s.score, s.umbral_cola_revision_efectivo)
                == nivel_riesgo
            ]

        total = len(sesiones)
        pagina_actual = max(1, page)
        tamano_pagina = max(1, page_size)
        inicio = (pagina_actual - 1) * tamano_pagina
        items_pagina = sesiones[inicio : inicio + tamano_pagina]

        # Agregados sobre el TOTAL filtrado (19.3/20.4) — sobre `sesiones` (ya
        # filtrado por q/exam_id/fecha/nivel_riesgo/materia/comision/scoping),
        # ANTES de recortar por pagina. Reusa `_nivel_riesgo_de_score`
        # (scoring.py), el umbral EFECTIVO de cada sesion (mismo criterio que el
        # filtro y que la Cola de revision).
        riesgo_bajo = riesgo_medio = riesgo_alto = 0
        en_cola_revision = 0
        for s in sesiones:
            nivel = _nivel_riesgo_de_score(s.score, s.umbral_cola_revision_efectivo)
            if nivel == "alto":
                riesgo_alto += 1
            elif nivel == "medio":
                riesgo_medio += 1
            else:
                riesgo_bajo += 1
            if s.score >= s.umbral_cola_revision_efectivo:
                en_cola_revision += 1

        return RegistroSesionesOut(
            riesgo_bajo=riesgo_bajo,
            riesgo_medio=riesgo_medio,
            riesgo_alto=riesgo_alto,
            en_cola_revision=en_cola_revision,
            items=[
                SesionResumen(
                    id=s.id,
                    modo=s.modo,
                    exam_id=s.exam_id,
                    etiqueta=s.etiqueta,
                    creada_en=s.creada_en,
                    finalizada_en=s.finalizada_en,
                    ultimo_evento_en=s.ultimo_evento_en,
                    total_eventos=s.total_eventos,
                    total_discrepancias=s.total_discrepancias,
                    score=s.score,
                    umbral_cola_revision_efectivo=s.umbral_cola_revision_efectivo,
                    examen_contenido_id=s.examen_contenido_id,
                    examen_titulo=s.examen_titulo,
                    comision_nombre=s.comision_nombre,
                    materia_nombre=s.materia_nombre,
                    alumno_idnumber=s.alumno_idnumber,
                    alumno_email=s.alumno_email,
                    alumno_nombre=s.alumno_nombre,
                )
                for s in items_pagina
            ],
            total=total,
            page=pagina_actual,
            page_size=tamano_pagina,
        )

    @router.get(
        "/sessions/registro/examenes",
        response_model=list[ExamenConSesionesOut],
        summary="Catalogo de examenes con sesiones (filtro del Registro, C-76 tarea 17.2)",
    )
    async def listar_examenes_con_sesiones(
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_supervision_vivo)],
    ) -> list[ExamenConSesionesOut]:
        """Examenes con AL MENOS una sesion finalizada — opciones del <select> de
        "Examen" del Registro de sesiones. El frontend NUNCA hardcodea esta lista.

        Mismo scoping por comision que ``listar_registro_sesiones``: el TUTOR ve
        solo los examenes de SU comision.
        """
        if principal.tiene_algun_rol({Rol.COORDINADOR, Rol.ADMIN_SISTEMA}):
            catalogo = await session_service.catalogo_examenes_con_sesiones(db)
        else:
            # Sin rol institucional: acotar al alcance del TUTOR reusando el mismo
            # filtro por docente que ya aplica el registro paginado (una sola fuente
            # de verdad para "que examenes ve este tutor").
            sesiones = await session_service.listar_sesiones_finalizadas(db)
            vistos: dict[str, str] = {}
            for s in sesiones:
                if s.docente_id != principal.subject or not s.examen_contenido_id:
                    continue
                vistos.setdefault(s.examen_contenido_id, s.examen_titulo or s.examen_contenido_id)
            catalogo = sorted(vistos.items(), key=lambda kv: kv[1])
        return [ExamenConSesionesOut(id=eid, titulo=titulo) for eid, titulo in catalogo]

    @router.get(
        "/sessions/{session_id}",
        response_model=SesionDetalle,
        summary="Detalle de sesion para revision del tutor/coordinador",
    )
    async def obtener_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_supervision_vivo)],
    ) -> SesionDetalle:
        """Detalle completo de una sesion con eventos y biometria (vista del tutor/coordinador).

        C-76 bloque 8 (D2): el TUTOR solo accede al detalle de sesiones de SU
        comision (403 fuera de ella); COORDINADOR/ADMIN_SISTEMA son globales
        (REVISOR fue eliminado del dominio en c-76)."""
        sesion = await session_service.detalle_sesion(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        docente_id = await session_service.docente_id_de_sesion(db, session_id)
        try:
            autorizar_supervision_vivo_sobre_sesion(principal, docente_id)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": "sesion_ajena", "mensaje": str(exc)},
            ) from exc

        # migration 0083: pesos/desactivados de la FOTO tomada al crear esta
        # sesion (``sesion.config_snapshot``), no de la config viva — un cambio
        # de pesos posterior no debe alterar el score de una sesion que ya
        # arranco. Sin foto (pre-migracion o degradacion al crear), cae a los
        # pesos vivos; si tampoco hay config disponible, calcular_score cae al
        # fallback por severidad (degradacion graceful, RN-GLB-03). L2.5: el
        # score solo prioriza la revision humana.
        pesos_vivos = await _pesos_vivos_por_tipo(db)
        desactivados_vivos = await _tipos_desactivados(db)
        pesos_por_tipo = pesos_de_snapshot(sesion.config_snapshot, pesos_vivos=pesos_vivos)
        desactivados = desactivados_de_snapshot(
            sesion.config_snapshot, desactivados_vivos=desactivados_vivos
        )
        umbral_vivo = await _umbral_vivo(db)
        umbral_efectivo = umbral_de_snapshot(sesion.config_snapshot, umbral_vivo=umbral_vivo)

        # C-15 (6.4): contextualizacion del score. Los eventos que caen dentro de
        # una ventana de pausa AUTORIZADA (aprobada/finalizada) se EXCLUYEN del
        # puntaje (L2.5: no se borran ni se ocultan, solo se marcan). El detalle
        # del tutor/coordinador reporta el score SIN esos eventos.
        ventanas = await _ventanas_pausa_aprobada(db, session_id)
        ids_en_pausa = eventos_en_pausa_autorizada(sesion.eventos, ventanas)
        eventos_para_score = [
            e for e in sesion.eventos if e.id not in ids_en_pausa
        ]
        score = calcular_score(
            eventos_para_score,
            pesos_por_tipo=pesos_por_tipo,
            tipos_desactivados=desactivados,
        )

        eventos = [
            EventoDetalle(
                id=e.id,
                tipo=e.tipo,
                severidad=e.severidad,
                ts_cliente=e.ts_cliente,
                ts_backend=e.ts_backend,
                payload=e.payload,
                # Descifrado at-rest de la evidencia (Ley 25.326). Sin cipher o si el
                # registro es legacy en claro, decrypt lo devuelve tal cual.
                screenshot_base64=(
                    cipher.decrypt(e.screenshot_b64) if cipher is not None else e.screenshot_b64
                ),
                screenshot_sha256=e.screenshot_sha256,
                face_count_cliente=e.face_count_cliente,
                face_count_servidor=e.face_count_servidor,
                veredicto_reinferencia=e.veredicto_reinferencia,
                en_pausa_autorizada=e.id in ids_en_pausa,
            )
            for e in sesion.eventos
        ]

        biometria = None
        if sesion.biometria is not None:
            bio = sesion.biometria
            biometria = BiometriaDetalle(
                liveness_ok=bio.liveness_ok,
                retos_resueltos=bio.retos_resueltos,
                resultado=bio.resultado,
                registrada_en=bio.registrada_en,
            )

        examen_titulo, comision_nombre, materia_nombre = (
            await session_service.contexto_academico_de_examen(
                db, sesion.examen_contenido_id
            )
        )
        alumno_nombre = await session_service.nombre_alumno_de_sesion(
            db, sesion.alumno_idnumber, sesion.alumno_email
        )

        return SesionDetalle(
            id=sesion.id,
            modo=sesion.modo,
            etiqueta=sesion.etiqueta,
            examen_contenido_id=sesion.examen_contenido_id,
            examen_titulo=examen_titulo,
            comision_nombre=comision_nombre,
            materia_nombre=materia_nombre,
            alumno_nombre=alumno_nombre,
            alumno_idnumber=sesion.alumno_idnumber,
            alumno_email=sesion.alumno_email,
            creada_en=sesion.creada_en,
            finalizada_en=sesion.finalizada_en,
            score=score,
            umbral_cola_revision_efectivo=umbral_efectivo,
            eventos=eventos,
            biometria=biometria,
            cierre_forzado_en=sesion.cierre_forzado_en,
            cierre_forzado_motivo=sesion.cierre_forzado_motivo,
            config_snapshot=sesion.config_snapshot,
        )

    @router.post(
        "/sessions/{session_id}/respuestas",
        status_code=http_status.HTTP_201_CREATED,
        response_model=SubmitRespuestasOut,
        summary="Enviar respuestas del alumno (para cálculo de nota server-side, C-69)",
        dependencies=[Depends(require_autenticado)],
    )
    async def submit_respuestas(
        session_id: str,
        body: SubmitRespuestasIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> SubmitRespuestasOut:
        """Persiste las respuestas del alumno para calcular la nota server-side.

        D8: la corrección y el write-back los origina el backend, nunca el cliente.
        D3: la opción correcta NUNCA viaja al cliente — sólo se usa acá server-side.
        Idempotente por (session_id, pregunta_id): re-enviar sobreescribe la respuesta.

        Seguridad:
        - H1 (IDOR): 404 si la sesión no existe o no es del alumno autenticado.
        - H2 (regrade): 409 si la sesión ya está finalizada — no se pueden cambiar
          las respuestas de un intento ya entregado.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        # 404 (no 403) tanto si no existe como si no es del alumno: no revelar la
        # existencia de sesiones ajenas (no dar un oráculo de session_ids).
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        if sesion_model.finalizada_en is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "error": "sesion_finalizada",
                    "mensaje": "No se pueden modificar las respuestas de una sesión ya finalizada.",
                },
            )
        # Enforcement de PLAZO (C-72 §2, H-1/H-2): revalidar el reloj server-side en
        # cada envío. El cliente es sensor no confiable (regla #6): sin esto la sesión
        # abierta acepta respuestas fuera de tiempo / con la ventana cerrada.
        if sesion_model.examen_contenido_id is not None:
            from datetime import datetime, timezone

            try:
                await verificar_plazo(
                    db,
                    examen_contenido_id=sesion_model.examen_contenido_id,
                    creada_en=sesion_model.creada_en,
                    ahora=datetime.now(timezone.utc),
                )
            except TiempoAgotadoError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail={"error": "tiempo_agotado", "mensaje": exc.mensaje},
                ) from exc
        repo = RespuestaAlumnoRepository(db)
        n = await repo.guardar_respuestas(
            session_id=session_id,
            respuestas=[
                {"pregunta_id": r.pregunta_id, "opcion_elegida_id": r.opcion_elegida_id}
                for r in body.respuestas
                if r.opcion_elegida_id is not None
            ],
        )
        # Cloze/ddwtos (C-74 §6): un item de respuesta_cloze trae VARIOS blanks —
        # se aplana a una fila por blank para el upsert (session_id, blank_id).
        n += await repo.guardar_respuestas_cloze(
            session_id=session_id,
            respuestas=[
                {"pregunta_id": r.pregunta_id, "blank_id": blank_id, "valor": valor}
                for r in body.respuestas
                if r.respuesta_cloze is not None
                for blank_id, valor in r.respuesta_cloze.items()
            ],
        )
        # El repo hace flush; sin commit las respuestas se pierden al cerrar la
        # sesión de DB del request (get_db no auto-commitea).
        await db.commit()
        return SubmitRespuestasOut(session_id=session_id, respuestas_guardadas=n)

    @router.get(
        "/sessions/{session_id}/respuestas",
        response_model=ListarRespuestasOut,
        summary="Obtener las respuestas ya guardadas de la sesion (reanudacion, dueño)",
    )
    async def obtener_respuestas(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> ListarRespuestasOut:
        """Devuelve las respuestas ya persistidas de la sesion (vuln reload/restart).

        Al reanudar una sesion ACTIVA (creada antes de un F5), el cliente necesita
        recuperar lo que ya habia contestado para no reiniciar el intento con las
        respuestas en blanco. Gateado al DUEÑO de la sesion (mismo criterio de
        ``_principal_es_dueno`` que ``submit_respuestas``/``finalizar_sesion``):
        404 (no 403) tanto si no existe como si no es del alumno autenticado, para
        no revelar la existencia de sesiones ajenas.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        repo = RespuestaAlumnoRepository(db)
        rows = await repo.listar_por_sesion(session_id)
        cloze_rows = await repo.listar_cloze_por_sesion(session_id)

        # Agrupar los blanks cloze por pregunta_id: N filas (una por blank) → un
        # item por pregunta con su dict {blank_id: valor} completo.
        cloze_por_pregunta: dict[str, dict[str, str]] = {}
        for cr in cloze_rows:
            cloze_por_pregunta.setdefault(cr.pregunta_id, {})[cr.blank_id] = cr.valor

        respuestas = [
            RespuestaGuardadaOut(pregunta_id=r.pregunta_id, opcion_elegida_id=r.opcion_elegida_id)
            for r in rows
        ] + [
            RespuestaGuardadaOut(pregunta_id=pregunta_id, respuesta_cloze=blanks)
            for pregunta_id, blanks in cloze_por_pregunta.items()
        ]
        return ListarRespuestasOut(session_id=session_id, respuestas=respuestas)

    @router.patch(
        "/sessions/{session_id}/finalizar",
        response_model=FinalizarSesionOut,
        summary="Finalizar sesion de proctoring (idempotente)",
    )
    async def finalizar_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> FinalizarSesionOut:
        """Setea finalizada_en = now() si es NULL.

        Idempotente: si ya estaba finalizada, responde 200 sin modificar.
        404 si la sesion no existe.
        C-69 (admin-sync): si la sesión tiene examen_contenido vinculado, la nota se
        CALCULA y PERSISTE como 'pendiente'. NO se auto-envía a Moodle — el envío es
        manual por el admin (POST /exam-content/{examen_id}/sincronizar-moodle). La
        nota se calcula SIEMPRE que haya examen vinculado, esté o no Moodle configurado
        (así el admin la ve en los resultados aunque Moodle no exista todavía).

        Seguridad:
        - H1 (IDOR): 404 si la sesión no existe o no es del alumno autenticado.
        - H2 (regrade): si la sesión YA estaba finalizada, NO se recalcula ni
          re-persiste la nota (idempotente puro) — así no se puede subir la nota
          re-finalizando un intento ya entregado.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )

        ya_finalizada = sesion_model.finalizada_en is not None

        # H2: la nota se calcula SOLO en la primera finalización. Re-finalizar una
        # sesión ya finalizada es idempotente y NO recalcula (nota=None → el
        # writeback no toca el estado persistido).
        nota: float | None = None
        if not ya_finalizada and sesion_model.examen_contenido_id:
            resp_rows = await db.execute(
                select(RespuestaAlumnoModel).where(
                    RespuestaAlumnoModel.session_id == session_id
                )
            )
            respuestas = [
                RespuestaAlumno(
                    pregunta_id=r.pregunta_id,
                    opcion_elegida_id=r.opcion_elegida_id,
                )
                for r in resp_rows.scalars().all()
            ]
            # Cloze/ddwtos (C-74 §6): agrupar los blanks por pregunta_id — cada
            # pregunta cloze es UNA RespuestaAlumno con su dict {blank_id: valor}.
            cloze_rows = await RespuestaAlumnoRepository(db).listar_cloze_por_sesion(session_id)
            cloze_por_pregunta: dict[str, dict[str, str]] = {}
            for cr in cloze_rows:
                cloze_por_pregunta.setdefault(cr.pregunta_id, {})[cr.blank_id] = cr.valor
            respuestas.extend(
                RespuestaAlumno(pregunta_id=pregunta_id, respuesta_cloze=blanks)
                for pregunta_id, blanks in cloze_por_pregunta.items()
            )
            nota = await calcular_nota_academica(
                db=db,
                examen_contenido_id=sesion_model.examen_contenido_id,
                respuestas=respuestas,
            )

        # Identidad para el write-back: la del DUEÑO de la sesión (persistida al
        # crearla), con fallback al principal. Antes se usaba la identidad del que
        # finaliza → atribución incorrecta de la nota (H1).
        alumno_idnumber = sesion_model.alumno_idnumber or principal.username or ""
        alumno_email = sesion_model.alumno_email or principal.email or ""

        sesion = await finalizar_sesion_con_writeback(
            db=db,
            session_id=session_id,
            writeback_svc=writeback_svc,
            nota=nota,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
        )
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return FinalizarSesionOut(id=sesion.id, finalizada_en=sesion.finalizada_en)

    # C-15 (3.2): observaciones del tutor (insumo de la revision humana C-16).
    @router.post(
        "/sessions/{session_id}/observaciones",
        status_code=http_status.HTTP_201_CREATED,
        response_model=ObservacionOut,
        summary="Registrar observacion del tutor (insumo C-16)",
        dependencies=[Depends(require_supervision_vivo)],
    )
    async def crear_observacion(
        session_id: str,
        body: ObservacionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> ObservacionOut:
        """Persiste una observacion del tutor sobre la sesion. 404 si no existe."""
        obs = await observacion_service.crear_observacion(
            db, session_id=session_id, texto=body.texto, tutor_actor=body.tutor_actor
        )
        if obs is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return ObservacionOut(
            id=obs.id,
            texto=obs.texto,
            tutor_actor=obs.tutor_actor,
            creada_en=obs.creada_en,
        )

    @router.get(
        "/sessions/{session_id}/observaciones",
        response_model=list[ObservacionOut],
        summary="Listar observaciones del tutor de la sesion",
        dependencies=[Depends(require_supervision_vivo)],
    )
    async def listar_observaciones(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[ObservacionOut]:
        """Lista observaciones asc por creada_en. 404 si la sesion no existe."""
        obs = await observacion_service.listar_observaciones(db, session_id)
        if obs is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return [
            ObservacionOut(
                id=o.id,
                texto=o.texto,
                tutor_actor=o.tutor_actor,
                creada_en=o.creada_en,
            )
            for o in obs
        ]

    # C-15 (3.3): cierre FORZADO de la sesion por el tutor/coordinador. Operativo, NO
    # disciplinario (regla dura #5: el sistema nunca sanciona; el veredicto es
    # HUMANO en C-16). El audit trail vive en la propia fila (cierre_forzado_*).
    @router.patch(
        "/sessions/{session_id}/cerrar-forzado",
        response_model=CerrarForzadoOut,
        summary="Cierre forzado de sesion por el tutor/coordinador (operativo, auditado)",
        dependencies=[Depends(require_supervision_vivo)],
    )
    async def cerrar_forzado(
        session_id: str,
        body: CerrarForzadoIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> CerrarForzadoOut:
        """Fuerza el cierre: setea finalizada_en + cierre_forzado_*.

        Idempotente. 404 si la sesion no existe.
        """
        sesion = await session_service.cerrar_forzado(
            db, session_id, motivo=body.motivo, tutor_actor=body.tutor_actor
        )
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return CerrarForzadoOut(
            id=sesion.id,
            finalizada_en=sesion.finalizada_en,
            cierre_forzado_en=sesion.cierre_forzado_en,
            cierre_forzado_por=sesion.cierre_forzado_por,
            cierre_forzado_motivo=sesion.cierre_forzado_motivo,
        )

    if require_admin is not None:

        @router.delete(
            "/sessions/{session_id}",
            status_code=http_status.HTTP_204_NO_CONTENT,
            summary="Elimina una sesion modo='test' (diagnostico) — admin-only (C-76 tarea 20.1)",
        )
        async def eliminar_sesion_test(
            session_id: str,
            request: Request,
            db: Annotated[AsyncSession, Depends(get_db)],
            principal: Annotated[AuthenticatedPrincipal, Depends(require_admin)],
        ) -> None:
            """Elimina una sesion de DIAGNOSTICO (``modo='test'``, sin examen real).

            409 si la sesion es ``modo='examen'`` (evidencia academica real — la
            proteccion permanente de la tarea 16 se mantiene INTACTA, sin
            excepciones). 404 si no existe. Auditado bajo ``ModuloAuditoria.SESIONES``
            (cierra el gap de la tarea 20.7: el modulo estaba muerto, sin ningun
            prefijo mapeado en ``modulo_de_accion``).
            """
            resultado = await session_service.eliminar_sesion_test(db, session_id)
            if resultado == "no_encontrada":
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Sesion {session_id!r} no encontrada",
                )
            if resultado == "modo_examen":
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail={
                        "error": "sesion_modo_examen",
                        "mensaje": (
                            "No se puede eliminar: es evidencia academica real "
                            "(cadena de custodia, regla dura #6/#7). Solo las "
                            "sesiones de diagnostico (modo='test') se pueden borrar."
                        ),
                    },
                )
            # Auditoria best-effort en la MISMA sesion de DB (ya committeada la
            # eliminacion arriba): un fallo acá no debe reventar un 204 ya efectivo.
            try:
                await registrar(
                    db,
                    actor=principal.email or principal.username or principal.subject or "admin",
                    accion=AccionAuditoria.SESION_TEST_ELIMINADA,
                    modulo=ModuloAuditoria.SESIONES,
                    entidad_id=session_id,
                    ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    proposito=f"Eliminó la sesión de diagnóstico {session_id}",
                )
                await db.commit()
            except Exception:  # noqa: BLE001 — best-effort, no bloquea el 204 ya efectivo
                pass
            return None

    return router
