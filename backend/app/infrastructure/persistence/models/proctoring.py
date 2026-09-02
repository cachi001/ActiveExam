"""Modelos ORM del modulo activeexam de proctoring (SQLAlchemy).

Tablas: proctoring_session, proctoring_event, proctoring_biometria.
Migración: 0005_proctoring_activeexam.py (branch 'activeexam', depends_on=None).

PRODUCCION:
- screenshot_b64: dato sensible (Ley 25.326). Mover a MinIO/S3 WORM con cifrado
  at-rest y politica de retencion automatica (90 dias o fin de hold disciplinario).
- embedding: dato sensible (Ley 25.326); cifrar con KMS antes de persistir; purgar
  al egreso del estudiante (DD-13, DSR).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import false, func

from app.infrastructure.persistence.base import Base


class ProctoringSessionModel(Base):
    """Sesion de proctoring activeexam. Aditiva — no reemplaza SesionModel de produccion."""

    __tablename__ = "proctoring_session"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="UUID generado por Postgres (gen_random_uuid)",
    )
    modo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'test' o 'examen'",
    )
    exam_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="ID del examen (referencia externa, no FK a tabla de produccion)",
    )
    etiqueta: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Etiqueta libre para identificar la sesion",
    )
    # C-69 (activeexam, migration 0027): vinculo REAL con el examen de contenido importado
    # de Moodle XML. NULLABLE — una sesion de prueba (modo 'test') o un examen sin
    # contenido asociado sigue siendo valida. FK ON DELETE SET NULL: borrar el
    # contenido del catalogo NO borra la sesion ni su evidencia (cadena de custodia,
    # L2.5) — solo se pierde la referencia. La tabla `examen` (config) no existe en
    # activeexam; `examen_contenido` y `proctoring_session` SI coexisten, por eso el
    # vinculo vive aca.
    examen_contenido_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("examen_contenido.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK a examen_contenido(id). NULL = sesion sin contenido vinculado.",
    )
    creada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finalizada_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Ancla del timer de examen (migración 0067). Momento en que el alumno abre las
    # preguntas por primera vez, seteado idempotente server-side en el primer fetch
    # de rendición. NO es `creada_en`: la sesión puede crearse anticipadamente en el
    # consentimiento/biometría, y anclar el reloj ahí le descontaría esos minutos al
    # examen. NULL hasta el primer fetch (el timer cae a `creada_en` como fallback).
    # INMUTABLE una vez seteado (a prueba de F5: relecturas devuelven el original).
    examen_iniciado_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # C-69 (migration 0033): identidad del alumno persistida al CREAR la sesion.
    # Antes la identidad se extraia del JWT recien en finalize (write-back). El
    # enforcement server-side de intentos por examen necesita contar las sesiones
    # finalizadas de un alumno, por eso se persiste aca. NULLABLE: las sesiones de
    # prueba (modo 'test') o las creadas antes de esta migracion quedan con NULL.
    # OJO CON EL NOMBRE: `alumno_idnumber` NO guarda un idnumber de Moodle.
    # Guarda `principal.username`, que para quien entra por el campus vale
    # "lti:{deployment_id}:{sub}". El nombre viene de Moodle, donde `idnumber` es
    # el campo de la clave institucional, y quedó de un plan que el campus real no
    # sostuvo: ahí los alumnos tienen `idnumber: None` (verificado en c-78).
    #
    # Acá NO se maneja legajo. Su uso real hoy es de clave de join contra
    # `usuario.username` (write-back y conteo de intentos). Renombrarla a
    # `alumno_username` es deuda pendiente: son 118 referencias y cae sobre el
    # camino de la nota, así que no se toca en caliente.
    alumno_idnumber: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="username del alumno (NO es un idnumber de Moodle). NULL = sin identidad.",
    )
    alumno_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Email del alumno (fallback de identidad). NULL = sin email.",
    )

    # migration 0102: el docente probando su propio examen. La marca la pone el
    # SERVIDOR segun el rol de quien crea la sesion, nunca el cliente (regla dura
    # #6): si viniera del body, un alumno pediria que su rendicion no cuente.
    # Estas sesiones quedan fuera de notas, estadisticas y write-back.
    es_prueba: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
        default=False,
        comment="Rendicion de prueba del staff: no cuenta como intento real.",
    )

    # migration 0083: foto de la config del sistema (umbral_cola_revision +
    # scoring_weights/severidades/desactivados) vigente al CREAR la sesion (no al
    # reanudarla). El scoring de ESTA sesion usa esta foto en vez de la config viva,
    # asi un cambio de config posterior no afecta retroactivamente examenes ya
    # arrancados. NULL = sesion anterior a este change o config no disponible al
    # crear -> cae a la config viva (degradacion, comportamiento previo).
    config_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment=(
            "Foto de umbral/pesos de scoring al crear la sesion. NULL = usar "
            "config viva (sesion pre-migracion o config no disponible al crear)."
        ),
    )

    # C-15 (tarea 3.3): cierre FORZADO por el proctor. Operativo, NO disciplinario
    # (regla dura #5: el sistema nunca sanciona — esto solo CIERRA la sesion). El
    # cierre forzado tambien setea finalizada_en; estas 3 columnas son el audit trail
    # persistente (quien, cuando, por que) — patron "la fila ES el audit log" del activeexam,
    # que no tiene tabla audit_log persistente. INMUTABLE una vez seteado.
    cierre_forzado_en: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp del cierre forzado por el proctor. NULL = no fue cierre forzado.",
    )
    cierre_forzado_por: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Subject del JWT del proctor que forzo el cierre (audit trail).",
    )
    cierre_forzado_motivo: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Motivo operativo del cierre forzado (NO veredicto disciplinario).",
    )

    # c-16: decision terminal del revisor, UN SOLO PASO (activeexam, migration 0013;
    # modelo colapsado a 3 estados — el owner del proyecto rechazo explicitamente
    # el modelo de dos fases con `caso_abierto`: "no existe el caso abierto,
    # nunca dije que era un estado y no lo va a ser"). NULLABLE — None = sin
    # revisar todavia. Una vez seteada (aprobado/anulado), es INMUTABLE (RN-RV-07).
    decision: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="'pendiente' | 'aprobado' | 'anulado' | NULL"
    )
    decision_actor: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Subject del JWT del revisor al momento de decidir"
    )
    decision_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decision_motivo: Mapped[str | None] = mapped_column(
        String(1024), nullable=True,
        comment="Motivo del veredicto. Obligatorio no vacio cuando decision='anulado' (D11, RN-RV-06)",
    )
    decision_evidencia_ids: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True,
        comment=(
            "Lista ESTRUCTURADA de proctoring_event.id elegidos por el revisor "
            "como evidencia del veredicto (no texto libre). Obligatoria y no "
            "vacia cuando decision='anulado'; filtra las capturas que ve el "
            "alumno en su informe de devolucion (D12)."
        ),
    )

    # c-76 tarea 14 (migration 0081): soft-hide ADMINISTRATIVO del panel de
    # resultados — oculta la fila del listado por default sin borrar nada.
    # Ortogonal a `decision` (veredicto humano de fraude, RN-RV) y a
    # `estado_entrega` (que se DERIVA, no se persiste). NUNCA sanciona ni
    # deja de sancionar nada por si solo: es solo visibilidad en la UI.
    archivado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Soft-hide administrativo de la fila en el panel de resultados",
    )

    eventos: Mapped[list[ProctoringEventModel]] = relationship(
        back_populates="sesion",
        cascade="all, delete-orphan",
        order_by="ProctoringEventModel.ts_backend",
    )
    biometria: Mapped[ProctoringBiometriaModel | None] = relationship(
        back_populates="sesion",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ProctoringEventModel(Base):
    """Evento de deteccion con screenshot e informacion de re-inferencia server-side.

    PRODUCCION:
    - screenshot_b64: dato sensible (Ley 25.326). Se persiste CIFRADO at-rest
      (`cipher.encrypt` en event_service) cuando hay cipher configurado.
      El deposito WORM en MinIO ya existe (c-77) y es ADICIONAL: nunca reemplaza
      esta columna, que sigue siendo la fuente de verdad. Pendiente real: la
      politica de retencion automatica.
    - screenshot_sha256: integridad liviana (SHA-256 del contenido base64).
      PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada).
    - face_count_servidor / veredicto_reinferencia: producidos por MediaPipe server-side
      (mismo motor que el cliente, D8). L2.5: el veredicto NO sanciona; solo enriquece
      la evidencia que ve el revisor humano.
    """

    __tablename__ = "proctoring_event"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctoring_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ej: 'FACE_ABSENT', 'MULTIPLE_FACES', 'GAZE_DEVIATION'",
    )
    severidad: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="'bajo' | 'medio' | 'alto' | 'critico'",
    )
    ts_cliente: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp reportado por el cliente (no confiable, sensor no verificado)",
    )
    ts_backend: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp del servidor (autoritativo)",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Datos adicionales del evento (libre)",
    )
    # LEGACY (c-78): las filas escritas antes de la migracion 0097 tienen la
    # captura aca, como base64 cifrado. Las nuevas van a `screenshot_bin`. El
    # camino de lectura mira primero el binario y cae aca si esta vacio.
    screenshot_b64: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "LEGACY: screenshot en base64 cifrado at-rest. Las filas nuevas usan "
            "screenshot_bin (44% menos espacio). Se conserva para leer el historico."
        ),
    )
    # --- Captura binaria (c-78, migracion 0097) ----------------------------
    # Medido con pg_column_size: la misma captura de 85 KB ocupaba 151.224 bytes
    # como base64 cifrado y ocupa 85.065 aca. Era doble expansion base64 (el
    # data URL, y despues el token Fernet que tambien es base64), y TOAST no la
    # comprime porque lo cifrado es incompresible.
    screenshot_bin: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment=(
            "Screenshot CIFRADO at-rest en binario (dato sensible Ley 25.326). "
            "Token Fernet sin su base64 externo. El deposito WORM (c-77) es adicional."
        ),
    )
    screenshot_prefijo: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment=(
            "Prefijo del data URL original ('data:image/jpeg;base64'), guardado TAL "
            "CUAL para que la reconstruccion sea byte a byte y screenshot_sha256 "
            "siga verificando. NULL si el cliente mando base64 pelado."
        ),
    )
    # PRODUCCION: cadena de custodia completa (HMAC clave maestra + WORM + firma encadenada)
    screenshot_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hex del screenshot (integridad liviana, D9). NULL si no hay screenshot.",
    )
    # --- Primera capa de la cadena de custodia (c-78, migracion 0096) -------
    # Hasta c-78 el cliente mandaba su hash y el servicio lo TIRABA: la regla
    # dura #6 ("el backend re-hashea lo que manda el cliente") no se cumplia.
    screenshot_sha256_cliente: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "SHA-256 hex de la imagen segun el CLIENTE (sensor no confiable). "
            "Se guarda tal cual llego, sea verdad o no: es parte de la evidencia."
        ),
    )
    custodia_cliente: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="no_verificable",
        comment=(
            "'coincide' | 'discrepancia' | 'no_verificable'. L2.5: una discrepancia "
            "es senal para el revisor humano, NUNCA una sancion automatica."
        ),
    )
    face_count_cliente: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Conteo de rostros reportado por el cliente (campo explicito del body)",
    )
    face_count_servidor: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Conteo de rostros re-detectado server-side con MediaPipe (mismo motor "
            "que el cliente, D8). NULL si veredicto es 'no_evaluado'."
        ),
    )
    veredicto_reinferencia: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="no_evaluado",
        comment="'coincide' | 'discrepancia' | 'no_evaluado'. L2.5: nunca sanciona.",
    )
    # --- Deposito WORM (c-77, migracion 0082) ------------------------------
    # NULL siempre que MinIO no este configurado (Render sin VPS, caso actual).
    # screenshot_b64 en Postgres sigue siendo la fuente de verdad — el deposito
    # WORM es ADICIONAL, no un reemplazo (decision del dueño, ver tasks.md).
    worm_object_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Key del objeto en el bucket WORM. NULL si MinIO no esta configurado.",
    )
    worm_uri: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URI completa del deposito WORM (endpoint/bucket/object_key).",
    )
    worm_retain_until: Mapped[str | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="retain_until del Object Lock Compliance aplicado al depositar.",
    )

    sesion: Mapped[ProctoringSessionModel] = relationship(back_populates="eventos")


class ProctoringBiometriaModel(Base):
    """Resultado biometrico de la sesion de proctoring activeexam.

    PRODUCCION:
    - embedding: dato sensible (Ley 25.326, ISO 30107-3). En demo se persiste en
      texto plano solo si el cliente lo envia (campo nullable). Para produccion:
      cifrar con KMS antes de persistir; purgar al egreso del estudiante (DD-13, DSR).
    """

    __tablename__ = "proctoring_biometria"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("proctoring_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    liveness_ok: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="True si el liveness challenge paso",
    )
    retos_resueltos: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="Lista de retos de liveness resueltos",
    )
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "Embedding facial. PRODUCCION: dato sensible (Ley 25.326); "
            "cifrar con KMS antes de persistir; purgar al egreso (DD-13, DSR)."
        ),
    )
    resultado: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'verificado' | 'rechazado' | 'pendiente'",
    )
    registrada_en: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sesion: Mapped[ProctoringSessionModel] = relationship(back_populates="biometria")
