#!/usr/bin/env python3
"""
OTEL Endpoint Validation Script

This script validates that your OpenTelemetry collector is correctly configured
and accessible. It sends test spans, metrics, and logs to verify the connection.

Usage:
    python otel_validate.py [--endpoint http://localhost:4317]

Requirements:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

import argparse
import logging
import os
import sys
import time
import uuid
from typing import Optional

# Import OpenTelemetry components
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Validate OpenTelemetry collector connection')
parser.add_argument('--endpoint', default=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317'),
                    help='OTLP endpoint URL (default: http://localhost:4317)')
parser.add_argument('--insecure', action='store_true', default=True,
                    help='Use insecure connection (default: True)')
parser.add_argument('--service-name', default='otel-validation',
                    help='Service name for telemetry (default: otel-validation)')
args = parser.parse_args()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('otel-validation')

def setup_telemetry(endpoint: str, insecure: bool = True, service_name: str = 'otel-validation'):
    """
    Set up OpenTelemetry telemetry (tracing, metrics, and logging).
    
    Args:
        endpoint: The OTLP endpoint URL
        insecure: Whether to use an insecure connection
        service_name: The service name for telemetry
    
    Returns:
        Tuple of (tracer, meter, logger)
    """
    # Create a unique ID for this validation run
    validation_id = str(uuid.uuid4())[:8]
    
    # Create a resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.instance.id": validation_id,
        "validation.run.id": validation_id
    })
    
    logger.info(f"Validation run ID: {validation_id}")
    logger.info(f"Configuring telemetry with endpoint: {endpoint} (insecure: {insecure})")
    
    # Set up tracing
    trace_provider = TracerProvider(resource=resource)
    
    # Add console exporter for local visibility
    trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    # Add OTLP exporter
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=insecure
    )
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    
    # Set global trace provider
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(f"{service_name}-tracer")
    
    # Set up metrics
    console_metric_reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(), export_interval_millis=5000
    )
    
    otlp_metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=endpoint,
            insecure=insecure
        ),
        export_interval_millis=5000
    )
    
    metrics_provider = MeterProvider(
        resource=resource, 
        metric_readers=[console_metric_reader, otlp_metric_reader]
    )
    metrics.set_meter_provider(metrics_provider)
    meter = metrics.get_meter(f"{service_name}-meter")
    
    # Set up logging
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    
    # Add OTLP log exporter
    otlp_log_exporter = OTLPLogExporter(
        endpoint=endpoint,
        insecure=insecure
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
    
    # Create logger with OpenTelemetry handler
    otel_logger = logging.getLogger(f"{service_name}-logger")
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    otel_logger.addHandler(otel_handler)
    otel_logger.setLevel(logging.INFO)
    
    return tracer, meter, otel_logger

def validate_connection(tracer, meter, otel_logger):
    """
    Validate the connection to the OpenTelemetry collector by sending test telemetry.
    """
    # Create counter metrics
    counter = meter.create_counter(
        name="validation.counter",
        description="Counter metric for validation",
        unit="1",
    )
    
    # Create histogram metrics
    histogram = meter.create_histogram(
        name="validation.histogram",
        description="Histogram metric for validation",
        unit="ms",
    )
    
    # Validation span
    with tracer.start_as_current_span("validation.test") as span:
        span.set_attribute("validation.attribute", "test_value")
        otel_logger.info("Sending test span, metric, and log to the collector")
        
        # Add nested span
        with tracer.start_as_current_span("validation.nested") as nested_span:
            nested_span.set_attribute("validation.nested", True)
            otel_logger.info("This is a nested operation")
            
            # Record metrics
            counter.add(1, {"validation.type": "test"})
            histogram.record(123.45, {"validation.type": "test"})
            
            # Simulate some work
            time.sleep(0.5)
    
    # Give time for the batch processor to export
    logger.info("Waiting for telemetry to be exported...")
    time.sleep(5)

def check_endpoint(endpoint: str) -> Optional[str]:
    """
    Check the endpoint format and return warnings if needed.
    """
    warning = None
    
    if not endpoint.startswith(('http://', 'https://')):
        warning = f"Warning: Endpoint '{endpoint}' does not include protocol prefix (http:// or https://)"
    
    if '4317' in endpoint and 'http://' in endpoint:
        # Valid gRPC endpoint
        pass
    elif '4318' in endpoint and 'http://' in endpoint:
        warning = "Note: You're using port 4318 which is typically for HTTP/protobuf, not gRPC"
    
    return warning

def main():
    # Print configuration details
    logger.info("OpenTelemetry Endpoint Validation Tool")
    logger.info("-" * 50)
    
    # Check endpoint format
    warning = check_endpoint(args.endpoint)
    if warning:
        logger.warning(warning)
    
    try:
        # Set up telemetry
        tracer, meter, otel_logger = setup_telemetry(
            endpoint=args.endpoint,
            insecure=args.insecure,
            service_name=args.service_name
        )
        
        # Validate connection
        logger.info("Sending validation telemetry...")
        validate_connection(tracer, meter, otel_logger)
        
        logger.info("Validation complete! Check your collector/backend for the telemetry.")
        logger.info("Look for service.name=%s in your queries", args.service_name)
        
    except Exception as e:
        logger.error(f"Error validating OpenTelemetry connection: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
