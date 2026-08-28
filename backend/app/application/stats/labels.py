"""Etiquetas legibles (castellano) para códigos técnicos — FUENTE ÚNICA.

Nada de identificadores snake_case a la vista del usuario: los reportes (PDF/Excel),
los gráficos y la UI deben mostrar SIEMPRE texto normalizado y profesional. Antes
cada export tenía su propio mapa (duplicado, incompleto y con claves desfasadas del
enum real), y caía a un `tipo.replace("_", " ")` crudo. Acá se centraliza y se
completa contra el enum canónico ``TipoEvento``; el fallback humaniza cualquier
código desconocido en vez de mostrarlo tal cual.
"""

from __future__ import annotations

import json

from app.domain.events.schema import TipoEvento
from app.domain.exam_content.estado_entrega import estados_para_ui, etiqueta_estado_entrega

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
    TipoEvento.CAPTURA_PAUSA: "Captura en pausa",
    TipoEvento.PAUSA_SIN_CAPTURA: "Pausa sin captura",
    # "copiar_pegar" (C-25/C-76 tarea 15) es un evento real emitido por el
    # cliente pero fuera del enum TipoEvento (IngestEventoIn.tipo acepta
    # cualquier string) — clave string literal, no un miembro del enum.
    "copiar_pegar": "Copiar / pegar",
}

# Estados de revisión (decisiones humanas, modelo de un solo paso) — usados en
# gráficos y reportes.
# `pendiente` NO está: el endpoint de revisión lo rechaza explícitamente por no ser
# una decisión terminal (`_parse_decision`, review/router.py), así que la columna
# `proctoring_session.decision` nunca puede valer eso. Era una etiqueta muerta
# (F-07, c-78 D8). `humanizar` cubre cualquier valor inesperado.
ETIQUETA_DECISION: dict[str, str] = {
    "sin_revisar": "Sin revisar",
    "aprobado": "Aprobado",
    "anulado": "Anulado por fraude",
}


#: Color de cada decisión para los gráficos. Vive acá y no en la pantalla por lo
#: mismo que las etiquetas: si lo elige cada gráfico, cada gráfico lo elige
#: distinto y el mismo veredicto termina de dos colores en dos pantallas.
COLOR_DECISION: dict[str, str] = {
    "sin_revisar": "#94a3b8",
    "aprobado": "#10b981",
    "anulado": "#ef4444",
}


def decisiones_para_ui() -> list[dict[str, str]]:
    """Lo que consume la pantalla de estadísticas: valor, etiqueta y color."""
    return [
        {"valor": v, "etiqueta": etiqueta, "color": COLOR_DECISION.get(v, "#8b5cf6")}
        for v, etiqueta in ETIQUETA_DECISION.items()
    ]


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


# Estados de sincronización con Moodle (WritebackEstado + el alias de display
# 'sin_token' de resultados_query.ESTADO_SIN_TOKEN + 'manual' de c-78 D14).
# FUENTE ÚNICA de las etiquetas que ve el admin en "Alumnos que rindieron" (filtro
# + badge de estado): el frontend las consume por API (`GET /estados-moodle`) en vez
# de repetirlas. Antes las tenía escritas a mano y ya se habían desfasado — cuando
# apareció 'manual', el badge lo mostraba pero el filtro no lo ofrecía, así que el
# estado se veía y no se podía buscar.
#: Lista ordenada que consume el frontend para armar el filtro y el badge.
ESTADOS_MOODLE: list[dict[str, str]] = estados_para_ui()

#: Compatibilidad: quedaba código leyendo el diccionario. Se arma DESDE el enum
#: para que no pueda volver a divergir.
ETIQUETA_ESTADO_MOODLE: dict[str, str] = {e["valor"]: e["etiqueta"] for e in ESTADOS_MOODLE}
TONO_ESTADO_MOODLE: dict[str, str] = {e["valor"]: e["tono"] for e in ESTADOS_MOODLE}


def etiqueta_estado_moodle(estado: str) -> str:
    """Etiqueta legible de un estado de la nota (fuente única: `EstadoEntregaNota`)."""
    return etiqueta_estado_entrega(estado)


