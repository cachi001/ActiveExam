"""Modelos ORM de las entidades transaccionales (PostgreSQL).

Mapea Usuario, Examen, Sesion, Asignacion, Consentimiento, Embedding, Evidencia y
Caso disciplinario (`04`), con las cardinalidades del ERD (FKs + tabla de union
Asignacion). El ``estado`` de Sesion usa un ENUM nativo de Postgres
(``estado_sesion``) -> la base rechaza valores fuera del enum aun por fuera de la
aplicacion (D3, capability session-lifecycle-enum).

El ENUM se crea en la migracion 002 con ``create_type=False`` aqui para que el
control del ciclo de vida del tipo lo lleve la migracion (expand/contract), no la
metadata declarativa.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.persistence.base import Base


class EstadoSesionDB(str, enum.Enum):
    """Replica de ``app.domain.entities.session.EstadoSesion`` para el mapeo ORM.

    Se mantiene en infraestructura (no se importa el enum de dominio en el modelo
    ORM para no atar la forma de persistencia a la del dominio); ambos comparten
    los mismos valores del ciclo de vida (`04` Sesion)."""

    INICIADA = "iniciada"
    ACTIVA = "activa"
    FINALIZADA = "finalizada"
    FLAGGEADA = "flaggeada"
    CERRADA = "cerrada"


# Tipo ENUM nativo de Postgres. ``create_type=False``: el CREATE TYPE lo hace la
# migracion 002 (control expand/contract del ciclo de vida del tipo).
estado_sesion_enum = SAEnum(
    EstadoSesionDB,
    name="estado_sesion",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class UsuarioModel(Base):
    """Usuario provisionado JIT desde el IdP (`04` Usuario).

    Campos de auth local (C-55):
    - ``password_hash``: hash bcrypt 12r (passlib). NULL = usuario federado Keycloak;
      NOT NULL = usuario con credencial local. Ver migracion 0006 (paso 1).
    - ``auth_provider``: 'keycloak' (default) o 'local'. Determina el flujo de login.
    """

    __tablename__ = "usuario"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    id_institucional: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    attrs_federados: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # C-55: credencial local (nullable — usuarios Keycloak no tienen password local).
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="keycloak"
    )


class ExamenModel(Base):
    """Examen configurado por administracion (`04` Examen)."""

    __tablename__ = "examen"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    umbral_score: Mapped[float] = mapped_column(Float, nullable=False)
    parametros: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    detectores: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    ventana: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    retencion: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class SesionModel(Base):
    """Sesion (entidad central). ``estado`` restringido al ENUM nativo (D3)."""

    __tablename__ = "sesion"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id"), nullable=False
    )
    exam_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("examen.id"), nullable=False
    )
    estado: Mapped[EstadoSesionDB] = mapped_column(
        estado_sesion_enum, nullable=False, server_default=EstadoSesionDB.INICIADA.value
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clave_sesion: Mapped[str] = mapped_column(String(255), nullable=False)
    creada_en: Mapped[str] = mapped_column(server_default=func.now(), nullable=False)
    actualizada_en: Mapped[str] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    usuario: Mapped[UsuarioModel] = relationship()
    examen: Mapped[ExamenModel] = relationship()


class AsignacionModel(Base):
    """Tabla de union proctor↔examen (relacion *—*, `04` Asignacion)."""

    __tablename__ = "asignacion"
    __table_args__ = (
        UniqueConstraint("proctor_id", "exam_id", name="proctor_exam"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    proctor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id"), nullable=False
    )
    exam_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("examen.id"), nullable=False
    )


class ConsentimientoModel(Base):
    """Consentimiento INMUTABLE: acuse con hash (`04`, D5). Sin path de update en
    el repositorio; la migracion 002 puede reforzar con un trigger anti-update."""

    __tablename__ = "consentimiento"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id"), nullable=False
    )
    exam_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("examen.id"), nullable=False
    )
    version_texto: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[str] = mapped_column(server_default=func.now(), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class EmbeddingModel(Base):
    """Embedding facial CIFRADO at-rest (`04`, SU-08, D5).

    ``vector_cifrado`` es ``BYTEA`` (ciphertext del KMS), NUNCA texto plano. La
    columna nombra explicitamente que esta cifrada para evitar uso accidental en
    claro. Eliminable al egreso del estudiante (DD-13)."""

    __tablename__ = "embedding"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id"), nullable=False
    )
    vector_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    fecha: Mapped[str] = mapped_column(server_default=func.now(), nullable=False)


class EvidenciaModel(Base):
    """Evidencia con cadena de custodia (`04` Evidencia)."""

    __tablename__ = "evidencia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sesion.id"), nullable=False
    )
    uri_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    hash_cliente: Mapped[str | None] = mapped_column(String(128), nullable=True)
    firma_cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_backend: Mapped[str | None] = mapped_column(String(128), nullable=True)
    firma_maestra: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_reinferencia: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class CasoDisciplinarioModel(Base):
    """Caso disciplinario con hold de retencion (`04`)."""

    __tablename__ = "caso_disciplinario"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sesion.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String(64), nullable=False)
    refs_evidencia: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    decisiones: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    vinculo_externo: Mapped[str | None] = mapped_column(Text, nullable=True)
    hold: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")


class RefreshTokenModel(Base):
    """Refresh tokens persistentes del provider JWT propio (C-55).

    ``rotado_en IS NULL`` = vigente; ``rotado_en IS NOT NULL`` = ya rotado.
    La rotacion detecta reuso de un token ya rotado (-> 401, defensa en profundidad).
    El ON DELETE CASCADE garantiza que al borrar un usuario sus tokens caducan.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    jti: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    rotado_en: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
