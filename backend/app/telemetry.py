"""OpenTelemetry traces and metrics.

Spans cover every agent step (route, retrieve, grade, rewrite, generate, check) and every ingestion stage, so a
slow answer can be traced to the exact step. Exporters are configured from the environment:
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP to a collector (Docker Compose sends it on to Tempo, Prometheus and Grafana)
- APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor / Application Insights, which Azure AI Foundry reads
Without either, the API calls below are no-ops.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

from opentelemetry import metrics, trace

log = logging.getLogger(__name__)
tracer = trace.get_tracer("askwise")
meter = metrics.get_meter("askwise")

questions = meter.create_counter("askwise.questions", description="Questions answered")
question_latency = meter.create_histogram("askwise.question.duration", unit="ms", description="Time to full answer")
step_latency = meter.create_histogram("askwise.agent.step.duration", unit="ms", description="Agent step time")
ingested_chunks = meter.create_counter("askwise.ingest.chunks", description="Chunks indexed")
rewrites = meter.create_counter("askwise.agent.rewrites", description="Searches retried with a rewritten query")


@contextmanager
def span(name: str, **attributes):
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(f"askwise.{key}", value)
        yield current


def setup(app=None, service_name: str = "askwise-api") -> str:
    """Configures exporters and instruments FastAPI. Returns a short description of where telemetry goes."""
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor()
            _instrument(app)
            return "azure-monitor"
        except ImportError:
            log.warning("azure-monitor-opentelemetry is not installed; skipping Azure Monitor export")
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            log.warning("OpenTelemetry SDK/exporter not installed; telemetry disabled")
            return "disabled"
        resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", service_name)})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=10000)
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
        _instrument(app)
        return "otlp"
    return "disabled"


def _instrument(app) -> None:
    if app is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/api/health")
    except ImportError:
        pass