# --- Acciones del registro de auditoría -------------------------------------
# El export de auditoría lo lee una persona (y eventualmente un organismo de
# control): nunca debe salir "moodle.sync" ni "review.decision.aprobado".
# Cubre AccionAuditoria; los prefijos variables se resuelven en etiqueta_accion().
ETIQUETA_ACCION: dict[str, str] = {
    "user.create": "Alta de usuario",
    "user.update": "Editó usuario",
    # Baja de usuario = baja LÓGICA (soft-delete) = cambio de estado, NO eliminación.
    "user.delete": "Cambió el estado del usuario",
    "user.reactivate": "Cambió el estado del usuario",
    "materia.create": "Creó materia",
    "materia.update": "Editó materia",
    "materia.delete": "Eliminó materia",
    "materia.set_activa": "Cambió el estado de la materia",
    "comision.create": "Creó comisión",
    "comision.update": "Editó comisión",
    "comision.delete": "Eliminó comisión",
    "comision.set_activa": "Cambió el estado de la comisión",
    "comision.set_docente": "Asignó docente a la comisión",
    # c-79 / c-76 / c-78 (F-07): acciones que el sistema YA emitía pero que no
    # tenían etiqueta acá, así que en el export y en el registro salían con su
    # código crudo humanizado ("Materia set coordinador").
    "materia.set_coordinador": "Asignó coordinador a la materia",
    "materia.set_profesor": "Asignó profesor a la materia",
    "sesion.test.delete": "Eliminó una sesión de diagnóstico",
    "sesion.resultado.archivar": "Archivó o desarchivó un resultado",
    "examen.import": "Cargó un examen",
    "examen.moodle_target": "Fijó destino de la nota en Moodle",
    "examen.config_update": "Cambió la configuración del examen",
    "examen.seleccion_preguntas": "Cambió las preguntas del examen",
    "examen.baja": "Dio de baja un examen",
    "examen.reactivar": "Reactivó un examen",
    "pregunta_banco.baja": "Dio de baja una pregunta del banco",
    "pregunta_banco.reactivar": "Reactivó una pregunta del banco",
    "categoria_banco.baja": "Dio de baja una categoría del banco",
    "categoria_banco.reactivar": "Reactivó una categoría del banco",
    "examen.publicar_notas": "Publicó las notas del examen",
    "moodle.sync": "Sincronizó notas a Moodle",
    "moodle.nota_marcada_manual": "Marcó a mano que la nota se cargó en el campus",
    "moodle_credencial.conectar": "Conectó su cuenta del campus",
    "moodle_credencial.renovar": "Renovó su cuenta del campus",
    "moodle_credencial.desconectar": "Desconectó su cuenta del campus",
    "moodle_credencial.intentos_fallidos": "Intentos fallidos repetidos en el campus",
    "inscripcion.create": "Inscribió a un alumno",
    "inscripcion.delete": "Dio de baja una inscripción",
    "config_update": "Cambió la configuración del sistema",
    "consent.otorgado": "Otorgó el consentimiento",
    "consent_alternative_chosen": "Eligió la vía alternativa",
    "biometria.verificacion": "Verificó la identidad",
    "enrollment.embedding_referencia.alta": "Registró la foto de referencia",
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


# --- Módulos del registro de auditoría --------------------------------------
# Fuente única del nombre legible del módulo (espeja TODOS_MODULOS del front).
# El export y cualquier reporte deben mostrar "Campus (Moodle)", nunca "MOODLE".
ETIQUETA_MODULO: dict[str, str] = {
    "USUARIOS": "Gestión de usuarios",
    "MATERIAS": "Materias y comisiones",
    "EXAMENES": "Catálogo de exámenes",
    "SESIONES": "Sesiones de examen",
    "CONSENTIMIENTO": "Consentimiento",
    "BIOMETRIA": "Registro biométrico",
    "EVIDENCIA": "Evidencia de sesiones",
    "REVISION": "Cola de revisión",
    "MOODLE": "Campus (Moodle)",
    "CONFIGURACION": "Configuración del sistema",
}


def etiqueta_modulo(modulo: str | None) -> str:
    """Etiqueta legible de un módulo de auditoría (o humaniza si es desconocido)."""
    if not modulo:
        return ""
    return ETIQUETA_MODULO.get(modulo, humanizar(modulo))


# --- Detalle (propósito) del registro de auditoría --------------------------
# Un cambio de configuración se guarda como propósito JSON {before, after}. En la
# pantalla se diffea a "Cambió N parámetros"; en el export hay que resumirlo a
# texto legible en vez de volcar el JSON crudo (que en el archivo se lee como
# basura). Port del helper `configDiff`/`labelConfig` del front (auditoria.helpers.ts).
_LABEL_CONFIG: dict[str, str] = {
    "chat_habilitado": "Chat proctor–alumno",
    "pausas_habilitadas": "Pausas del alumno",
    "pausa_max_min": "Duración máx. de pausa (min)",
    "umbral_cola_revision": "Umbral de revisión",
    "detectores_activos": "Detectores activos",
    "retencion_dias_default": "Retención por defecto (días)",
    "consent_version_vigente": "Versión de consentimiento",
    "face_absent_ms": "Rostro ausente (ms)",
    "multiple_faces_frames": "Múltiples rostros (frames)",
    "gaze_deviation_threshold": "Umbral de mirada desviada",
    "gaze_sustained_ms": "Mirada desviada sostenida (ms)",
    "gaze_fixation_tolerance": "Tolerancia de fijación",
}


def _label_config(key: str) -> str:
    return _LABEL_CONFIG.get(key, key.replace("_", " "))


def _fmt_valor_config(valor: object) -> str:
    """bool → Sí/No, lista → 'N ítems', dict → JSON, None → '—'."""
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, list):
        return f"{len(valor)} ítem" + ("" if len(valor) == 1 else "s")
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def detalle_legible(proposito: str | None) -> str:
    """Detalle del propósito para el export/reporte.

    Un cambio de config llega como JSON ``{before, after}`` → se resume a
    "Cambió — Param: antes → después; …". Cualquier otro propósito (texto plano)
    se devuelve tal cual. Nunca vuelca el JSON crudo.
    """
    if not proposito:
        return ""
    try:
        parsed = json.loads(proposito)
    except (ValueError, TypeError):
        return proposito
    if not isinstance(parsed, dict) or "before" not in parsed or "after" not in parsed:
        return proposito
    before = parsed.get("before") or {}
    after = parsed.get("after") or {}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return proposito
    cambios: list[str] = []
    for key in sorted(set(before) | set(after)):
        if key == "version":  # metadato, no es un parámetro configurable
            continue
        antes = before.get(key)
        despues = after.get(key)
        if antes != despues:
            cambios.append(
                f"{_label_config(key)}: "
                f"{_fmt_valor_config(antes)} → {_fmt_valor_config(despues)}"
            )
    if not cambios:
        return "Guardó la configuración sin cambios."
    return "Cambió — " + "; ".join(cambios)
