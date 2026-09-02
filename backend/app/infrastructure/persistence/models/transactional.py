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
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
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
    - ``password_hash``: hash bcrypt 12r (passlib). NULL = usuario federado (LTI);
      NOT NULL = usuario con credencial local. Ver migracion 0006 (paso 1).
    - ``auth_provider``: 'jwt' (default) o 'local'. Determina el flujo de login.

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
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    attrs_federados: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # C-55: credencial local (nullable — usuarios federados no tienen password local).
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="jwt"
    )
    # 0059: clave temporal. TRUE = el usuario debe cambiar su contraseña en el
    # próximo login (creado por admin con clave temporal). Se limpia al cambiarla.
    debe_cambiar_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # 0066: override admin de un solo uso para rehacer la referencia biométrica.
    # El alumno no puede rehacerla mientras siga vigente; un admin puede habilitar
    # UNA rehecha (TRUE). Se consume (vuelve a FALSE) al guardar la nueva referencia.
    biometria_rehacer_habilitada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # 0085: lockout de login (pentest — fuerza bruta sin límite de intentos).
    # intentos_fallidos se incrementa en cada 401 y se resetea a 0 en un login
    # exitoso. bloqueado_hasta se fija al alcanzar el máximo configurado
    # (LOGIN_LOCKOUT_MAX_INTENTOS) y bloquea el login mientras esté en el futuro.
    intentos_fallidos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # C-61: datos personales (nullable — compatibilidad con usuarios pre-existentes).
    nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apellido: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # C-61: baja logica (soft-delete). NULL = activo; NOT NULL = dado de baja.
    eliminado_en: Mapped[str | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # 0056: auditoría de cuenta.
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_acceso_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    # C-69: referencia opcional al examen de contenido importado (banco Moodle).
    # NULLABLE: un examen sin contenido es válido. La FK/columna en la DB la
    # provee la migración del modelo de contenido (ver nota de apply C-69).
    examen_contenido_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )


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

    La foto se guarda como BYTEA directamente en Postgres (``foto_bytes``), que
    es como la crea la migración 0008 y como está la tabla en producción y en dev.

    ``vigente``: solo un registro TRUE por usuario. Al renovar la foto, el
    registro anterior se marca FALSE (``marcar_anteriores_no_vigentes``).
    El ON DELETE CASCADE garantiza que al borrar el usuario, sus fotos desaparecen.

    MinIO (pendiente, no borrado)
    -----------------------------
    El diseño original guardaba la foto en un bucket no-WORM y dejaba en la DB
    solo los punteros (``uri_storage``, ``bucket``). Eso lo crea la migración
    0007, de la rama "full", que **no está aplicada en ninguna base viva**: este
    modelo las declaraba igual, así que describía una tabla que no existe y
    cualquier ``select()`` entero reventaba con ``UndefinedColumnError``.

    Cuando MinIO vuelva hay que migrar la tabla PRIMERO y recién ahí descomentar
    las columnas de abajo (y el camino de subida en
    ``application/enrollment/guardar_foto_perfil.py``). Las dos variantes no
    pueden convivir en un mismo modelo: ``foto_bytes`` es NOT NULL.
    """

    __tablename__ = "foto_referencia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    foto_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    # Volver a habilitar junto con la migración que las cree (ver docstring):
    # uri_storage: Mapped[str] = mapped_column(Text, nullable=False)
    # bucket: Mapped[str] = mapped_column(Text, nullable=False)
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


class ConfiguracionSistemaModel(Base):
    """Configuracion global del sistema (singleton versionado, configuracion-sistema-funcional).

    Fila UNICA (PK fija ``id='global'``) con los defaults globales del proctoring que
    hoy viven mock-only en el frontend: umbrales de deteccion, umbral de cola de
    revision, detectores activos, retencion default y el puntero a la version de
    texto de consentimiento vigente.

    Es la fuente de verdad autoritativa server-side (RN-GLB-01, cliente = sensor no
    confiable). ``version`` es un entero monotonico que actua como ETag: cada edicion
    exitosa lo incrementa para que los clientes detecten config rancia. La tabla
    existe IGUAL en full y en activeexam (mismo schema), por eso vive aqui (Base compartida).

    L2.5: estos valores alimentan la PRIORIZACION de la cola de revision; nunca una
    sancion automatica.
    """

    __tablename__ = "configuracion_sistema"

    # Singleton: una sola fila con id fijo 'global'.
    id: Mapped[str] = mapped_column(String(32), primary_key=True, server_default="global")
    # Umbrales de deteccion (unidades internas autoritativas).
    face_absent_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3000")
    multiple_faces_frames: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    gaze_deviation_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.20"
    )
    gaze_sustained_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="2500"
    )
    gaze_fixation_tolerance: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.25"
    )
    # Umbral de cola de revision (0-100): score por encima entra a la cola humana.
    umbral_cola_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="70"
    )
    # Detectores activos (lista de TipoEvento) — JSONB para portabilidad activeexam/full.
    # Default: TODOS los detectores activos (el admin desactiva los que no quiera).
    detectores_activos: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=(
            '["rostro_ausente", "multiples_rostros", "mirada_desviada_sostenida", '
            '"perdida_de_foco", "cambio_pestana", "monitor_adicional", '
            '"salida_pantalla_completa", "copiar_pegar", "corte_conectividad_prolongado"]'
        ),
    )
    # Retencion default en dias (politica concreta en C-19).
    retencion_dias_default: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="365"
    )
    # Retencion de CAPTURAS de proctoring (screenshot_b64), en dias. Distinta de
    # retencion_dias_default (retencion GENERAL de sesion, C-19): esta es
    # especifica del dato mas pesado y sensible (rostro + pantalla del alumno en
    # base64 dentro de Postgres). Default 180 (un cuatrimestre). Minimo 90 dias,
    # validado en dominio (app.domain.retention.policy) y en el endpoint que
    # edita esta config — nunca con un CHECK de base (mensaje entendible).
    retencion_capturas_dias: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="180"
    )
    # Puntero a la version de texto de consentimiento vigente (perfil).
    consent_version_vigente: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="v1"
    )
    # Toggles globales de la rendicion (C-69). Default true = funcion habilitada
    # (compat con el comportamiento previo al toggle).
    # c-78 E-14 (migracion 0095): APAGADO por defecto. `ChatBox` pollea cada 3.5 s
    # en la pantalla de cada alumno: con 100 rindiendo son ~28,6 req/s, el 36% del
    # techo medido en el plan free de Render, gastado en una funcion que la mayoria
    # de los examenes no usa. Se prende desde Configuracion cuando hace falta.
    # Prendido por defecto (migracion 0098, revierte la 0095): el sistema viene
    # con la funcionalidad completa y el techo lo decide la prueba de carga, no
    # un supuesto. Se apaga desde Configuracion si hace falta — es un toggle de
    # runtime, y su valor queda congelado por sesion en `config_snapshot`.
    chat_habilitado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    pausas_habilitadas: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    # Límite de duración de una pausa autorizada, en minutos (C-69). Al vencer, la
    # pausa se reanuda sola (evita usar la pausa para hacer tiempo / copiarse).
    pausa_max_min: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
    # Cantidad máxima de pausas (aprobada+finalizada) por sesión (C-76 bloque 4).
    # Se consume al APROBAR, no al solicitar: el alumno siempre puede pedir.
    pausas_max_por_sesion: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="2"
    )
    # Version monotonica (ETag). Cada edicion exitosa la incrementa.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ConsentimientoPerfilModel(Base):
    """Consentimiento de perfil del usuario, APPEND-ONLY (Ley 25.326, GAP #2).

    Atado a ``usuario_id``; cada otorgamiento/revocacion/via-alternativa inserta una
    fila nueva (nunca se actualiza), de modo que el historico es demostrable. El
    estado vigente es la fila mas reciente por ``usuario_id``.

    - ``version_texto`` + ``hash_texto``: que texto exacto consintio el usuario.
    - ``hash_registro``: SHA-256 de ``usuario_id|version_texto|timestamp|estado`` para
      integridad del registro.

    La tabla existe IGUAL en full y activeexam. Eliminacion al egreso atada al motor de
    retencion/DSR (difiere ante holds).
    """

    __tablename__ = "consentimiento_perfil"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_texto: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_texto: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    estado: Mapped[str] = mapped_column(String(32), nullable=False)
    hash_registro: Mapped[str] = mapped_column(String(64), nullable=False)


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


class ConsentTextoVersionModel(Base):
    """Version del texto de consentimiento informado (Ley 25.326, C-08 ext).

    Tabla APPEND-ONLY por semantica: version es PK (string), el texto NUNCA muta.
    Misma version => mismo hash; texto nuevo => nueva version.

    El campo ``bloques`` almacena una lista de dicts {titulo, cuerpo} (los cinco
    bloques informativos obligatorios de RN-CO-01). El ``hash_texto`` es el SHA-256
    deterministico de version+bloques (JSON canonico: sorted keys, sin whitespace).

    El admin publica versiones; los estudiantes deben re-consentir cuando la
    version vigente (``configuracion_sistema.consent_version_vigente``) cambia.
    """

    __tablename__ = "consent_texto_version"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    bloques: Mapped[list] = mapped_column(JSONB, nullable=False)
    hash_texto: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class MoodleCredencialModel(Base):
    """Credencial de servicio de Moodle (singleton, migracion 0047).

    UNA fila (id=1): es la credencial INSTITUCIONAL del campus.

    DESDE C-73 §10 ES EL RESPALDO, NO LA VIA PRINCIPAL. La nota la devuelve el
    DOCENTE a cargo de la comision con SU credencial personal
    (`moodle_credencial_docente`), porque escribir todo con una cuenta de servicio
    deja la libreta sin saber quien puso cada nota y obliga a replicar de este lado
    los permisos que Moodle ya sabe imponer. Esta credencial se usa cuando la
    comision no tiene docente asignado o el docente todavia no cargo la suya: la nota
    sale igual, firmada como institucional (degradacion, no bloqueo).

    NO guarda curso ni actividad de destino: eso es de cada examen
    (`examen_contenido.moodle_courseid`/`moodle_cmid`). Un destino global convertia
    "examen sin destino" en "nota escrita en la libreta de otra materia" (migracion
    0048). `component` si es un default institucional, sobreescribible por examen.

    ``token_cifrado`` guarda el token de Web Services cifrado con Fernet
    (``SecretCipher``), NUNCA en claro. La API jamas lo devuelve: para que el admin
    reconozca cual cargo se expone ``token_pista`` (ultimos 4 caracteres).

    Mientras la tabla este vacia, el resolver cae a las variables de entorno
    (MOODLE_*), asi que un despliegue existente sigue funcionando sin tocar nada.
    """

    __tablename__ = "moodle_credencial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    token_cifrado: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_pista: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    component: Mapped[str] = mapped_column(
        String(50), nullable=False, default="mod_assign"
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_por: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # C-73 §10 (migracion 0050): shortname del servicio externo del campus. Hace falta
    # para canjear contrasena por token (`login/token.php?service=`), que es la unica
    # forma de obtener un token acotado a las funciones que ese servicio declara.
    service_shortname: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )


class MoodleCredencialDocenteModel(Base):
    """Credencial personal de Moodle de UN docente (migracion 0050, C-73 §10).

    Con esta credencial se devuelven las notas de las comisiones que ese docente tiene
    a cargo, de modo que en la libreta la nota figure puesta POR EL y que sea Moodle
    —no nuestro codigo— quien impida escribir donde no da clase.

    NO GUARDA LA CONTRASENA, y el esquema no tiene donde hacerlo. La contrasena se usa
    UNA vez para canjearla por un token en `login/token.php` y se descarta. Guardar el
    token es ademas mas estable: los tokens de Moodle sobreviven al cambio de
    contrasena (CVE-2016-7038), asi que rotar la clave no rompe la sincronizacion.

    ``estado='caida'`` marca que Moodle respondio `invalidtoken` (revocado o vencido).
    No se borra el token: se marca, para poder avisarle a la persona en vez de fallar
    en silencio.
    """

    __tablename__ = "moodle_credencial_docente"

    usuario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("usuario.id", ondelete="CASCADE"),
        primary_key=True,
    )
    moodle_username: Mapped[str] = mapped_column(String(255), nullable=False)
    token_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    token_pista: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="activa"
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_uso_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # C-73 ext (migr 0051): URL del campus per-docente. NULL = usar la institucional.
    base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
