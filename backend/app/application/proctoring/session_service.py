"""Servicio de aplicacion para sesiones de proctoring activeexam.

Orquesta la creacion, listado y detalle de sesiones. No depende de Keycloak,
Vault ni MinIO. La logica de scoring se delega a scoring.py para evitar
duplicacion con el repositorio.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.scoring import calcular_score, construir_config_snapshot
from app.domain.events.reanudacion import clasificar_reanudacion
from app.domain.events.schema import TipoEvento
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

# Severidad en el vocabulario del CATÁLOGO (evento_score_config / frontend usan
# "baja"/"media"/"alta"/"critica"), no el del enum de dominio ("baseline"...).
_SEVERIDAD_CATALOGO_REANUDACION = {
    TipoEvento.RECARGA_PAGINA: "baja",
    TipoEvento.REANUDACION_TARDIA: "media",
}
from app.infrastructure.persistence.repositories.proctoring import (
    ProctoringRepository,
    SesionResumenData,
)

_log = logging.getLogger(__name__)


async def _emitir_evento_reanudacion(
    repo: ProctoringRepository, sesion: ProctoringSessionModel
) -> None:
    """Emite SERVER-SIDE el evento de reanudación (C-72 sección 5, H-4).

    La ausencia se mide como el tiempo desde el último evento de la sesión (o desde
    ``creada_en`` si no hubo eventos), con hora del servidor — el cliente no reporta
    nada, así que un navegador modificado no puede suprimir el evento (regla #6). La
    duración clasifica entre recarga rápida y reanudación tardía y queda en el payload.
    """
    ahora = datetime.now(timezone.utc)
    ultimo = await repo.ultimo_evento_ts_backend(sesion.id)
    referencia = ultimo or sesion.creada_en
    ausencia_seg = max(0.0, (ahora - referencia).total_seconds())
    tipo = clasificar_reanudacion(ausencia_seg)
    await repo.crear_evento(
        session_id=sesion.id,
        tipo=tipo.value,
        severidad=_SEVERIDAD_CATALOGO_REANUDACION[tipo],
        ts_cliente=ahora,  # server-side: no hay reporte del cliente
        payload={"ausencia_seg": round(ausencia_seg, 1), "origen": "server"},
    )


class ConfigSnapshotNoDisponibleError(Exception):
    """La config del sistema no se pudo leer al crear la sesion.

    Decision de producto: NUNCA se crea una sesion de examen sin foto de
    config (migration 0083) — si el score/umbral no queda fijado en el
    instante en que el alumno arranca, un cambio de config posterior podria
    evaluar retroactivamente eventos que el alumno vio con otro valor. Antes
    esto degradaba en silencio a la config viva (GAP real: un revisor podia
    anular con un numero distinto al que el alumno vio en pantalla). Ahora
    bloquea la creacion de la sesion con un error explicito en vez de eso.
    """


async def _construir_snapshot_al_crear(db: AsyncSession) -> dict:
    """Foto de umbral/pesos de scoring vigente AHORA, para guardar en la sesion
    que se está creando (migration 0083).

    Se resuelve con las mismas fuentes que ``ConfigService``/los helpers vivos
    del router (``evento_score_config``, ``configuracion_sistema``), sin pasar
    por su cache (la sesion necesita el valor exacto de este instante, no uno
    potencialmente stale).

    Nunca degrada en silencio: si la config no esta disponible, eleva
    ``ConfigSnapshotNoDisponibleError`` — la sesion NO se crea sin foto (ver
    docstring de la excepcion). El caller HTTP la traduce a 503.
    """
    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
        EventoScoreConfigModel,
    )

    try:
        # c-78: se leen en la MISMA consulta los interruptores de chat y pausas.
        # La foto tiene que incluirlos para que el gate server-side los respete sin
        # mirar la config viva (que cambiaria una rendicion ya empezada).
        config_row = await db.execute(
            select(
                ConfiguracionSistemaModel.umbral_cola_revision,
                ConfiguracionSistemaModel.chat_habilitado,
                ConfiguracionSistemaModel.pausas_habilitadas,
            )
        )
        fila_config = config_row.first()
        umbral = fila_config[0] if fila_config is not None else None
        chat_habilitado = bool(fila_config[1]) if fila_config is not None else None
        pausas_habilitadas = bool(fila_config[2]) if fila_config is not None else None
        if umbral is None:
            raise ConfigSnapshotNoDisponibleError(
                "configuracion_sistema.umbral_cola_revision no esta disponible"
            )

        pesos_rows = await db.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
                EventoScoreConfigModel.activo,
            )
        )
        pesos: dict[str, int] = {}
        desactivados: set[str] = set()
        for tipo, peso, activo in pesos_rows.all():
            if activo:
                pesos[tipo] = int(peso)
            else:
                desactivados.add(tipo)
    except ConfigSnapshotNoDisponibleError:
        raise
    except Exception as exc:  # noqa: BLE001 — nunca crear sesion sin foto de config
        # Medido bajo carga (150+ sesiones concurrentes, pool de DB agotado): sin
        # este log, la causa real (timeout de pool, conexion rechazada, etc.)
        # quedaba invisible — el 503 traducido no dice NADA de lo que pasó de
        # verdad, y en logs no aparecia ningun traceback.
        _log.exception(
            "Fallo al leer configuracion del sistema al crear sesion (se traduce a 503)"
        )
        raise ConfigSnapshotNoDisponibleError(
            "no se pudo leer la configuracion del sistema al crear la sesion"
        ) from exc

    return construir_config_snapshot(
        umbral_cola_revision=int(umbral),
        pesos_por_tipo=pesos,
        tipos_desactivados=frozenset(desactivados),
        chat_habilitado=chat_habilitado,
        pausas_habilitadas=pausas_habilitadas,
    )


async def crear_sesion(
    db: AsyncSession,
    modo: str,
    exam_id: str | None = None,
    etiqueta: str | None = None,
    examen_contenido_id: str | None = None,
    alumno_idnumber: str | None = None,
    alumno_email: str | None = None,
) -> ProctoringSessionModel:
    """Crea una nueva sesion de proctoring activeexam.

    ``examen_contenido_id`` (C-69) vincula la sesion con el examen de contenido
    importado de Moodle XML (NULLABLE). ``alumno_idnumber``/``alumno_email``
    persisten la identidad del alumno (C-69, enforcement de intentos).

    C-config-snapshot (migration 0083): guarda una foto de umbral/pesos de
    scoring vigente AHORA en la sesion, para que un cambio de config posterior
    no la afecte retroactivamente.
    """
    repo = ProctoringRepository(db)
    snapshot = await _construir_snapshot_al_crear(db)
    return await repo.crear_sesion(
        modo=modo,
        exam_id=exam_id,
        etiqueta=etiqueta,
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
        config_snapshot=snapshot,
    )


async def crear_o_reanudar_sesion(
    db: AsyncSession,
    modo: str,
    exam_id: str | None = None,
    etiqueta: str | None = None,
    examen_contenido_id: str | None = None,
    alumno_idnumber: str | None = None,
    alumno_email: str | None = None,
) -> ProctoringSessionModel:
    """Crea una sesion, o REANUDA la activa existente (anti-zombie, reload durante examen).

    Solo aplica la busqueda de reanudacion cuando hay ``examen_contenido_id`` Y
    ``alumno_idnumber`` (la sesion 'test' sin vinculo no tiene forma de identificar
    "la misma rendicion" — cada POST crea una fila nueva, como antes).

    Si el alumno ya tiene una sesion ACTIVA (``finalizada_en IS NULL``) para ese
    examen, se devuelve ESA MISMA fila (misma id, misma creada_en) en vez de crear
    una nueva. Esto es lo que rompe el ciclo "F5 -> sesion zombie": recargar la
    pagina vuelve a pasar por acá y encuentra la sesion ya abierta, así que el
    timer (creada_en) y las respuestas ya guardadas (via GET .../respuestas) se
    pueden restaurar en el cliente en vez de perderse.
    """
    repo = ProctoringRepository(db)
    if examen_contenido_id is not None and alumno_idnumber:
        activa = await repo.obtener_sesion_activa(alumno_idnumber, examen_contenido_id)
        if activa is not None:
            # C-72 sección 5 (H-4): reabrir una sesión activa emite el evento de
            # reanudación server-side. Solo en el resume — crear una sesión nueva
            # (rama de abajo) NO emite (no hubo reapertura). Tampoco se re-toma el
            # snapshot de config: la sesión reanudada sigue con la foto tomada al
            # crearla la primera vez (misma sesión, mismo examen que arrancó).
            await _emitir_evento_reanudacion(repo, activa)
            return activa
    snapshot = await _construir_snapshot_al_crear(db)
    return await repo.crear_sesion(
        modo=modo,
        exam_id=exam_id,
        etiqueta=etiqueta,
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=alumno_idnumber,
        alumno_email=alumno_email,
        config_snapshot=snapshot,
    )


async def listar_sesiones(db: AsyncSession) -> list[SesionResumenData]:
    """Lista todas las sesiones con total_eventos, total_discrepancias y score."""
    repo = ProctoringRepository(db)
    return await repo.listar_sesiones()


async def listar_sesiones_finalizadas(
    db: AsyncSession,
    *,
    q: str | None = None,
    exam_id: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    materia_id: str | None = None,
    comision_id: str | None = None,
    comision_ids_permitidas: set[str] | None = None,
) -> list[SesionResumenData]:
    """Sesiones finalizadas con filtros SQL (Registro de sesiones, C-76 tarea 17).

    ``materia_id``/``comision_id`` (C-76 tarea 20.3): filtro en cascada.

    ``comision_ids_permitidas`` (c-78 §11.4): scoping por pertenencia, EN SQL.
    ``None`` = sin restriccion (admin_sistema). Un set vacio devuelve vacio.

    NO pagina ni filtra por nivel de riesgo — eso lo hace el router (mismo motivo
    que ``resultados_query``: el nivel de riesgo depende del score, que recien se
    conoce despues de esta consulta)."""
    repo = ProctoringRepository(db)
    return await repo.listar_sesiones_finalizadas(
        q=q,
        exam_id=exam_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        materia_id=materia_id,
        comision_id=comision_id,
        comision_ids_permitidas=comision_ids_permitidas,
    )


async def catalogo_examenes_con_sesiones(db: AsyncSession) -> list[tuple[str, str]]:
    """``[(examen_contenido_id, titulo)]`` con sesiones finalizadas (C-76 tarea 17.2)."""
    repo = ProctoringRepository(db)
    return await repo.catalogo_examenes_con_sesiones()


async def obtener_umbral_alto(db: AsyncSession) -> int:
    """Umbral de riesgo "alto" VIVO (``configuracion_sistema.umbral_cola_revision``).

    Misma fuente que la Cola de revision humana y ``resultados_query._umbral_cola_revision``
    (degradacion graceful: default institucional 70 si la tabla/singleton no esta
    disponible). Se define aca (no se importa el helper privado de
    ``resultados_query``, modulo de otro dominio) para no crear un acoplamiento
    cruzado moodle -> proctoring."""
    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
    )

    UMBRAL_DEFAULT = 70
    try:
        row = await db.execute(select(ConfiguracionSistemaModel.umbral_cola_revision))
        val = row.scalars().first()
    except Exception:  # noqa: BLE001 — degradacion: sin config, usa el default
        return UMBRAL_DEFAULT
    return int(val) if val is not None else UMBRAL_DEFAULT


async def detalle_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Obtiene el detalle completo de una sesion (con eventos y biometria)."""
    repo = ProctoringRepository(db)
    return await repo.obtener_sesion(session_id)


async def contexto_academico_de_examen(
    db: AsyncSession, examen_contenido_id: str | None
) -> tuple[str | None, str | None, str | None]:
    """(examen_titulo, comision_nombre, materia_nombre) de un examen_contenido_id.

    Usado por el detalle de sesión (GET /sessions/{id}) para mostrar en el header
    qué examen rindió el alumno y de qué materia/comisión — mismo join que ya usa
    el listado de sesiones, para UN solo examen."""
    repo = ProctoringRepository(db)
    return await repo.contexto_academico_de_examen(examen_contenido_id)


async def nombre_alumno_de_sesion(
    db: AsyncSession, alumno_idnumber: str | None, alumno_email: str | None
) -> str | None:
    """Nombre completo del alumno dueño de la sesión (o None si no se resuelve)."""
    repo = ProctoringRepository(db)
    return await repo.nombre_alumno(alumno_idnumber, alumno_email)


async def tiene_pertenencia_de_sesion(
    db: AsyncSession, usuario_id: str, session_id: str, *, es_coordinador: bool = False
) -> bool:
    """Pertenencia sobre la sesion (C-76 bloque 8, N:M c-79). Ver
    ``ProctoringRepository.tiene_pertenencia_de_sesion`` para el detalle."""
    repo = ProctoringRepository(db)
    return await repo.tiene_pertenencia_de_sesion(
        usuario_id, session_id, es_coordinador=es_coordinador
    )


async def obtener_sesion_ligera(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Fetch simple de la sesion por id, sin JOINs.

    Usado por los guards de pertenencia (H1, IDOR) de chat/pausas — necesitan
    ``alumno_idnumber``/``alumno_email`` para decidir si el principal es el
    dueño de la sesion antes de dejarlo leer/escribir en ella."""
    return await db.get(ProctoringSessionModel, session_id)


async def finalizar_sesion(
    db: AsyncSession, session_id: str
) -> ProctoringSessionModel | None:
    """Setea finalizada_en = now() si es NULL (idempotente). None si no existe."""
    repo = ProctoringRepository(db)
    return await repo.finalizar_sesion(session_id)


async def eliminar_sesion_test(db: AsyncSession, session_id: str) -> str:
    """Elimina una sesion SOLO si es ``modo='test'`` (C-76 tarea 20.1).

    Devuelve ``'eliminada'`` | ``'no_encontrada'`` | ``'modo_examen'``. Ver
    ``ProctoringRepository.eliminar_sesion_test`` para el detalle de la
    proteccion de ``modo='examen'`` (regla dura #6/#7, permanente)."""
    repo = ProctoringRepository(db)
    return await repo.eliminar_sesion_test(session_id)


async def cerrar_forzado(
    db: AsyncSession,
    session_id: str,
    motivo: str,
    tutor_actor: str | None = None,
) -> ProctoringSessionModel | None:
    """Cierre forzado de la sesion por el proctor (operativo, NO disciplinario).

    Idempotente: si ya estaba cerrada de forma forzada, no muta el audit. None si
    la sesion no existe. Ver ProctoringRepository.cerrar_forzado."""
    repo = ProctoringRepository(db)
    return await repo.cerrar_forzado(session_id, motivo=motivo, tutor_actor=tutor_actor)
