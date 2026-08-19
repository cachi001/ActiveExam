"""Modelos ORM del Tool Provider LTI 1.3 (C-75).

Tres tablas nuevas (migraciones 0063/0064/0065):
- ``LtiDeploymentConfiableModel``: allowlist de emisores de confianza + mapeo
  contexto de curso → comisión (design D2). Falla cerrado: sin filas, todo launch
  se rechaza.
- ``LtiNonceModel``: anti-replay del flujo OIDC (nonce/state con TTL, design D5).
- ``LtiToolKeyModel``: par de claves RS256 de ActiveExam-como-Tool; la privada va
  cifrada (Fernet/``SecretCipher``), la pública como JWK para el JWKS (design D3).

El usuario provisionado JIT reusa ``UsuarioModel`` con ``auth_provider='lti'`` — no
hay tabla de usuarios LTI (design D1).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class LtiDeploymentConfiableModel(Base):
    """Emisor LTI de confianza + mapeo de su contexto de curso a una comisión.

    La confianza es doble: el ``id_token`` debe estar bien firmado (contra
    ``jwks_uri``) Y su ``(iss, deployment_id, client_id)`` debe existir acá con
    ``activo=True``. ``comision_id`` NULL = launch válido pero sin matriculación
    automática (design D2).
    """

    __tablename__ = "lti_deployment_confiable"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    iss: Mapped[str] = mapped_column(Text, nullable=False)
    deployment_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    jwks_uri: Mapped[str] = mapped_column(Text, nullable=False)
    context_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    comision_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("comision.id", ondelete="SET NULL"),
        nullable=True,
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class LtiNonceModel(Base):
    """Nonce/state de un login OIDC de LTI, con TTL corto (anti-replay, design D5).

    Se crea en ``/lti/login`` y se consume en ``/lti/launch``. ``consumido_en``
    NULL = usable; NOT NULL = ya usado (cualquier reuso se rechaza). Se limpia por
    TTL con ``expira_en`` (índice). No referencia usuario: vive antes de saber quién
    es el alumno.
    """

    __tablename__ = "lti_nonce"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    nonce: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    iss: Mapped[str] = mapped_column(Text, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    consumido_en: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class LtiProvisioningPendienteModel(Base):
    """Confirmacion de alta pendiente (migracion 0084, primer ingreso LTI).

    Un launch que resultaria en una cuenta NUEVA no se auto-provisiona ni
    loguea directo: se guardan acá los claims ya validados (firma/nonce/aud/
    exp verificados en ``/lti/launch``) y se redirige al frontend a una
    pantalla de confirmacion. ``POST /lti/confirmar-provisioning`` reusa estos
    claims (el id_token original ya se consumio via nonce, no se puede
    re-validar) para crear la cuenta recien cuando el usuario confirma.

    ``usado_en`` NULL = pendiente; NOT NULL = ya consumido (uso único).
    Reingresos (cuenta LTI ya existente) NUNCA pasan por acá — siguen
    logueando directo, sin fricción.
    """

    __tablename__ = "lti_provisioning_pendiente"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    deployment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("lti_deployment_confiable.id", ondelete="CASCADE"),
        nullable=False,
    )
    claims: Mapped[dict] = mapped_column(JSONB, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expira_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    usado_en: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class LtiToolKeyModel(Base):
    """Par de claves RS256 de ActiveExam-como-Tool (design D3).

    ``clave_privada_cifrada`` = PEM de la RSA privada, cifrado con Fernet
    (``SecretCipher``); NUNCA en claro. ``clave_publica_jwk`` = JWK público
    (kid/kty/n/e) servido tal cual en ``GET /lti/jwks``. Rotación: varias filas,
    ``activo`` en la vigente para firmar.
    """

    __tablename__ = "lti_tool_key"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    kid: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    clave_privada_cifrada: Mapped[str] = mapped_column(Text, nullable=False)
    clave_publica_jwk: Mapped[dict] = mapped_column(JSONB, nullable=False)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
