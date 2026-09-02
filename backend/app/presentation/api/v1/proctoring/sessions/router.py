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
from app.application.proctoring.captura_almacenada import leer_captura
from app.application.proctoring.prueba_de_staff import es_rendicion_de_prueba
from app.domain.exam_content.perfil_para_rendir import (
    PerfilParaRendir,
    falta_para_rendir,
    puede_rendir,
)
from app.application.proctoring.enforcement import (
    ExamenDadoDeBajaError,
    ExamenEnBorradorError,
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
from app.domain.auth.authorization import (
    autorizar_supervision_vivo_sobre_sesion,
    principal_es_dueno_de_sesion,
)
from app.domain.auth.capabilities import tiene_capacidad
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
    SesionEnCursoOut,
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

    Traduce el modelo ORM a los campos primitivos que espera la funcion pura
    compartida (``domain.auth.authorization``), reusada tambien por los
    routers de eventos/chat/pausas/biometria."""
    return principal_es_dueno_de_sesion(
        principal, sesion.alumno_idnumber, sesion.alumno_email
    )


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


async def _perfil_para_rendir(db: AsyncSession, usuario_id: str) -> PerfilParaRendir:
    """Resuelve las tres condiciones contra la base.

    Mismos repositorios que usa el gate de matriculacion: si la matricula y la
    rendicion preguntaran distinto, una de las dos estaria mal.
    """
    from app.infrastructure.persistence.repositories.exam_content import _es_uuid
    from app.infrastructure.persistence.repositories.biometric_reference import (
        EmbeddingReferenciaRepository,
        FotoReferenciaRepository,
    )
    from app.infrastructure.persistence.repositories.consent_perfil import (
        ConsentimientoPerfilSqlRepository,
    )

    if not _es_uuid(usuario_id):
        # Un `sub` que no es UUID no puede tener perfil, y consultarlo revienta
        # con un 500 de asyncpg donde corresponde un 403 (mismo caso que la
        # guarda de pertenencia).
        return PerfilParaRendir(
            consintio=False, tiene_biometria=False, tiene_foto=False
        )

    consentimiento = await ConsentimientoPerfilSqlRepository(db).vigente(usuario_id)
    return PerfilParaRendir(
        consintio=consentimiento is not None and consentimiento.estado == "otorgado",
        tiene_biometria=(
            await EmbeddingReferenciaRepository(db).obtener_vigente(usuario_id)
        )
        is not None,
        tiene_foto=(await FotoReferenciaRepository(db).obtener_vigente(usuario_id))
        is not None,
    )


async def _pertenece_al_principal(
    db: AsyncSession, principal: AuthenticatedPrincipal, examen_contenido_id: str
) -> bool:
    """Si el examen es de una comision/materia que este principal tiene a cargo.

    Misma pregunta que hace `_exigir_pertenencia` en el router de examenes, y
    contra el mismo repositorio: tutor de su comision, coordinador o profesor de
    su materia. El admin_sistema es de alcance institucional.

    Se usa para decidir si una rendicion del staff es un ENSAYO. No reemplaza a
    ninguna guarda: la inscripcion y el enforcement siguen corriendo para todos
    los demas casos.
    """
    from app.domain.auth.authorization import _ROLES_SIN_LIMITE_DE_PERTENENCIA
    from app.infrastructure.persistence.repositories.exam_content import (
        ComisionSqlRepository,
    )

    if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
        return True
    return await ComisionSqlRepository(db).tiene_pertenencia_sobre_examen(
        principal.subject or "",
        examen_contenido_id,
        es_coordinador=principal.tiene_rol(Rol.COORDINADOR),
        es_profesor=principal.tiene_rol(Rol.PROFESOR),
    )


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

    async def _comision_ids_permitidas(
        db: AsyncSession, principal: AuthenticatedPrincipal
    ) -> set[str] | None:
        """Comisiones que el principal puede ver (N:M, c-79/c-78). ``None`` = sin
        restricción (solo admin_sistema, alcance global).

        - TUTOR: sus comisiones (``comision_tutor``).
        - COORDINADOR: las comisiones de SUS materias (``materia_coordinador``) —
          c-79, ya no es de alcance global.
        - PROFESOR: las comisiones de SUS materias (``materia_profesor``) — c-78.

        El resultado es la UNIÓN de las membresías que el principal tenga: alguien
        con dos roles ve lo de ambos, no lo del primero que matchee. Devolver el
        conjunto vacío es correcto y significativo: ve NADA, no "ve todo".
        """
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        if principal.tiene_rol(Rol.ADMIN_SISTEMA):
            return None
        repo = ComisionSqlRepository(db)
        subject = principal.subject or ""
        permitidas: set[str] = set()
        if principal.tiene_rol(Rol.COORDINADOR):
            permitidas |= set(await repo.comision_ids_a_cargo_coordinador(subject))
        if principal.tiene_rol(Rol.PROFESOR):
            permitidas |= set(await repo.comision_ids_a_cargo_profesor(subject))
        if principal.tiene_rol(Rol.TUTOR) or not permitidas:
            # El tutor suma SIEMPRE sus comisiones. El `or not permitidas` cubre a
            # un principal sin ninguno de los tres roles (no debería llegar acá,
            # pero si llega tiene que quedar acotado, nunca abierto).
            permitidas |= set(await repo.comision_ids_a_cargo(subject))
        return permitidas

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
            # c-78 E-07: el docente probando su propio examen. Le saltea el borrador
            # y la ventana, no la baja logica ni el tope de intentos. Se deriva del
            # rol, NO de un flag del body: el cliente es un sensor no confiable
            # (regla dura #6) y un alumno no puede auto-declararse staff.
            # El staff academico probando SU PROPIO examen (incluye al TUTOR,
            # decision del dueno: no arma el examen pero necesita ver que se toma).
            #
            # Se deriva del ROL + la PERTENENCIA, nunca de un flag del body: el
            # cliente es un sensor no confiable (regla dura #6). Y las dos
            # condiciones hacen falta —con el rol solo, un docente abriria "de
            # prueba" el parcial de otra catedra, y un profesor que ademas cursa
            # otra materia veria su propio parcial marcado como ensayo, sin nota.
            es_examen_propio = await _pertenece_al_principal(
                db, principal, body.examen_contenido_id
            )
            es_prueba_de_staff = es_rendicion_de_prueba(
                list(principal.roles), es_examen_propio=es_examen_propio
            )
            # migración 0105: si el EXAMEN está en modo prueba, la sesión es un
            # ensayo sin importar quién la rinda. Es la vía por la que un alumno
            # de verdad puede probar el examen: recorre su flujo real (consentimiento,
            # foto, biometría) y nada de lo que haga cuenta.
            from app.infrastructure.persistence.models.exam_content import (
                ExamenContenidoModel as _ExamenContenidoModel,
            )

            examen_en_modo_prueba = bool(
                (
                    await db.execute(
                        select(_ExamenContenidoModel.modo_prueba).where(
                            _ExamenContenidoModel.id == body.examen_contenido_id
                        )
                    )
                ).scalar_one_or_none()
            )
            try:
                await verificar_enforcement(
                    db,
                    examen_contenido_id=body.examen_contenido_id,
                    alumno_idnumber=principal.username,
                    ahora=datetime.now(timezone.utc),
                    es_prueba_de_staff=es_prueba_de_staff,
                )
            except ExamenEnBorradorError as exc:
                # 403, no 410: el examen no fue retirado, todavia no se habilito.
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "examen_en_borrador",
                        "mensaje": exc.mensaje,
                    },
                ) from exc
            except ExamenDadoDeBajaError as exc:
                # c-78: 410 Gone, no 403. El recurso EXISTIA y fue retirado; no es
                # un problema de permisos ni de horario, asi que el alumno no gana
                # nada reintentando ni esperando a que abra la ventana.
                raise HTTPException(
                    status_code=http_status.HTTP_410_GONE,
                    detail={
                        "error": "examen_dado_de_baja",
                        "mensaje": exc.mensaje,
                    },
                ) from exc
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

            # Gate de PERFIL: sin consentimiento y sin biometría no se rinde.
            #
            # Vivía solo en la matriculación por código, así que al alumno
            # inscripto desde el panel del docente no lo frenaba nadie: creaba la
            # sesión, veía las preguntas, respondía y finalizaba. Sin
            # consentimiento no se puede hacer proctoring (regla dura
            # #7) y sin referencia biométrica la rendición no prueba quién la hizo.
            #
            # Va acá y no en el onboarding a propósito: el consentimiento y la
            # biometría crean sus propias sesiones (sin examen vinculado) y no
            # pueden quedar bloqueados por sí mismos. Al staff que prueba su
            # examen tampoco se le pide: no es una rendición.
            if not es_prueba_de_staff:
                perfil = await _perfil_para_rendir(db, principal.subject or "")
                if not puede_rendir(perfil):
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "perfil_incompleto",
                            "mensaje": falta_para_rendir(perfil),
                        },
                    )

            # Gate de inscripción (C-71): backstop server-side — el alumno debe estar
            # inscripto en la comisión del examen para poder crear la sesión.
            #
            # No se le pide al staff que prueba: un docente NUNCA está inscripto
            # como alumno de su propia comisión, así que exigírselo hacía imposible
            # probar el examen — que es para lo único que sirve el borrador.
            try:
                if not es_prueba_de_staff:
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
                # Solo cuando hay examen vinculado: sin él no hay nota ni
                # resultados de los que haga falta excluirla.
                es_prueba=bool(body.examen_contenido_id)
                and (es_prueba_de_staff or examen_en_modo_prueba),
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

        C-76 bloque 8 (N:M desde c-79): el TUTOR ve SOLO las sesiones de examenes
        cuya comision lo tiene como tutor (comision_tutor); el COORDINADOR ve las
        de SUS materias asignadas (materia_coordinador) — ya no alcance global.
        Solo ADMIN_SISTEMA sigue siendo institucional.
        """
        sesiones = await session_service.listar_sesiones(db)
        comision_ids = await _comision_ids_permitidas(db, principal)
        if comision_ids is not None:
            sesiones = [s for s in sesiones if s.comision_id in comision_ids]
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
                es_prueba=bool(getattr(s, "es_prueba", False)),
                examen_contenido_id=s.examen_contenido_id,
                examen_titulo=s.examen_titulo,
                comision_nombre=s.comision_nombre,
                materia_nombre=s.materia_nombre,
                # Identidad del alumno, resuelta server-side contra `usuario`. El
                # repositorio ya la traia y esta respuesta la descartaba: los tres
                # campos existian en el schema y nadie los pasaba, asi que salian
                # null y la pantalla caia a `etiqueta`, que la manda el CLIENTE.
                # Con 40 alumnos rindiendo, eso le mostraba al tutor 40 tarjetas
                # con el titulo del examen en vez del nombre de cada persona; y
                # por la regla dura #6 esa etiqueta puede decir cualquier cosa.
                alumno_nombre=s.alumno_nombre,
                alumno_idnumber=s.alumno_idnumber,
                alumno_email=s.alumno_email,
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
        incluir_pruebas: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> RegistroSesionesOut:
        """Registro de sesiones FINALIZADAS: tabla paginada con filtros server-side.

        - ``incluir_pruebas``: por defecto False — los ENSAYOS del docente no se
          listan. Mezclados con las rendiciones reales obligaban a separarlos a
          ojo. En True vuelven a aparecer: se ocultan, no se esconden.
        - ``q``: busqueda por alumno (idnumber/email/nombre/apellido).
        - ``exam_id``: filtra por ``examen_contenido_id`` (catalogo: GET
          /sessions/registro/examenes — nunca hardcodeado en el frontend).
        - ``fecha_desde``/``fecha_hasta``: rango sobre ``finalizada_en``.
        - ``nivel_riesgo``: 'bajo' | 'medio' | 'alto', derivado del score con el
          MISMO umbral que la Cola de revision (``umbral_cola_revision`` vivo) —
          no un umbral reinventado.
        - ``materia_id``/``comision_id`` (C-76 tarea 20.3): filtro en cascada
          Materia -> Comision (mismo patron que Notas).

        Mismo scoping por comision que el resto del panel (C-76 bloque 8, N:M
        desde c-79): el TUTOR ve solo las sesiones de examenes cuya comision lo
        tiene como tutor; el COORDINADOR ve las de SUS materias asignadas; solo
        ADMIN_SISTEMA es de alcance institucional.
        """
        if nivel_riesgo is not None and nivel_riesgo not in _NIVELES_RIESGO_VALIDOS:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "nivel_riesgo_invalido",
                    "mensaje": f"nivel_riesgo debe ser uno de {sorted(_NIVELES_RIESGO_VALIDOS)}",
                },
            )

        # c-78 §11.4: el scoping va EN LA QUERY, no en un filtro de Python sobre
        # todas las sesiones finalizadas de la base. Ademas de ser correcto, evita
        # traer decenas de miles de filas para descartar casi todas.
        comision_ids = await _comision_ids_permitidas(db, principal)
        sesiones = await session_service.listar_sesiones_finalizadas(
            db,
            q=q,
            exam_id=exam_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            materia_id=materia_id,
            comision_id=comision_id,
            comision_ids_permitidas=comision_ids,
            incluir_pruebas=incluir_pruebas,
        )
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
            # F-01 (c-78 D3): "entra a la Cola de revision" exige un examen REAL
            # vinculado, no solo pasar el umbral. Esta tarjeta contaba tambien las
            # sesiones de diagnostico (sin examen) que superaban el umbral, asi que
            # daba un numero mas alto que la propia Cola de revision para el mismo
            # dato. El LISTADO de esta pantalla NO se toca: muestra las de
            # diagnostico a proposito (desde aca se borran) — lo que se corrige es
            # el AGREGADO, para que cuente lo que realmente entra a la cola.
            if (
                s.score >= s.umbral_cola_revision_efectivo
                and s.examen_contenido_id is not None
            ):
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
                    es_prueba=s.es_prueba,
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

        Mismo scoping por comision que ``listar_registro_sesiones`` (N:M desde
        c-79): el TUTOR ve solo los examenes de SUS comisiones; el COORDINADOR,
        los de SUS materias asignadas.
        """
        comision_ids = await _comision_ids_permitidas(db, principal)
        if comision_ids is None:
            catalogo = await session_service.catalogo_examenes_con_sesiones(db)
        else:
            # Acotar al alcance del TUTOR/COORDINADOR reusando el mismo filtro por
            # comisión que ya aplica el registro paginado (una sola fuente de
            # verdad para "que examenes ve este principal").
            sesiones = await session_service.listar_sesiones_finalizadas(db)
            vistos: dict[str, str] = {}
            for s in sesiones:
                if s.comision_id not in comision_ids or not s.examen_contenido_id:
                    continue
                vistos.setdefault(s.examen_contenido_id, s.examen_titulo or s.examen_contenido_id)
            catalogo = sorted(vistos.items(), key=lambda kv: kv[1])
        return [ExamenConSesionesOut(id=eid, titulo=titulo) for eid, titulo in catalogo]

    # OJO: va ANTES de "/sessions/{session_id}". FastAPI resuelve por orden de
    # declaracion, asi que declarada despues, "en-curso" entraba como session_id y
    # el alumno se comia un 403 de supervision_vivo (la ruta de detalle es del tutor).
    @router.get(
        "/sessions/en-curso",
        response_model=list[SesionEnCursoOut],
        summary="Examenes que el alumno dejo empezados y sin entregar",
    )
    async def listar_sesiones_en_curso(
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> list[SesionEnCursoOut]:
        """Sesiones ABIERTAS del alumno autenticado, para poder retomarlas.

        El backend ya sabia reanudar (``crear_o_reanudar_sesion`` reusa la sesion
        activa con su cronometro, y ``GET /sessions/{id}/respuestas`` devuelve lo ya
        contestado), pero nada permitia DESCUBRIR esa sesion: al alumno que se le
        cortaba la conexion la pantalla le mostraba el examen como no empezado, con
        el cartel "Tenes un solo intento", y entendia que lo habia perdido. Una
        reanudacion que el alumno no puede encontrar es, para el, una reanudacion
        que no existe.

        Acotado SIEMPRE al alumno del JWT (H1/IDOR): nunca se lista por examen, o un
        alumno podria ver quien mas lo esta rindiendo. No devuelve score ni eventos:
        el proctoring no se le muestra al alumno.
        """
        from app.infrastructure.persistence.repositories.proctoring import (
            ProctoringRepository,
        )

        alumno = principal.username or ""
        if not alumno:
            return []
        repo = ProctoringRepository(db)
        sesiones = await repo.listar_sesiones_en_curso(alumno)
        if not sesiones:
            return []

        # Titulo del examen en UNA consulta (no una por sesion): es lo unico que la
        # tarjeta necesita mostrar y viene de otra tabla.
        from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel

        ids = {str(s.examen_contenido_id) for s in sesiones}
        filas = (
            await db.execute(
                select(ExamenContenidoModel.id, ExamenContenidoModel.titulo).where(
                    ExamenContenidoModel.id.in_(ids)
                )
            )
        ).all()
        titulos = {str(i): t for i, t in filas}

        return [
            SesionEnCursoOut(
                session_id=str(s.id),
                examen_contenido_id=str(s.examen_contenido_id),
                examen_titulo=titulos.get(str(s.examen_contenido_id)),
                creada_en=s.creada_en,
                examen_iniciado_en=s.examen_iniciado_en,
            )
            for s in sesiones
        ]

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

        C-76 bloque 8 (N:M desde c-79): el TUTOR solo accede al detalle de
        sesiones de SU comision (403 fuera de ella); el COORDINADOR, a las de SUS
        materias asignadas; solo ADMIN_SISTEMA es global."""
        sesion = await session_service.detalle_sesion(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        tiene_pertenencia = await session_service.tiene_pertenencia_de_sesion(
            db,
            principal.subject or "",
            session_id,
            es_coordinador=principal.tiene_rol(Rol.COORDINADOR),
        )
        try:
            autorizar_supervision_vivo_sobre_sesion(principal, tiene_pertenencia)
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
                # Descifrado at-rest de la evidencia. `leer_captura` es
                # el ÚNICO camino de lectura (c-78): resuelve si la captura está en
                # la columna binaria nueva o en la base64 legacy, y descifra según
                # corresponda. Ninguna pantalla decide eso por su cuenta.
                screenshot_base64=leer_captura(
                    screenshot_bin=e.screenshot_bin,
                    screenshot_prefijo=e.screenshot_prefijo,
                    screenshot_b64_legacy=e.screenshot_b64,
                    cipher=cipher,
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
                # c-78 E-07: el denominador es el set que le tocó a este intento.
                session_id=sesion_model.id,
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
