#!/usr/bin/env python3
"""
Cross-Service Context Propagation Example for OpenTelemetry

This script demonstrates how context (including baggage items) propagates across service
boundaries in distributed systems. It shows how to use baggage to carry business context
along with traces to enrich observability data.

Usage:
    python baggage_propagation.py --endpoint http://localhost:4317

Requirements:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

import argparse
import json
import logging
import os
import random
import sys
import time
import uuid
from typing import Dict, List, Optional, Tuple

# Import OpenTelemetry components
from opentelemetry import trace, baggage, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('otel-context-propagation')

# Service definitions with their metadata
SERVICES = {
    'web-frontend': {
        'name': 'web-frontend',
        'version': '1.0.0',
        'language': 'javascript',
    },
    'mobile-app': {
        'name': 'mobile-app',
        'version': '2.1.0',
        'language': 'kotlin',
    },
    'api-gateway': {
        'name': 'api-gateway',
        'version': '1.2.0',
        'language': 'go',
    },
    'user-service': {
        'name': 'user-service',
        'version': '3.0.1',
        'language': 'java',
    },
    'order-service': {
        'name': 'order-service',
        'version': '2.0.0',
        'language': 'python',
    },
    'payment-service': {
        'name': 'payment-service',
        'version': '1.5.0',
        'language': 'node',
    },
    'inventory-service': {
        'name': 'inventory-service',
        'version': '1.1.0',
        'language': 'python',
    },
    'shipping-service': {
        'name': 'shipping-service',
        'version': '1.0.0',
        'language': 'rust',
    },
    'notification-service': {
        'name': 'notification-service',
        'version': '2.0.0',
        'language': 'python',
    },
    'analytics-service': {
        'name': 'analytics-service',
        'version': '1.0.0',
        'language': 'python',
    },
}

# Baggage examples for different business contexts
BAGGAGE_TEMPLATES = {
    'e-commerce': {
        'user.id': lambda: f"user-{random.randint(10000, 99999)}",
        'user.tier': lambda: random.choice(['standard', 'premium', 'enterprise']),
        'user.country': lambda: random.choice(['US', 'CA', 'UK', 'DE', 'JP', 'AU']),
        'session.id': lambda: str(uuid.uuid4()),
        'cart.id': lambda: f"cart-{random.randint(1000, 9999)}",
        'order.id': lambda: f"order-{random.randint(10000, 99999)}",
        'payment.method': lambda: random.choice(['credit_card', 'paypal', 'bank_transfer', 'crypto']),
        'shipping.method': lambda: random.choice(['standard', 'express', 'next_day']),
        'device.type': lambda: random.choice(['desktop', 'mobile', 'tablet']),
        'marketing.campaign': lambda: f"campaign-{random.randint(100, 999)}",
    },
    'banking': {
        'customer.id': lambda: f"cust-{random.randint(10000, 99999)}",
        'account.type': lambda: random.choice(['checking', 'savings', 'investment', 'credit']),
        'transaction.id': lambda: f"txn-{uuid.uuid4()}",
        'transaction.amount': lambda: str(round(random.uniform(10, 1000), 2)),
        'transaction.currency': lambda: random.choice(['USD', 'EUR', 'GBP', 'JPY']),
        'risk.score': lambda: str(random.randint(0, 100)),
        'authentication.method': lambda: random.choice(['password', 'sms', 'app', 'biometric']),
        'customer.segment': lambda: random.choice(['retail', 'business', 'wealth', 'institutional']),
    },
    'healthcare': {
        'patient.id': lambda: f"patient-{random.randint(10000, 99999)}",
        'visit.id': lambda: f"visit-{random.randint(1000, 9999)}",
        'provider.id': lambda: f"provider-{random.randint(100, 999)}",
        'department': lambda: random.choice(['cardiology', 'neurology', 'oncology', 'pediatrics']),
        'insurance.id': lambda: f"ins-{random.randint(10000, 99999)}",
        'appointment.type': lambda: random.choice(['initial', 'follow-up', 'emergency', 'procedure']),
        'priority': lambda: random.choice(['routine', 'urgent', 'emergency']),
    }
}

# Service interaction flows
FLOWS = [
    {
        'name': 'checkout_flow',
        'domain': 'e-commerce',
        'source': 'web-frontend',
        'steps': [
            {'from': 'web-frontend', 'to': 'api-gateway', 'operation': 'checkout_request'},
            {'from': 'api-gateway', 'to': 'user-service', 'operation': 'validate_user'},
            {'from': 'api-gateway', 'to': 'order-service', 'operation': 'create_order'},
            {'from': 'order-service', 'to': 'inventory-service', 'operation': 'reserve_inventory'},
            {'from': 'order-service', 'to': 'payment-service', 'operation': 'process_payment'},
            {'from': 'order-service', 'to': 'shipping-service', 'operation': 'create_shipment'},
            {'from': 'order-service', 'to': 'notification-service', 'operation': 'send_confirmation'},
            {'from': 'notification-service', 'to': 'analytics-service', 'operation': 'record_purchase'},
        ],
        'baggage_keys': [
            'user.id', 'user.tier', 'user.country', 'session.id', 'cart.id', 
            'order.id', 'payment.method', 'shipping.method', 'device.type', 
            'marketing.campaign'
        ],
        'enrichment_service': 'api-gateway',
        'enrichment_keys': ['user.tier', 'user.country']
    },
    {
        'name': 'mobile_checkout',
        'domain': 'e-commerce',
        'source': 'mobile-app',
        'steps': [
            {'from': 'mobile-app', 'to': 'api-gateway', 'operation': 'checkout_request'},
            {'from': 'api-gateway', 'to': 'user-service', 'operation': 'validate_user'},
            {'from': 'api-gateway', 'to': 'order-service', 'operation': 'create_order'},
            {'from': 'order-service', 'to': 'payment-service', 'operation': 'process_payment'},
            {'from': 'order-service', 'to': 'shipping-service', 'operation': 'create_shipment'},
            {'from': 'order-service', 'to': 'notification-service', 'operation': 'send_confirmation'},
        ],
        'baggage_keys': [
            'user.id', 'device.type', 'session.id', 'cart.id', 
            'order.id', 'payment.method', 'shipping.method'
        ],
        'enrichment_service': 'api-gateway',
        'enrichment_keys': ['user.tier']
    },
    {
        'name': 'bank_transfer',
        'domain': 'banking',
        'source': 'web-frontend',
        'steps': [
            {'from': 'web-frontend', 'to': 'api-gateway', 'operation': 'transfer_request'},
            {'from': 'api-gateway', 'to': 'user-service', 'operation': 'authenticate_user'},
            {'from': 'api-gateway', 'to': 'payment-service', 'operation': 'validate_accounts'},
            {'from': 'payment-service', 'to': 'payment-service', 'operation': 'execute_transfer'},
            {'from': 'payment-service', 'to': 'notification-service', 'operation': 'send_receipt'},
            {'from': 'notification-service', 'to': 'analytics-service', 'operation': 'record_transaction'},
        ],
        'baggage_keys': [
            'customer.id', 'account.type', 'transaction.id', 'transaction.amount',
            'transaction.currency', 'risk.score', 'authentication.method',
            'customer.segment'
        ],
        'enrichment_service': 'payment-service',
        'enrichment_keys': ['risk.score']
    }
]

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Cross-Service Context Propagation Example for OpenTelemetry')
    parser.add_argument('--endpoint', default=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317'),
                        help='OTLP endpoint URL (default: http://localhost:4317)')
    parser.add_argument('--insecure', action='store_true', default=True,
                        help='Use insecure connection (default: True)')
    parser.add_argument('--num-traces', type=int, default=3,
                        help='Number of traces to generate (default: 3)')
    parser.add_argument('--flow', type=str, choices=[flow['name'] for flow in FLOWS], 
                        help='Specific flow to simulate (default: random)')
    return parser.parse_args()

def setup_telemetry(endpoint: str, insecure: bool = True) -> Tuple[object, object]:
    """Set up OpenTelemetry tracing and logging."""
    # Create a unique ID for this simulation run
    simulation_id = str(uuid.uuid4())[:8]
    
    # Create a resource with service information
    resource = Resource.create({
        "service.name": "otel-context-simulation",
        "service.version": "1.0.0",
        "simulation.run.id": simulation_id
    })
    
    logger.info(f"Simulation run ID: {simulation_id}")
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
    tracer = trace.get_tracer("context-simulation-tracer")
    
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
    otel_logger = logging.getLogger("context-simulation-logger")
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    otel_logger.addHandler(otel_handler)
    otel_logger.setLevel(logging.INFO)
    
    return tracer, otel_logger

def generate_baggage_values(domain: str, keys: List[str]) -> Dict[str, str]:
    """Generate baggage values for the specified domain and keys."""
    baggage_values = {}
    
    if domain in BAGGAGE_TEMPLATES:
        template = BAGGAGE_TEMPLATES[domain]
        for key in keys:
            if key in template:
                baggage_values[key] = template[key]()
                
    return baggage_values

def enrich_baggage(ctx, service: str, flow: Dict, existing_values: Dict[str, str]) -> context.Context:
    """Simulate a service enriching baggage with additional context."""
    if service != flow['enrichment_service']:
        return ctx
        
    enrichment_keys = flow['enrichment_keys']
    domain = flow['domain']
    
    # Generate enrichment values
    for key in enrichment_keys:
        if key not in existing_values and domain in BAGGAGE_TEMPLATES:
            template = BAGGAGE_TEMPLATES[domain]
            if key in template:
                value = template[key]()
                ctx = baggage.set_baggage(key, value, context=ctx)
                existing_values[key] = value
                
    return ctx

def simulate_service_span(
    tracer,
    otel_logger,
    from_service: str,
    to_service: str, 
    operation: str,
    parent_ctx=None,
    baggage_values: Dict[str, str] = None,
) -> context.Context:
    """
    Simulate a span representing a service call with baggage propagation.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        from_service: Source service name
        to_service: Target service name
        operation: Operation being performed
        parent_ctx: Parent context (if any)
        baggage_values: Current baggage values (for logging)
        
    Returns:
        The updated context with the span
    """
    from_info = SERVICES.get(from_service, {'name': from_service, 'version': '1.0.0', 'language': 'unknown'})
    to_info = SERVICES.get(to_service, {'name': to_service, 'version': '1.0.0', 'language': 'unknown'})
    
    # Prepare span attributes
    attributes = {
        'service.name': from_info['name'],
        'service.version': from_info['version'],
        'service.language': from_info['language'],
        'peer.service': to_info['name'],
        'peer.service.version': to_info['version'],
        'peer.service.language': to_info['language'],
    }
    
    # Add all baggage values as span attributes (with baggage prefix)
    if baggage_values:
        for key, value in baggage_values.items():
            attributes[f'baggage.{key}'] = value
    
    # Start a new span
    with tracer.start_as_current_span(
        f"{from_service}_{to_service}_{operation}",
        context=parent_ctx,
        kind=trace.SpanKind.CLIENT,
        attributes=attributes
    ) as span:
        span_ctx = trace.get_current_span().get_span_context()
        trace_id = trace.format_trace_id(span_ctx.trace_id)
        span_id = trace.format_span_id(span_ctx.span_id)
        
        # Log the operation with baggage values
        otel_logger.info(
            f"Service {from_service} calling {to_service}.{operation}",
            extra={
                "trace_id": trace_id,
                "span_id": span_id,
                "from_service": from_service,
                "to_service": to_service,
                "operation": operation,
                "baggage": json.dumps(baggage_values) if baggage_values else "{}"
            }
        )
        
        # Simulate some work
        time.sleep(random.uniform(0.05, 0.2))
        
        # Return the current context with the span
        return context.get_current()

def simulate_service_receive(
    tracer,
    otel_logger,
    service: str,
    operation: str,
    parent_ctx,
    baggage_values: Dict[str, str] = None,
) -> context.Context:
    """
    Simulate a span representing a service receiving a request.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        service: Service name
        operation: Operation being performed
        parent_ctx: Parent context
        baggage_values: Current baggage values (for logging)
        
    Returns:
        The updated context with the span
    """
    service_info = SERVICES.get(service, {'name': service, 'version': '1.0.0', 'language': 'unknown'})
    
    # Prepare span attributes
    attributes = {
        'service.name': service_info['name'],
        'service.version': service_info['version'],
        'service.language': service_info['language'],
    }
    
    # Add all baggage values as span attributes (with baggage prefix)
    if baggage_values:
        for key, value in baggage_values.items():
            attributes[f'baggage.{key}'] = value
    
    # Start a new span
    with tracer.start_as_current_span(
        f"{service}_receive_{operation}",
        context=parent_ctx,
        kind=trace.SpanKind.SERVER,
        attributes=attributes
    ) as span:
        span_ctx = trace.get_current_span().get_span_context()
        trace_id = trace.format_trace_id(span_ctx.trace_id)
        span_id = trace.format_span_id(span_ctx.span_id)
        
        # Log the operation receipt with baggage values
        otel_logger.info(
            f"Service {service} received {operation} request",
            extra={
                "trace_id": trace_id,
                "span_id": span_id,
                "service": service,
                "operation": operation,
                "baggage": json.dumps(baggage_values) if baggage_values else "{}"
            }
        )
        
        # Simulate some work
        time.sleep(random.uniform(0.05, 0.2))
        
        # Return the current context with the span
        return context.get_current()

def simulate_flow(tracer, otel_logger, flow: Dict):
    """
    Simulate a complete flow with baggage propagation across services.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        flow: Flow definition to simulate
    """
    flow_name = flow['name']
    domain = flow['domain']
    steps = flow['steps']
    
    logger.info(f"Simulating flow: {flow_name} (domain: {domain})")
    
    # Generate initial baggage values
    baggage_values = generate_baggage_values(domain, flow['baggage_keys'])
    
    # Initialize context with baggage
    ctx = context.get_current()
    for key, value in baggage_values.items():
        ctx = baggage.set_baggage(key, value, context=ctx)
    
    # Create a trace ID that will be seen in Jaeger
    correlation_id = str(uuid.uuid4())
    
    # Process each step in the flow
    for i, step in enumerate(steps):
        from_service = step['from']
        to_service = step['to']
        operation = step['operation']
        
        # Make service call
        ctx = simulate_service_span(
            tracer=tracer,
            otel_logger=otel_logger,
            from_service=from_service,
            to_service=to_service,
            operation=operation,
            parent_ctx=ctx,
            baggage_values=baggage_values
        )
        
        # Add potential enrichment
        ctx = enrich_baggage(ctx, to_service, flow, baggage_values)
        
        # Update baggage values from context for logging
        for key in flow['baggage_keys']:
            value = baggage.get_baggage(key, context=ctx)
            if value:
                baggage_values[key] = value
        
        # Receive at destination service
        ctx = simulate_service_receive(
            tracer=tracer,
            otel_logger=otel_logger,
            service=to_service,
            operation=operation,
            parent_ctx=ctx,
            baggage_values=baggage_values
        )
        
    logger.info(f"Flow {flow_name} completed with baggage: {baggage_values}")
    
    return baggage_values

def main():
    """Main execution function."""
    args = parse_args()
    
    # Print configuration details
    logger.info("OpenTelemetry Context Propagation Simulation")
    logger.info("-" * 50)
    
    try:
        # Set up telemetry
        tracer, otel_logger = setup_telemetry(
            endpoint=args.endpoint,
            insecure=args.insecure
        )
        
        # Get flow to simulate
        if args.flow:
            flows_to_run = [next(flow for flow in FLOWS if flow['name'] == args.flow)]
        else:
            flows_to_run = random.choices(FLOWS, k=args.num_traces)
        
        logger.info(f"Simulating {len(flows_to_run)} flows with baggage propagation")
        
        for i, flow in enumerate(flows_to_run):
            logger.info(f"Flow {i+1}/{len(flows_to_run)}: {flow['name']}")
            simulate_flow(tracer, otel_logger, flow)
            
            # Small delay between flows
            time.sleep(random.uniform(0.5, 1.0))
        
        logger.info("Simulation complete! Check Jaeger to visualize context propagation.")
        logger.info("Look at the span attributes to see propagated baggage values.")
        
        # Give time for exporters to flush
        time.sleep(5)
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
