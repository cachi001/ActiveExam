"""Observabilidad base (DD-12): logging estructurado, metricas y trazas.

Montada ANTES de que exista dominio. Cada change posterior instrumenta sobre
esta base en lugar de inventar observabilidad ad-hoc.

- ``logging.py``: logging estructurado JSON a stdout, con ``trace_id``.
- ``telemetry.py``: instrumentacion OpenTelemetry (trazas via OTLP) + metricas
  Prometheus.
"""
