"""Router de la Configuracion del Sistema (configuracion-sistema-funcional).

Endpoints:
- ``GET  /effective`` : config efectiva autoritativa (cualquier autenticado). Incluye
  ``version`` como ETag para detectar config rancia.
- ``PATCH /``         : edita los defaults globales. SOLO ``admin_sistema`` con MFA.
  Bump monotonico de ``version`` + fila inmutable ``config_update`` en audit_log
  (snapshot before/after).

Reglas duras:
- ``extra='forbid'`` en todos los schemas.
- Edicion restringida a ``admin_sistema`` con MFA (RN-AU-05).
- ``umbral_cola_revision`` validado en [70, 100] (piso de producto); umbrales coherentes.
- L2.5: la config alimenta PRIORIZACION; nunca sancion automatica.

Patron: usa ``request.app.state.session_factory`` (igual que scoring/router.py).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit.acciones import (
    EntidadAuditoria,
    ModuloAuditoria,
    TipoAccionAuditoria,
)
from app.application.config.service import ConfigEfectiva, ConfigService
from app.domain.audit_chain import AuditEntry
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.persistence.repositories.audit_log import (
    AuditLogSqlRepository,
)
from app.infrastructure.persistence.repositories.config_sistema import (
    ConfiguracionSistemaSqlRepository,
)
from app.presentation.api.v1.auth.dependencies import (
    get_current_principal,
    require_mfa,
    require_roles,
)

router = APIRouter()

_require_admin = require_roles(Rol.ADMIN_SISTEMA)

ACCION_CONFIG_UPDATE = "config_update"


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigEfectivaResponse(_Strict):
    version: int
    face_absent_ms: int
    multiple_faces_frames: int
    gaze_deviation_threshold: float
    gaze_sustained_ms: int
    gaze_fixation_tolerance: float
    umbral_cola_revision: int
    retencion_dias_default: int
    consent_version_vigente: str
    detectores_activos: list[str]
    chat_habilitado: bool
    pausas_habilitadas: bool
    pausa_max_min: int
    scoring_weights: dict[str, int]
    scoring_severidades: dict[str, str] = {}


class EditarConfigRequest(_Strict):
    """Edicion parcial de la config global. Solo los campos enviados se actualizan.

    Los valores son las UNIDADES INTERNAS autoritativas (ms, 0-1, 0-100). La escala
    amigable (baja/media/alta + %) la convierte el frontend antes de enviar (ola 2)."""

    face_absent_ms: int | None = Field(default=None, ge=0, le=600000)
    multiple_faces_frames: int | None = Field(default=None, ge=1, le=1000)
    gaze_deviation_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    gaze_sustained_ms: int | None = Field(default=None, ge=0, le=600000)
    gaze_fixation_tolerance: float | None = Field(default=None, ge=0.0, le=1.0)
    # Piso de producto: el umbral de revisión NO puede bajar de 70 (decisión del
    # owner). Server-side sí o sí — el cliente es sensor no confiable (regla dura #6):
    # el slider del front también pisa en 70, pero la garantía vive acá.
    umbral_cola_revision: int | None = Field(default=None, ge=70, le=100)
    detectores_activos: list[str] | None = None
    retencion_dias_default: int | None = Field(default=None, ge=0, le=36500)
    consent_version_vigente: str | None = None
    # Toggles globales de la rendicion (C-69).
    chat_habilitado: bool | None = None
    pausas_habilitadas: bool | None = None
    pausa_max_min: int | None = Field(default=None, ge=1, le=120)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _config_service(request: Request) -> ConfigService:
    """Reusa el ConfigService cacheado en app.state, o crea uno por request."""
    svc = getattr(request.app.state, "config_service", None)
    if svc is None:
        svc = ConfigService(_get_session_factory(request))
        request.app.state.config_service = svc
    return svc


def _to_response(e: ConfigEfectiva) -> ConfigEfectivaResponse:
    return ConfigEfectivaResponse(
        version=e.version,
        face_absent_ms=e.face_absent_ms,
        multiple_faces_frames=e.multiple_faces_frames,
        gaze_deviation_threshold=e.gaze_deviation_threshold,
        gaze_sustained_ms=e.gaze_sustained_ms,
        gaze_fixation_tolerance=e.gaze_fixation_tolerance,
        umbral_cola_revision=e.umbral_cola_revision,
        retencion_dias_default=e.retencion_dias_default,
        consent_version_vigente=e.consent_version_vigente,
        detectores_activos=list(e.detectores_activos),
        chat_habilitado=e.chat_habilitado,
        pausas_habilitadas=e.pausas_habilitadas,
        pausa_max_min=e.pausa_max_min,
        scoring_weights=dict(e.scoring_weights),
        scoring_severidades=dict(e.scoring_severidades),
    )


def _snapshot(cfg) -> dict:
    """Snapshot serializable de la config (para before/after del audit)."""
    if cfg is None:
        return {}
    return {
        "version": cfg.version,
        "face_absent_ms": cfg.face_absent_ms,
        "multiple_faces_frames": cfg.multiple_faces_frames,
        "gaze_deviation_threshold": float(cfg.gaze_deviation_threshold),
        "gaze_sustained_ms": cfg.gaze_sustained_ms,
        "gaze_fixation_tolerance": float(cfg.gaze_fixation_tolerance),
        "umbral_cola_revision": cfg.umbral_cola_revision,
        "detectores_activos": list(cfg.detectores_activos or ()),
        "retencion_dias_default": cfg.retencion_dias_default,
        "consent_version_vigente": cfg.consent_version_vigente,
        "chat_habilitado": cfg.chat_habilitado,
        "pausas_habilitadas": cfg.pausas_habilitadas,
        "pausa_max_min": cfg.pausa_max_min,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# GET /effective — config efectiva autoritativa (cualquier autenticado)
# ---------------------------------------------------------------------------


@router.get("/effective", response_model=ConfigEfectivaResponse)
async def config_efectiva(
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConfigEfectivaResponse:
    """Devuelve la configuracion efectiva (pesos + umbrales + version/ETag).

    Accesible a cualquier usuario autenticado: la lee TEST DETECCION, el examen y
    el panel. El campo ``version`` permite al cliente detectar staleness."""
    svc = _config_service(request)
    efectiva = await svc.get_efectiva()
    return _to_response(efectiva)


# ---------------------------------------------------------------------------
# PATCH / — editar la config global (SOLO admin_sistema)
# ---------------------------------------------------------------------------


@router.patch("", response_model=ConfigEfectivaResponse)
async def editar_config(
    body: EditarConfigRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ConfigEfectivaResponse:
    """Edita los defaults globales. SOLO ``admin_sistema`` (403 si no).

    C-68 (decisión del dueño): edición restringida a ``admin_sistema`` por ROL,
    sin exigir MFA. El backend slim usa JWT propio que NO emite MFA (deuda técnica
    documentada en own_issuer.py: 'MFA propio = change futuro'); exigir MFA acá
    haría la config INEDITABLE en slim/Railway. Cuando exista MFA propio se puede
    re-agregar require_mfa.

    400 si el body no trae ningun campo. Bump monotonico de version + fila
    inmutable ``config_update`` en audit_log (snapshot before/after).

    422 si ``consent_version_vigente`` refiere una version que no existe en la tabla
    ``consent_texto_version`` (C-08 ext, Ley 25.326 compliance)."""
    cambios = body.model_dump(exclude_none=True)
    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El body debe incluir al menos un campo a actualizar.",
        )

    factory = _get_session_factory(request)

    # Validar consent_version_vigente contra la tabla de versiones si se especifica.
    if "consent_version_vigente" in cambios:
        nueva_version = cambios["consent_version_vigente"]
        from app.application.consent.text_version_service import ConsentTextoVersionService
        async with factory() as session:
            tv_svc = ConsentTextoVersionService(session)
            if not await tv_svc.version_exists(nueva_version):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"La version de consentimiento {nueva_version!r} no existe en la tabla "
                        "consent_texto_version. Publicala primero con POST /api/v1/consent/text/versions."
                    ),
                )

    async with factory() as session:
        repo = ConfiguracionSistemaSqlRepository(session)
        antes = await repo.ensure_singleton()
        before = _snapshot(antes)
        actualizado = await repo.update(cambios)
        after = _snapshot(actualizado)

        # Auditoria inmutable: fila config_update con before/after (cadena de custodia).
        await AuditLogSqlRepository(session).append(
            AuditEntry(
                actor=principal.id_institucional,
                timestamp=_now_iso(),
                ip="",
                user_agent="",
                accion=ACCION_CONFIG_UPDATE,
                evidencia_id=None,
                proposito=json.dumps(
                    {"before": before, "after": after}, ensure_ascii=False
                ),
                # Clasificación para el filtro/export de Auditoría: sin esto el cambio
                # de config quedaba con modulo=NULL y NO aparecía al filtrar por
                # "Configuración del sistema".
                modulo=ModuloAuditoria.CONFIGURACION,
                entidad=EntidadAuditoria.CONFIGURACION,
                tipo_accion=TipoAccionAuditoria.EDITAR,
            )
        )
        await session.commit()

    # Invalida el cache del ConfigService para que la proxima lectura traiga lo nuevo.
    svc = _config_service(request)
    svc.invalidate()
    efectiva = await svc.get_efectiva()
    return _to_response(efectiva)


# ---------------------------------------------------------------------------
# Credencial de servicio de Moodle (migración 0047) — SOLO admin_sistema.
#
# El token de Web Services es un SECRETO: se guarda cifrado (Fernet) y NUNCA sale
# por la API. La lectura devuelve si hay token y sus últimos 4 caracteres, para que
# el admin reconozca cuál cargó sin poder reconstruirlo. Tampoco se audita el valor:
# el rastro dice QUÉ campos se tocaron y quién, jamás el secreto.
# ---------------------------------------------------------------------------

ACCION_MOODLE_CREDENCIAL = "moodle_credencial_update"


class MoodleCredencialResponse(BaseModel):
    """Estado de la credencial SIN el token (nunca se devuelve)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str
    courseid: int
    cmid: int
    component: str
    #: True si hay un token utilizable (en la base o, si la base está vacía, en el entorno).
    token_configurado: bool
    #: Últimos 4 caracteres del token guardado. None si el token viene del entorno.
    token_pista: str | None = None
    #: "db" | "env" | "sin_configurar" — de dónde sale la credencial vigente.
    origen: str
    actualizado_en: str | None = None
    actualizado_por: str | None = None


