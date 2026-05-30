"""Instrumentacion OpenTelemetry + metricas Prometheus (DD-12).

- Trazas: se exportan via OTLP a Tempo (``OTEL_EXPORTER_OTLP_ENDPOINT``).
- Metricas: se exponen en ``/metrics`` en formato Prometheus, scrapeadas por
  Prometheus segun ``infra/observability/prometheus/prometheus.yml``.

La instrumentacion de FastAPI es perezosa y tolerante a la ausencia de las
librerias OTel (asi los tests unitarios corren sin el stack). Si OTel no esta
instalado, ``instrument_app`` no falla: solo registra las metricas Prometheus.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def instrument_app(app: FastAPI, *, otlp_endpoint: str, service_name: str) -> None:
    """Instrumenta la app con trazas OTLP. Tolerante si OTel no esta presente."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OpenTelemetry no instalado; se omite la instrumentacion de trazas."
        )
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def metrics_endpoint() -> tuple[bytes, str]:
    """Render del registro Prometheus por defecto. Devuelve (payload, content_type)."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return generate_latest(), CONTENT_TYPE_LATEST
