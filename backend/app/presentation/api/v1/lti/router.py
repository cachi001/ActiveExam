"""Tool Provider LTI 1.3 de ActiveExam (C-75).

Secciones 2 y 3 del change: JWKS + registro dinámico + login OIDC. La validación
del launch (sección 4) y el JIT provisioning (sección 5) se agregan aparte.

Estos endpoints son PÚBLICOS (sin Bearer): el flujo LTI ocurre ANTES de que el
alumno tenga sesión en ActiveExam. La confianza no viene de un token propio sino
de (a) la allowlist `lti_deployment_confiable` (falla cerrado) y (b) —en el launch—
la firma del `id_token` contra el JWKS de Moodle.

Sólo Moodle: el endpoint de autorización del Platform se deriva de `iss`
(`{iss}/mod/lti/auth.php`), coherente con el Non-Goal "un solo LMS".
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

logger = logging.getLogger("lti")

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select

from app.application.lti.jit_provisioning import provisionar_o_recuperar_usuario
from app.application.lti.launch_validation import (
    JwksFetcher,
    LaunchInvalidoError,
    _default_jwks_fetcher,
    validar_launch,
)
from app.infrastructure.auth.db_refresh_store import DbRefreshTokenStore
from app.infrastructure.auth.own_issuer import emitir_jwt_propio
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.lti.keys import asegurar_tool_key_activa
from app.infrastructure.persistence.models.lti import (
    LtiDeploymentConfiableModel,
    LtiNonceModel,
    LtiToolKeyModel,
)

# TTL del nonce/state del flujo OIDC (design D5): corto, sólo tiene que sobrevivir
# el ida-y-vuelta login → launch.
_NONCE_TTL = timedelta(minutes=5)


def _base_url(request: Request) -> str:
    """URL base absoluta del Tool (sin barra final). Detrás del túnel/proxy debe
    llegar el esquema/host reales vía forwarded headers."""
    return str(request.base_url).rstrip("/")


def _launch_uri(request: Request) -> str:
    return f"{_base_url(request)}/api/v1/lti/launch"


def _login_uri(request: Request) -> str:
    return f"{_base_url(request)}/api/v1/lti/login"


def _jwks_uri(request: Request) -> str:
    return f"{_base_url(request)}/api/v1/lti/jwks"


def create_lti_router(
    session_factory=None,
    *,
    cipher: SecretCipher,
    # Sección 5: emisión de sesión tras JIT provisioning.
    # Si no se proveen, el endpoint /lti/launch devuelve JSON en lugar de redirigir
    # (retrocompatibilidad para tests de sección 4 que no los pasan).
    jwt_secret: str | None = None,
    jwt_issuer: str = "activeexam-auth",
    jwt_audience: str = "activeexam",
    jwt_ttl_seconds: int = 900,
    refresh_ttl_seconds: int = 604800,
    frontend_url: str = "",
    # Permite inyectar un fetcher de JWKS en tests sin HTTP a Moodle.
    jwks_fetcher_override: JwksFetcher | None = None,
) -> APIRouter:
    """Factory del router LTI.

    Args:
        cipher: cifra la clave privada RS256 del Tool al generarla.
        jwt_secret: secreto HS256 para emitir el JWT de sesión propio tras el
            launch (mismo que ``JWT_OWN_SECRET`` de ``/auth/login``). Si es None,
            el endpoint /lti/launch omite JIT + emisión de sesión y devuelve JSON
            (modo sección 4 — retrocompatibilidad).
        jwt_issuer: claim ``iss`` del JWT propio (``JWT_OWN_ISSUER``).
        jwt_audience: claim ``aud`` del JWT propio (``JWT_AUDIENCE``).
        jwt_ttl_seconds: vida del access token en segundos (default 15 min).
        refresh_ttl_seconds: vida del refresh token en segundos (default 7 días).
        frontend_url: URL base del frontend al que redirigir tras el launch
            exitoso. El token va como query param ``access_token``.
        jwks_fetcher_override: fetcher alternativo de JWKS (para tests sin HTTP).
    """
    router = APIRouter()

    def _factory(request: Request):
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        return factory

    # -- Sección 2: JWKS + registro dinámico ------------------------------------

    @router.get("/jwks", summary="JWK Set público del Tool (LTI 1.3)")
    async def lti_jwks(request: Request):
        """Publica las claves RS256 públicas activas del Tool. Genera el par la
        primera vez (perezoso, idempotente)."""
        factory = _factory(request)
        async with factory() as session:
            await asegurar_tool_key_activa(session, cipher)
            activas = (
                await session.execute(
                    select(LtiToolKeyModel).where(LtiToolKeyModel.activo.is_(True))
                )
            ).scalars().all()
            await session.commit()
        return {"keys": [k.clave_publica_jwk for k in activas]}

    @router.get(
        "/dynamic-registration",
        summary="Configuración del Tool para el registro dinámico (IMS)",
    )
    async def lti_dynamic_registration(request: Request):
        """Config que Moodle consume al registrar ActiveExam como herramienta LTI 1.3."""
        base = _base_url(request)
        host = request.url.hostname or ""
        return {
            "application_type": "web",
            "response_types": ["id_token"],
            "grant_types": ["implicit", "client_credentials"],
            "initiate_login_uri": _login_uri(request),
            "redirect_uris": [_launch_uri(request)],
            "client_name": "ActiveExam",
            "jwks_uri": _jwks_uri(request),
            "token_endpoint_auth_method": "private_key_jwt",
            "scope": "openid",
            "https://purl.imsglobal.org/spec/lti-tool-configuration": {
                "domain": host,
                "target_link_uri": _launch_uri(request),
                "claims": ["sub", "iss", "name", "email"],
            },
        }

    # -- Sección 3: login OIDC (third-party initiated login) --------------------

    async def _login_impl(
        request: Request,
        *,
        iss: str,
        login_hint: str,
        target_link_uri: str,
        client_id: str | None,
        lti_deployment_id: str | None,
        lti_message_hint: str | None,
    ):
        """Valida que el emisor sea de confianza, persiste state+nonce y redirige al
        endpoint de autorización de Moodle. Falla cerrado si el `iss`/`client_id` no
        está en la allowlist: 403 SIN generar nada."""
        factory = _factory(request)
        ahora = datetime.now(timezone.utc)

        cond = [
            LtiDeploymentConfiableModel.iss == iss,
            LtiDeploymentConfiableModel.activo.is_(True),
        ]
        if client_id is not None:
            cond.append(LtiDeploymentConfiableModel.client_id == client_id)
        if lti_deployment_id is not None:
            cond.append(
                LtiDeploymentConfiableModel.deployment_id == lti_deployment_id
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        async with factory() as session:
            confiable = (
                await session.execute(
                    select(LtiDeploymentConfiableModel.id).where(*cond).limit(1)
                )
            ).scalar_one_or_none()
            if confiable is None:
                # Falla cerrado: emisor desconocido, no se persiste state/nonce.
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="lti_iss_no_confiable",
                )

            # Limpieza oportunista de nonces vencidos (TTL, sin scheduler).
            await session.execute(
                delete(LtiNonceModel).where(LtiNonceModel.expira_en < ahora)
            )
            session.add(
                LtiNonceModel(
                    nonce=nonce,
                    state=state,
                    iss=iss,
                    expira_en=ahora + _NONCE_TTL,
                )
            )
            await session.commit()

        # Endpoint de autorización del Platform (Moodle).
        auth_url = f"{iss.rstrip('/')}/mod/lti/auth.php"
        params = {
            "scope": "openid",
            "response_type": "id_token",
            "response_mode": "form_post",
            "prompt": "none",
            "client_id": client_id or "",
            "redirect_uri": _launch_uri(request),
            "login_hint": login_hint,
            "state": state,
            "nonce": nonce,
        }
        if lti_message_hint is not None:
            params["lti_message_hint"] = lti_message_hint
        return RedirectResponse(
            f"{auth_url}?{urlencode(params)}", status_code=status.HTTP_302_FOUND
        )

    # OIDC third-party initiated login: la spec LTI 1.3 permite GET o POST. Moodle
    # lo envía como POST (form-encoded) desde el iframe del launch; otros Platforms
    # usan GET. Registramos ambos verbos contra la misma lógica.
    @router.get("/login", summary="Inicio de login OIDC de LTI (third-party, GET)")
    async def lti_login_get(
        request: Request,
        iss: str,
        login_hint: str,
        target_link_uri: str,
        client_id: str | None = None,
        lti_deployment_id: str | None = None,
        lti_message_hint: str | None = None,
    ):
        return await _login_impl(
            request,
            iss=iss,
            login_hint=login_hint,
            target_link_uri=target_link_uri,
            client_id=client_id,
            lti_deployment_id=lti_deployment_id,
            lti_message_hint=lti_message_hint,
        )

    @router.post("/login", summary="Inicio de login OIDC de LTI (third-party, POST)")
    async def lti_login_post(
        request: Request,
        iss: str = Form(...),
        login_hint: str = Form(...),
        target_link_uri: str = Form(...),
        client_id: str | None = Form(None),
        lti_deployment_id: str | None = Form(None),
        lti_message_hint: str | None = Form(None),
    ):
        return await _login_impl(
            request,
            iss=iss,
            login_hint=login_hint,
            target_link_uri=target_link_uri,
            client_id=client_id,
            lti_deployment_id=lti_deployment_id,
            lti_message_hint=lti_message_hint,
        )

    # Resuelve el jwks_fetcher a usar: el override (tests) o el de producción (HTTP).
    _jwks_fetcher = jwks_fetcher_override or _default_jwks_fetcher

    # -- Sección 4 + 5: validación del launch + JIT provisioning + sesión ------

    @router.post("/launch", summary="Recibe y valida el launch LTI (id_token firmado)")
    async def lti_launch(
        request: Request,
        id_token: str = Form(...),
        state: str = Form(...),
    ):
        """Valida el ``id_token`` (firma + nonce + aud + exp), provisiona JIT al
        alumno si no existe, emite JWT de sesión propio (mismo emisor que
        ``POST /auth/login``) y redirige al frontend con el token.

        Un launch inválido se rechaza sin crear ni loguear a nadie (falla cerrado).

        Sección 5: si ``jwt_secret`` no está configurado en la factory, responde
        JSON (modo retrocompatibilidad de sección 4 — solo tests que no lo pasen).
        """
        factory = _factory(request)
        async with factory() as session:
            try:
                validado = await validar_launch(
                    session,
                    id_token=id_token,
                    state=state,
                    jwks_fetcher=_jwks_fetcher,
                )
            except LaunchInvalidoError as exc:
                codigo = exc.codigo
                # Log de auditoría del rechazo (sin PII: solo el código estable).
                logger.warning("lti_launch_rechazado codigo=%s", codigo)
                http = (
                    status.HTTP_403_FORBIDDEN
                    if codigo == "deployment_no_confiable"
                    else status.HTTP_401_UNAUTHORIZED
                )
                raise HTTPException(status_code=http, detail=codigo) from exc

            # -- Sección 5: JIT provisioning + emisión de sesión ---------------
            if jwt_secret is None:
                # Modo sección 4 (retrocompatibilidad): sin JIT ni sesión.
                return {
                    "ok": True,
                    "sub": validado.claims.get("sub"),
                    "iss": validado.claims.get("iss"),
                }

            try:
                usuario, _creado = await provisionar_o_recuperar_usuario(
                    session,
                    claims=validado.claims,
                    deployment=validado.deployment,
                )
            except LaunchInvalidoError as exc:
                codigo = exc.codigo
                logger.warning("lti_launch_rechazado codigo=%s", codigo)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=codigo
                ) from exc

            # Emitir JWT de sesión propio (mismo emisor que /auth/login — design D4).
            access_token = emitir_jwt_propio(
                usuario,
                secret=jwt_secret,
                issuer=jwt_issuer,
                audience=jwt_audience,
                ttl_seconds=jwt_ttl_seconds,
            )

            # Emitir refresh token persistente en DB.
            db_store = DbRefreshTokenStore(session, ttl_seconds=refresh_ttl_seconds)
            refresh_jti = await db_store.issue_para_usuario(str(usuario.id))

            await session.commit()

        # Redirect al frontend con los tokens en el FRAGMENT (#), NO en la query
        # string. El fragment nunca se envía al servidor: no queda en los logs de
        # Nginx/uvicorn ni en el header Referer de los sub-recursos de la landing.
        # La query string sí se logueaba (formato `combined` de Nginx incluye
        # `$request`) — filtrando un refresh_token bearer válido 7 días. Patrón
        # equivalente al implicit flow de OAuth. El frontend lee de location.hash.
        params = urlencode({
            "access_token": access_token,
            "refresh_token": refresh_jti,
        })
        redirect_url = f"{frontend_url.rstrip('/')}/lti-login#{params}"
        return RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)

    return router
