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
    Boolean,
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

    Campos de datos personales (C-61):
    - ``nombre``, ``apellido``: nullable para compatibilidad con usuarios pre-existentes
      (federados / seed) que no tienen nombre en la DB.
    - ``eliminado_en``: NULL = activo; NOT NULL = baja logica (soft-delete). La fila
      nunca se borra fisicamente para preservar la cadena de custodia de evidencias
      asociadas (regla de dominio #6/#7).
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
    # C-61: datos personales (nullable — compatibilidad con usuarios pre-existentes).
    nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apellido: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # C-61: baja logica (soft-delete). NULL = activo; NOT NULL = dado de baja.
    eliminado_en: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
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


class FotoReferenciaModel(Base):
    """Foto de perfil del alumno — referencia de enrollment (C-56).

    La foto se almacena en el bucket de perfiles (no-WORM, SSE-S3, separado del
    bucket de evidencia WORM). Solo los metadatos viven en la DB: la URL del
    objeto, el hash SHA-256 del contenido (integridad), el bucket y el usuario.

    ``vigente``: solo un registro TRUE por usuario. Al renovar la foto, el
    registro anterior se marca FALSE (``marcar_anteriores_no_vigentes``).
    El ON DELETE CASCADE garantiza que al borrar el usuario, sus fotos desaparecen.
    """

    __tablename__ = "foto_referencia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    uri_storage: Mapped[str] = mapped_column(Text, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EmbeddingReferenciaModel(Base):
    """Embedding biometrico de referencia cifrado at-rest (C-56, D2).

    El vector 128-d del alumno (face-api / MediaPipe) se cifra con Fernet
    (EMBEDDING_ENCRYPTION_KEY) antes de persistirse. La columna ``embedding_cifrado``
    almacena el Fernet token (TEXT opaco); el plaintext NUNCA se persiste.

    Campos de retencion (stub para C-19):
    - ``fecha_expiracion``: NULL = no expira. Politica concreta en C-01/Fase 2.
    - ``eliminado_en``: NULL = vigente; NOT NULL = marcado para eliminacion al egreso.

    ``vigente``: solo un registro TRUE por usuario (el embedding de referencia
    activo). Al renovar, el registro anterior se marca FALSE.
    El ON DELETE CASCADE garantiza que al borrar el usuario, sus embeddings se eliminan.
    """

    __tablename__ = "embedding_referencia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    embedding_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    algoritmo: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="face-api-128d"
    )
    fecha_captura: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_expiracion: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    eliminado_en: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EventoScoreConfigModel(Base):
    """Configuracion del peso de score por tipo de evento (#9, migracion 0011).

    Permite a admin_sistema ajustar en caliente cuanto suma cada tipo de evento al
    score acumulado del examen (0-100), sin redeploy. Los valores por defecto coinciden
    con PESO_SCORE de frontend/src/proctoring/riskWeights.ts: baja=5, media=20,
    alta=50, critica=100. La migracion 0011 ya siembra los 8 tipos del catalogo.

    Constraints (definidos en la migracion):
    - severidad IN ('baseline','baja','media','alta','critica')
    - peso >= 0 AND peso <= 100
    - tipo_evento PK
    """

    __tablename__ = "evento_score_config"

    tipo_evento: Mapped[str] = mapped_column(Text, primary_key=True)
    severidad: Mapped[str] = mapped_column(Text, nullable=False)
    peso: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
