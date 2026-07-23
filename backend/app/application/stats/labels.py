"""Etiquetas legibles (castellano) para códigos técnicos — FUENTE ÚNICA.

Nada de identificadores snake_case a la vista del usuario: los reportes (PDF/Excel),
los gráficos y la UI deben mostrar SIEMPRE texto normalizado y profesional. Antes
cada export tenía su propio mapa (duplicado, incompleto y con claves desfasadas del
enum real), y caía a un `tipo.replace("_", " ")` crudo. Acá se centraliza y se
completa contra el enum canónico ``TipoEvento``; el fallback humaniza cualquier
código desconocido en vez de mostrarlo tal cual.
"""

from __future__ import annotations

from app.domain.events.schema import TipoEvento

# Cubre TODOS los miembros de TipoEvento (si se agrega uno, agregar su etiqueta).
ETIQUETA_EVENTO: dict[str, str] = {
    TipoEvento.ROSTRO_AUSENTE: "Rostro ausente",
    TipoEvento.MULTIPLES_ROSTROS: "Múltiples rostros",
    TipoEvento.MIRADA_DESVIADA: "Mirada desviada",
    TipoEvento.POSTURA: "Postura irregular",
    TipoEvento.CAMBIO_PESTANA: "Cambio de pestaña",
    TipoEvento.MONITOR_ADICIONAL: "Monitor adicional",
    TipoEvento.POSIBLE_CAMBIO_IDENTIDAD: "Posible cambio de identidad",
    TipoEvento.EVIDENCIA_CORRUPTA: "Evidencia corrupta",
    TipoEvento.TAMPERING_CAMARA_VIRTUAL: "Cámara virtual detectada",
    TipoEvento.CORTE_CONECTIVIDAD: "Corte de conexión",
    TipoEvento.HEARTBEAT: "Señal de actividad",
    TipoEvento.RECARGA_PAGINA: "Recarga de página",
    TipoEvento.REANUDACION_TARDIA: "Reanudación tardía",
}

# Estados de revisión (decisiones humanas) — usados en gráficos y reportes.
ETIQUETA_DECISION: dict[str, str] = {
    "sin_revisar": "Sin revisar",
    "pendiente": "Pendiente",
    "sin_hallazgos": "Sin hallazgos",
    "aprobado": "Aprobado",
    "caso_abierto": "Caso abierto",
}


def humanizar(clave: str) -> str:
    """Convierte un código snake_case en texto legible (nunca lo muestra crudo).

    'algun_codigo_nuevo' -> 'Algun codigo nuevo'. Es el último recurso: lo ideal es
    que todo código conocido tenga su etiqueta en los mapas de arriba.
    """
    return clave.replace("_", " ").strip().capitalize() if clave else ""


def etiqueta_evento(tipo: str) -> str:
    """Etiqueta legible de un tipo de evento (o humaniza si es desconocido)."""
    return ETIQUETA_EVENTO.get(tipo, humanizar(tipo))


def etiqueta_decision(decision: str) -> str:
    """Etiqueta legible de un estado de revisión (o humaniza si es desconocido)."""
    return ETIQUETA_DECISION.get(decision, humanizar(decision))


# --- Acciones del registro de auditoría -------------------------------------
# El export de auditoría lo lee una persona (y eventualmente un organismo de
# control): nunca debe salir "moodle.sync" ni "review.decision.aprobado".
# Cubre AccionAuditoria; los prefijos variables se resuelven en etiqueta_accion().
ETIQUETA_ACCION: dict[str, str] = {
    "user.create": "Alta de usuario",
    "user.update": "Editó usuario",
    "user.delete": "Baja de usuario",
    "user.reactivate": "Cambió el estado del usuario",
    "materia.create": "Creó materia",
    "materia.update": "Editó materia",
    "materia.delete": "Eliminó materia",
    "materia.set_activa": "Cambió el estado de la materia",
    "comision.create": "Creó comisión",
    "comision.update": "Editó comisión",
    "comision.delete": "Eliminó comisión",
    "comision.set_activa": "Cambió el estado de la comisión",
    "examen.import": "Cargó un examen",
    "examen.moodle_target": "Fijó destino de la nota en Moodle",
    "examen.config_update": "Cambió la configuración del examen",
    "examen.seleccion_preguntas": "Cambió las preguntas del examen",
    "moodle.sync": "Sincronizó notas a Moodle",
    "inscripcion.create": "Inscribió a un alumno",
    "inscripcion.delete": "Dio de baja una inscripción",
    "config_update": "Cambió la configuración del sistema",
    "consent.otorgado": "Otorgó el consentimiento",
    "consent_alternative_chosen": "Eligió la vía alternativa",
    "biometria.verificacion": "Verificó la identidad",
    "enrollment.embedding_referencia.renovacion": "Renovó la foto de referencia",
    "acceso_evidencia": "Accedió a evidencia",
    "deposito_evidencia": "Depositó evidencia",
    "manipulacion_detectada": "Detectó manipulación de evidencia",
    "firma_maestra_y_reinferencia": "Firmó y re-infirió evidencia",
    "retention.session.deleted": "Eliminó una sesión por retención",
    "retention.session.hold_deferred": "Difirió la eliminación por un hold",
    "retention.biometric.egress": "Eliminó el dato biométrico al egreso",
    "derecho_acceso.informe_devolucion": "Entregó el informe al alumno",
}


def etiqueta_accion(accion: str) -> str:
    """Etiqueta legible de una acción de auditoría.

    Los prefijos con sufijo variable se resuelven acá: ``review.decision.<x>``
    lleva el veredicto en el sufijo y ``verify_chain.<x>`` el resultado de la
    verificación, así que no pueden estar en un mapa plano.
    """
    if not accion:
        return ""
    if accion.startswith("review.decision."):
        sufijo = accion.removeprefix("review.decision.")
        return f"Decisión de revisión: {etiqueta_decision(sufijo).lower()}"
    if accion.startswith("verify_chain."):
        return "Verificó la cadena de custodia"
    return ETIQUETA_ACCION.get(accion, humanizar(accion))
