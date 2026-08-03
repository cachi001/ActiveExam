"""Cableado del write-back de Moodle desde la config (C-69/C-73 §7.2).

Extrae la decisión de arranque que vivía inline en ``create_app`` (main_slim):
si ``MOODLE_BASE_URL`` está vacío el write-back queda DESHABILITADO (factory →
``None``) y la finalización degrada de forma segura a ``persistir_nota_pendiente``.
Aislarlo en un factory puro permite clavar ese contrato con un test sin levantar
la app entera. El token NUNCA se loguea: sólo viaja al ``MoodleClientConfig``.
"""

from __future__ import annotations

from typing import Protocol

from app.application.moodle.writeback_service import MoodleWritebackService
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient


class _MoodleSettings(Protocol):
    """Campos de settings que lee el cableado (duck-typed sobre SlimSettings)."""

    moodle_base_url: str
    moodle_ws_token: str
    moodle_component: str


def build_moodle_config(settings: _MoodleSettings) -> MoodleClientConfig | None:
    """Devuelve el config del cliente Moodle, o ``None`` si el write-back está deshabilitado.

    Gate único: si ``moodle_base_url`` está vacío → ``None`` (write-back off).
    """
    if not settings.moodle_base_url:
        return None
    return MoodleClientConfig(
        base_url=settings.moodle_base_url,
        ws_token=settings.moodle_ws_token,
        component=settings.moodle_component,
    )


def build_writeback_svc(settings: _MoodleSettings) -> MoodleWritebackService | None:
    """Construye el ``MoodleWritebackService``, o ``None`` si Moodle no está configurado."""
    config = build_moodle_config(settings)
    if config is None:
        return None
    return MoodleWritebackService(moodle_client=MoodleRestClient(config=config))


def build_writeback_svc_dinamico(
    resolver, credencial_docente=None
) -> MoodleWritebackService:
    """Write-back cuya credencial se resuelve en CADA llamada (migración 0047).

    ``resolver``: ``MoodleCredencialResolver``. El servicio se construye siempre
    (no devuelve None): quién está configurado y quién no lo decide la credencial
    vigente en el momento de usarla, no el estado del entorno al arrancar. Así,
    cargar el token desde la UI empieza a funcionar sin reiniciar el backend.
    """

    async def _provider() -> MoodleClientConfig:
        cred = await resolver.resolver()
        return MoodleClientConfig(
            base_url=cred.base_url,
            ws_token=cred.ws_token,
            component=cred.component,
        )

    return MoodleWritebackService(
        moodle_client=MoodleRestClient(config_provider=_provider),
        # C-73 §10.4: con esto la nota se devuelve con la credencial del docente a
        # cargo; sin esto (None) todo va por la institucional, como antes.
        credencial_docente=credencial_docente,
    )
