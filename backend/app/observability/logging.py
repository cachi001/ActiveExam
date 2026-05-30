"""Logging estructurado JSON a stdout, correlacionado con ``trace_id``.

Twelve-factor: los logs son un stream de eventos a stdout; el colector (Loki)
los recoge. Cada linea es un objeto JSON, e incluye el ``trace_id`` del span
OpenTelemetry activo cuando existe, para correlacionar logs <-> trazas en
Grafana (los tres pilares, DD-12).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


def _current_trace_id() -> str | None:
    """Devuelve el trace_id activo (hex de 32) o ``None`` si no hay span/OTel."""
    try:
        from opentelemetry import trace  # import perezoso: OTel es opcional
    except ImportError:  # pragma: no cover - depende del entorno
        return None

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


class JsonLogFormatter(logging.Formatter):
    """Formatea cada registro como una linea JSON con ``trace_id``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        trace_id = _current_trace_id()
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configura el root logger para emitir JSON a stdout (idempotente)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
