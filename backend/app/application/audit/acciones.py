"""Catálogo canónico de acciones auditadas (dominio CRÍTICO).

Fuente ÚNICA de verdad de TODO lo que se registra en el audit log. Es un StrEnum:
cada miembro ES su string, así se usa directo en ``registrar_seguro(accion=...)`` y
queda retro-compatible con los literales previos. Organizado por categoría.
"""

from __future__ import annotations

from enum import StrEnum


class ModuloAuditoria(StrEnum):
    """Módulos de dominio para filtrar el audit log en la UI."""

    USUARIOS = "USUARIOS"
    MATERIAS = "MATERIAS"
    EXAMENES = "EXAMENES"
    SESIONES = "SESIONES"
    CONSENTIMIENTO = "CONSENTIMIENTO"
    BIOMETRIA = "BIOMETRIA"
    EVIDENCIA = "EVIDENCIA"
    REVISION = "REVISION"
    MOODLE = "MOODLE"
    CONFIGURACION = "CONFIGURACION"


# Etiqueta legible por módulo — fuente ÚNICA que consume tanto el export a
# Excel/PDF como el endpoint de catálogo (GET /admin/audit-catalogo) que puebla
# el filtro de Auditoría en el frontend. Si se agrega un ModuloAuditoria nuevo
# y no se le agrega label acá, el filtro lo muestra con su valor crudo (fallback
# seguro) en vez de romper — pero conviene completarlo.
MODULO_LABELS: dict[ModuloAuditoria, str] = {
    ModuloAuditoria.USUARIOS: "Usuarios",
    ModuloAuditoria.MATERIAS: "Materias",
    ModuloAuditoria.EXAMENES: "Exámenes",
    ModuloAuditoria.SESIONES: "Sesiones",
    ModuloAuditoria.CONSENTIMIENTO: "Consentimiento",
    ModuloAuditoria.BIOMETRIA: "Biometría",
    ModuloAuditoria.EVIDENCIA: "Evidencia",
    ModuloAuditoria.REVISION: "Revisión",
    ModuloAuditoria.MOODLE: "Moodle",
    ModuloAuditoria.CONFIGURACION: "Configuración",
}


class EntidadAuditoria(StrEnum):
    """Tipo de entidad de dominio afectada por la acción auditada.

    Permite navegar al detalle de la entidad desde la pantalla de Auditoría
    (combinado con ``entidad_id``).
    """

    USUARIO = "USUARIO"
    MATERIA = "MATERIA"
    COMISION = "COMISION"
    EXAMEN = "EXAMEN"
    INSCRIPCION = "INSCRIPCION"
    SESION = "SESION"
    CONSENTIMIENTO = "CONSENTIMIENTO"
    BIOMETRIA = "BIOMETRIA"
    EVIDENCIA = "EVIDENCIA"
    CONFIGURACION = "CONFIGURACION"
    SISTEMA = "SISTEMA"