class GuardarMoodleCredencialRequest(BaseModel):
    """Body del PUT. Todos los campos opcionales (update parcial).

    ``token`` ausente = NO se toca el token guardado (para poder corregir el
    courseid sin re-tipear el secreto). Para borrarlo está DELETE.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str | None = None
    token: str | None = Field(default=None, min_length=8, max_length=512)
    courseid: int | None = Field(default=None, ge=0)
    cmid: int | None = Field(default=None, ge=0)
    component: str | None = None

    @field_validator("component")
    @classmethod
    def component_valido(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in {"mod_assign", "mod_quiz"}:
            raise ValueError("component debe ser 'mod_assign' o 'mod_quiz'.")
        return v


def _resolver_credenciales(request: Request):
    resolver = getattr(request.app.state, "moodle_credenciales", None)
    if resolver is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credenciales de Moodle no inicializadas.",
        )
    return resolver


def _a_response(estado) -> MoodleCredencialResponse:
    return MoodleCredencialResponse(
        base_url=estado.base_url,
        courseid=estado.courseid,
        cmid=estado.cmid,
        component=estado.component,
        token_configurado=estado.token_configurado,
        token_pista=estado.token_pista,
        origen=estado.origen,
        actualizado_en=estado.actualizado_en,
        actualizado_por=estado.actualizado_por,
    )


async def _auditar_credencial(
    request: Request, principal: AuthenticatedPrincipal, proposito: str
) -> None:
    """Deja rastro del cambio de credencial. NUNCA registra el token."""
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        await AuditLogSqlRepository(session).append(
            AuditEntry(
                actor=principal.id_institucional,
                timestamp=_now_iso(),
                ip="",
                user_agent="",
                accion=ACCION_MOODLE_CREDENCIAL,
                evidencia_id=None,
                proposito=proposito,
            )
        )
        await session.commit()


@router.get("/moodle", response_model=MoodleCredencialResponse)
async def leer_credencial_moodle(
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> MoodleCredencialResponse:
    """Estado de la credencial de Moodle. El token NO se devuelve."""
    resolver = _resolver_credenciales(request)
    return _a_response(await resolver.estado())


@router.put("/moodle", response_model=MoodleCredencialResponse)
async def guardar_credencial_moodle(
    body: GuardarMoodleCredencialRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> MoodleCredencialResponse:
    """Guarda la credencial (token cifrado at-rest). 400 si el body viene vacío."""
    if all(
        v is None
        for v in (body.base_url, body.token, body.courseid, body.cmid, body.component)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El body debe incluir al menos un campo a actualizar.",
        )

    resolver = _resolver_credenciales(request)
    estado = await resolver.guardar(
        base_url=body.base_url,
        token=body.token,
        courseid=body.courseid,
        cmid=body.cmid,
        component=body.component,
        actor=principal.id_institucional,
    )

    # Qué se tocó, nunca con qué valor de token.
    campos = [
        nombre
        for nombre, valor in (
            ("base_url", body.base_url),
            ("courseid", body.courseid),
            ("cmid", body.cmid),
            ("component", body.component),
        )
        if valor is not None
    ]
    if body.token:
        campos.append("token (reemplazado)")
    await _auditar_credencial(
        request, principal, f"Actualizó la credencial de Moodle: {', '.join(campos)}"
    )
    return _a_response(estado)


@router.delete("/moodle/token", response_model=MoodleCredencialResponse)
async def borrar_token_moodle(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> MoodleCredencialResponse:
    """Borra el token guardado. El write-back deja de escribir hasta cargar otro."""
    resolver = _resolver_credenciales(request)
    estado = await resolver.borrar_token(actor=principal.id_institucional)
    await _auditar_credencial(
        request, principal, "Eliminó el token de Moodle guardado"
    )
    return _a_response(estado)
