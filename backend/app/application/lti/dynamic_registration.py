"""Registro dinámico LTI 1.3 — el lado que faltaba (c-78 E-12, D15).

El proyecto publicaba su configuración de Tool (`GET /lti/dynamic-registration`)
pero NO recibía ni persistía el registro: el `client_id` y el `deployment_id`
reales había que copiarlos a mano de un request y cargarlos por API. Esa fila se
perdía cada vez que se recreaba la base, y el síntoma llegaba tarde (los alumnos
no podían entrar).

Flujo IMS "LTI Dynamic Registration" (el que implementa Moodle):

  1. El admin de Moodle pega la URL de registro. Moodle la abre en un iframe con
     `?openid_configuration=<url>&registration_token=<jwt>`.
  2. El Tool GET-ea esa `openid_configuration` y saca `registration_endpoint` y
     el `issuer` del Platform.
  3. El Tool POST-ea SU configuración a `registration_endpoint`, autenticándose
     con `Authorization: Bearer <registration_token>`.
  4. El Platform responde con el registro creado, que trae el `client_id` real y
     —dentro de la claim `lti-tool-configuration`— el `deployment_id`.
  5. El Tool persiste esa terna y le avisa al iframe que terminó.

D15: la fila se crea con ``activo=False``. La allowlist es la raíz de confianza
del flujo LTI (cada fila = un Moodle habilitado a crear cuentas), así que el
registro automatiza el TIPEO, no la APROBACIÓN: un admin la habilita después.

Sin estado global ni framework: las funciones reciben el cliente HTTP inyectado
para poder testearlas sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel

# Claim donde LTI mete la configuración específica del Tool, tanto en el request
# como en la respuesta del Platform.
CLAIM_TOOL_CONFIGURATION = "https://purl.imsglobal.org/spec/lti-tool-configuration"


class RegistroDinamicoError(Exception):
    """Falla del registro dinámico. El mensaje es un código estable, sin PII."""


@dataclass(frozen=True, slots=True)
class RegistroDinamicoResultado:
    """Lo que quedó registrado, para responderle a quien disparó el flujo."""

    deployment_id_fila: str
    iss: str
    client_id: str
    deployment_id: str
    #: ``True`` si la fila ya existía (registro repetido: es idempotente).
    ya_existia: bool
    #: Siempre ``False`` en un alta nueva — se expone para que la UI lo diga.
    activo: bool


class ClienteHttp(Protocol):
    """Mínimo que el flujo necesita de un cliente HTTP (inyectable en tests)."""

    def get_json(self, url: str) -> dict[str, Any]: ...

    def post_json(
        self, url: str, *, payload: dict[str, Any], token: str | None
    ) -> dict[str, Any]: ...


class ClienteHttpx:
    """Implementación real sobre httpx (la misma librería que usa el fetch de JWKS)."""

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout

    def get_json(self, url: str) -> dict[str, Any]:
        import httpx

        resp = httpx.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def post_json(
        self, url: str, *, payload: dict[str, Any], token: str | None
    ) -> dict[str, Any]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()


def construir_registro_tool(
    *,
    client_name: str,
    initiate_login_uri: str,
    launch_uri: str,
    jwks_uri: str,
    domain: str,
) -> dict[str, Any]:
    """Payload de registro del Tool (función PURA).

    Es la MISMA configuración que publica `GET /lti/dynamic-registration` sin
    parámetros; se construye acá para que las dos vistas no puedan divergir.
    """
    return {
        "application_type": "web",
        "response_types": ["id_token"],
        "grant_types": ["implicit", "client_credentials"],
        "initiate_login_uri": initiate_login_uri,
        "redirect_uris": [launch_uri],
        "client_name": client_name,
        "jwks_uri": jwks_uri,
        "token_endpoint_auth_method": "private_key_jwt",
        "scope": "openid",
        CLAIM_TOOL_CONFIGURATION: {
            "domain": domain,
            "target_link_uri": launch_uri,
            "claims": ["sub", "iss", "name", "email"],
            "messages": [
                {"type": "LtiResourceLinkRequest", "target_link_uri": launch_uri}
            ],
        },
    }


def _extraer_deployment_id(registro: dict[str, Any]) -> str:
    """Saca el `deployment_id` de la respuesta del Platform.

    Moodle lo devuelve dentro de la claim de tool-configuration. Se busca ahí y,
    por tolerancia, en la raíz: la ubicación exacta varía entre versiones del
    Platform y quedarse sin deployment_id vuelve la fila inservible.
    """
    tool_cfg = registro.get(CLAIM_TOOL_CONFIGURATION) or {}
    deployment_id = tool_cfg.get("deployment_id") or registro.get("deployment_id")
    if not deployment_id:
        raise RegistroDinamicoError("registro_sin_deployment_id")
    return str(deployment_id)


async def registrar_deployment_dinamico(
    db: AsyncSession,
    *,
    openid_configuration_url: str,
    registration_token: str | None,
    registro_tool: dict[str, Any],
    cliente: ClienteHttp,
) -> RegistroDinamicoResultado:
    """Ejecuta los pasos 2 a 5 y persiste la fila (inactiva) de la allowlist.

    Idempotente por ``(iss, client_id, deployment_id)``: si el mismo Moodle
    vuelve a registrarse, se devuelve la fila existente sin duplicar y **sin
    reactivarla** — un re-registro no puede ser una forma de auto-aprobarse.
    """
    if not openid_configuration_url:
        raise RegistroDinamicoError("openid_configuration_ausente")

    try:
        platform_cfg = cliente.get_json(openid_configuration_url)
    except RegistroDinamicoError:
        raise
    except Exception as exc:  # noqa: BLE001 — red/JSON: código estable, sin PII
        raise RegistroDinamicoError("openid_configuration_inaccesible") from exc

    issuer = platform_cfg.get("issuer")
    registration_endpoint = platform_cfg.get("registration_endpoint")
    if not issuer or not registration_endpoint:
        raise RegistroDinamicoError("openid_configuration_incompleta")

    # El JWKS del Platform es lo que después valida la firma del id_token en cada
    # launch. Sin él la fila no sirve para nada.
    jwks_uri_platform = platform_cfg.get("jwks_uri")
    if not jwks_uri_platform:
        raise RegistroDinamicoError("platform_sin_jwks_uri")

    try:
        registro = cliente.post_json(
            str(registration_endpoint),
            payload=registro_tool,
            token=registration_token,
        )
    except Exception as exc:  # noqa: BLE001
        raise RegistroDinamicoError("registro_rechazado_por_el_platform") from exc

    client_id = registro.get("client_id")
    if not client_id:
        raise RegistroDinamicoError("registro_sin_client_id")
    deployment_id = _extraer_deployment_id(registro)

    existente = (
        await db.execute(
            select(LtiDeploymentConfiableModel).where(
                LtiDeploymentConfiableModel.iss == str(issuer),
                LtiDeploymentConfiableModel.client_id == str(client_id),
                LtiDeploymentConfiableModel.deployment_id == deployment_id,
            )
        )
    ).scalar_one_or_none()

    if existente is not None:
        # Se refresca el jwks_uri (el Platform puede haberlo movido) pero NO el
        # `activo`: la aprobación humana no se re-negocia desde afuera.
        existente.jwks_uri = str(jwks_uri_platform)
        await db.flush()
        return RegistroDinamicoResultado(
            deployment_id_fila=str(existente.id),
            iss=existente.iss,
            client_id=existente.client_id,
            deployment_id=existente.deployment_id,
            ya_existia=True,
            activo=existente.activo,
        )

    fila = LtiDeploymentConfiableModel(
        iss=str(issuer),
        deployment_id=deployment_id,
        client_id=str(client_id),
        jwks_uri=str(jwks_uri_platform),
        # D15: nace INACTIVA. Un launch desde acá se rechaza hasta que un
        # admin_sistema la habilite desde la pantalla de deployments.
        activo=False,
    )
    db.add(fila)
    await db.flush()
    return RegistroDinamicoResultado(
        deployment_id_fila=str(fila.id),
        iss=fila.iss,
        client_id=fila.client_id,
        deployment_id=fila.deployment_id,
        ya_existia=False,
        activo=False,
    )


async def hay_deployment_activo(db: AsyncSession) -> bool:
    """``True`` si existe al menos una fila ACTIVA en la allowlist LTI.

    Insumo del chequeo de salud (c-78 §10.2): con la allowlist vacía, ningún
    launch entra. Hoy la única señal de eso es un alumno que no puede rendir.
    """
    fila = (
        await db.execute(
            select(LtiDeploymentConfiableModel.id)
            .where(LtiDeploymentConfiableModel.activo.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    return fila is not None