class TipoAccionAuditoria(StrEnum):
    """Tipo de acción simplificado para filtrado en la UI (cuatro valores canónicos).

    El campo ``accion`` existente conserva el detalle dot-notation (user.create,
    materia.delete…); este enum es la capa de clasificación para los filtros.
    """

    CREAR = "CREAR"
    EDITAR = "EDITAR"
    ELIMINAR = "ELIMINAR"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"


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
    # C-73 §9: quién queda a cargo de la comisión decide quién devuelve la nota a
    # Moodle y qué exámenes puede tocar ese docente. Se audita como cambio sensible.
    COMISION_DOCENTE = "comision.set_docente"
    EXAMEN_IMPORTACION = "examen.import"
    EXAMEN_MOODLE_TARGET = "examen.moodle_target"
    EXAMEN_CONFIG_ACTUALIZACION = "examen.config_update"
    EXAMEN_SELECCION_PREGUNTAS = "examen.seleccion_preguntas"

    # ── Write-back de nota a Moodle (cadena de custodia — regla dura #6, L2.5) ──
    # La sincronización manual del admin ESCRIBE una nota académica real en el
    # campus. Debe quedar trazada (quién sincronizó qué examen y con qué resultado).
    MOODLE_SYNC = "moodle.sync"

    # ── Credencial PERSONAL de Moodle del docente (C-73 §13) ──────────────
    # Distinta de la config institucional del campus (modulo=CONFIGURACION,
    # ver CONFIG_ACTUALIZACION): esto es cada docente conectando/renovando SU
    # propia cuenta. Reemplaza el string suelto "moodle_credencial_update" (guion
    # bajo, sin modulo — quedaba invisible al filtrar Auditoría por MOODLE).
    MOODLE_CREDENCIAL_CONECTAR = "moodle_credencial.conectar"
    MOODLE_CREDENCIAL_DESCONECTAR = "moodle_credencial.desconectar"
    MOODLE_CREDENCIAL_RENOVAR = "moodle_credencial.renovar"
    #: Umbral de intentos fallidos SEGUIDOS alcanzado (IntentosFallidosTracker,
    #: en memoria — no hay tabla de intentos). Señal de "alguien está probando
    #: contraseñas", no un registro de cada fallo individual.
    MOODLE_CREDENCIAL_INTENTOS_FALLIDOS = "moodle_credencial.intentos_fallidos"

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
#   f"{PREFIJO_REVISION_DECISION}{decision}" -> "review.decision.anulado"
#   f"{PREFIJO_VERIFY_CHAIN}{status}"        -> "verify_chain.ok"
#   f"{PREFIJO_DSR}{tipo}"                   -> "dsr.rectification"
PREFIJO_REVISION_DECISION = "review.decision."
PREFIJO_VERIFY_CHAIN = "verify_chain."
PREFIJO_DSR = "dsr."


def modulo_de_accion(accion: str | None) -> str | None:
    """Deriva el módulo de auditoría a partir del prefijo de la ``accion``.

    Fuente ÚNICA de la clasificación accion → módulo. Se usa como FALLBACK en el
    ``append`` del repositorio: cuando un caller construye el ``AuditEntry`` sin
    pasar ``modulo`` (muchos lo hacían directo, dejando modulo=NULL → la entrada NO
    aparecía al filtrar por su módulo en Auditoría), el prefijo determinístico de la
    acción lo resuelve acá. Devuelve None solo si la acción no matchea ninguna
    familia conocida (se registra igual, sin módulo).
    """
    a = accion or ""
    if a.startswith("user."):
        return ModuloAuditoria.USUARIOS
    if a.startswith(("materia.", "comision.", "inscripcion.")):
        return ModuloAuditoria.MATERIAS
    if a == "moodle.sync" or a.startswith("moodle_credencial."):
        return ModuloAuditoria.MOODLE
    if a.startswith("examen."):
        return ModuloAuditoria.EXAMENES
    if a.startswith("config"):
        return ModuloAuditoria.CONFIGURACION
    if a.startswith("consent"):
        return ModuloAuditoria.CONSENTIMIENTO
    if a.startswith(("biometria", "enrollment")):
        return ModuloAuditoria.BIOMETRIA
    if a.startswith(PREFIJO_REVISION_DECISION):
        return ModuloAuditoria.REVISION
    # Evidencia y cadena de custodia: acceso/depósito de evidencia, manipulación,
    # firma maestra, verificación de cadena, retención/borrado y derechos del titular
    # (DSR) — el frontend los agrupa todos bajo "Evidencia de sesiones".
    if a.startswith(
        (
            "acceso_evidencia",
            "deposito_evidencia",
            "manipulacion_detectada",
            "firma_maestra",
            PREFIJO_VERIFY_CHAIN,
            "retention",
            PREFIJO_DSR,
            "derecho_acceso",
        )
    ):
        return ModuloAuditoria.EVIDENCIA
    return None
