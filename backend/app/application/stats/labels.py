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
