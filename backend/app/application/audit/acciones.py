"""Catálogo canónico de acciones auditadas (dominio CRÍTICO).

Fuente ÚNICA de verdad de TODO lo que se registra en el audit log. Es un StrEnum:
cada miembro ES su string, así se usa directo en ``registrar_seguro(accion=...)`` y
queda retro-compatible con los literales previos. Organizado por categoría.
"""

from __future__ import annotations

from enum import StrEnum


class AccionAuditoria(StrEnum):
    """Acciones auditadas del sistema, agrupadas por dominio."""

    # ── Usuarios ─────────────────────────────────────────────────────────
    USUARIO_ALTA = "user.create"
    USUARIO_EDICION = "user.update"
    USUARIO_BAJA = "user.delete"
    USUARIO_REACTIVACION = "user.reactivate"

    # ── Catálogo académico (materias / comisiones / exámenes) ────────────
    MATERIA_ALTA = "materia.create"
    MATERIA_EDICION = "materia.update"
    MATERIA_BAJA = "materia.delete"
    MATERIA_ACTIVACION = "materia.set_activa"
    COMISION_ALTA = "comision.create"
    COMISION_EDICION = "comision.update"
    COMISION_BAJA = "comision.delete"
    COMISION_ACTIVACION = "comision.set_activa"
    EXAMEN_IMPORTACION = "examen.import"
    EXAMEN_MOODLE_TARGET = "examen.moodle_target"
    EXAMEN_CONFIG_ACTUALIZACION = "examen.config_update"
    EXAMEN_SELECCION_PREGUNTAS = "examen.seleccion_preguntas"

    # ── Write-back de nota a Moodle (cadena de custodia — regla dura #6, L2.5) ──
    # La sincronización manual del admin ESCRIBE una nota académica real en el
    # campus. Debe quedar trazada (quién sincronizó qué examen y con qué resultado).
    MOODLE_SYNC = "moodle.sync"

    # ── Inscripciones ────────────────────────────────────────────────────
    INSCRIPCION_ALTA = "inscripcion.create"
    INSCRIPCION_BAJA = "inscripcion.delete"

    # ── Configuración del sistema ────────────────────────────────────────
    CONFIG_ACTUALIZACION = "config_update"

    # ── Consentimiento ───────────────────────────────────────────────────
    CONSENT_OTORGADO = "consent.otorgado"
    CONSENT_VIA_ALTERNATIVA = "consent_alternative_chosen"

    # ── Biometría / enrolamiento ─────────────────────────────────────────
    BIOMETRIA_VERIFICACION = "biometria.verificacion"
    ENROLLMENT_RENOVACION = "enrollment.embedding_referencia.renovacion"

    # ── Evidencia y cadena de custodia ───────────────────────────────────
    EVIDENCIA_ACCESO = "acceso_evidencia"
    EVIDENCIA_DEPOSITO = "deposito_evidencia"
    EVIDENCIA_MANIPULACION = "manipulacion_detectada"
    EVIDENCIA_FIRMA_MAESTRA = "firma_maestra_y_reinferencia"

    # ── Retención / eliminación ──────────────────────────────────────────
    RETENCION_SESION_ELIMINADA = "retention.session.deleted"
    RETENCION_SESION_DIFERIDA = "retention.session.hold_deferred"
    RETENCION_BIOMETRIA_EGRESO = "retention.biometric.egress"

    # ── Derechos del titular (DSR) ───────────────────────────────────────
    DSR_ACCESO_INFORME = "derecho_acceso.informe_devolucion"


# Prefijos de acciones DINÁMICAS (llevan un sufijo variable). Se componen así:
#   f"{PREFIJO_REVISION_DECISION}{decision}" -> "review.decision.caso_abierto"
#   f"{PREFIJO_VERIFY_CHAIN}{status}"        -> "verify_chain.ok"
#   f"{PREFIJO_DSR}{tipo}"                   -> "dsr.rectification"
PREFIJO_REVISION_DECISION = "review.decision."
PREFIJO_VERIFY_CHAIN = "verify_chain."
PREFIJO_DSR = "dsr."
