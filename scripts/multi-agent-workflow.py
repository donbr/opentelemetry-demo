#!/usr/bin/env python3
"""
Multi-Agent Workflow Simulation for OpenTelemetry

This script simulates a complex multi-agent workflow that generates telemetry
data showing how requests flow through multiple services. This demonstrates
parent-child relationships and baggage propagation across service boundaries.

Usage:
    python multi_agent_workflow.py --endpoint http://localhost:4317 --complex

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
logger = logging.getLogger('otel-simulation')

# Service definitions
SERVICES = {
    'api-gateway': {
        'name': 'api-gateway',
        'version': '1.0.0',
        'language': 'python',
        'dependencies': ['auth-service', 'product-service', 'user-service'],
    },
    'auth-service': {
        'name': 'auth-service',
        'version': '2.1.0',
        'language': 'go',
        'dependencies': ['user-service', 'cache-service'],
    },
    'product-service': {
        'name': 'product-service',
        'version': '1.2.0',
        'language': 'java',
        'dependencies': ['inventory-service', 'pricing-service', 'recommendation-service'],
    },
    'user-service': {
        'name': 'user-service',
        'version': '1.5.0',
        'language': 'node',
        'dependencies': ['db-service'],
    },
    'inventory-service': {
        'name': 'inventory-service',
        'version': '1.0.1',
        'language': 'python',
        'dependencies': ['db-service'],
    },
    'pricing-service': {
        'name': 'pricing-service',
        'version': '1.1.0',
        'language': 'python',
        'dependencies': ['db-service'],
    },
    'recommendation-service': {
        'name': 'recommendation-service',
        'version': '2.0.0',
        'language': 'python',
        'dependencies': ['db-service', 'analytics-service'],
    },
    'db-service': {
        'name': 'db-service',
        'version': '1.0.0',
        'language': 'internal',
        'dependencies': [],
    },
    'cache-service': {
        'name': 'cache-service',
        'version': '1.0.0',
        'language': 'internal',
        'dependencies': [],
    },
    'analytics-service': {
        'name': 'analytics-service',
        'version': '1.0.0',
        'language': 'python',
        'dependencies': ['db-service'],
    },
}

# API endpoints to simulate
ENDPOINTS = [
    '/api/v1/products',
    '/api/v1/products/{id}',
    '/api/v1/users/{id}',
    '/api/v1/cart',
    '/api/v1/checkout',
]

# HTTP methods to simulate
METHODS = ['GET', 'POST', 'PUT', 'DELETE']

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Multi-Agent Workflow Simulation for OpenTelemetry')
    parser.add_argument('--endpoint', default=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317'),
                        help='OTLP endpoint URL (default: http://localhost:4317)')
    parser.add_argument('--insecure', action='store_true', default=True,
                        help='Use insecure connection (default: True)')
    parser.add_argument('--complex', action='store_true', default=False,
                        help='Generate more complex workflow patterns')
    parser.add_argument('--num-requests', type=int, default=3,
                        help='Number of top-level requests to simulate (default: 3)')
    return parser.parse_args()

def setup_telemetry(endpoint: str, insecure: bool = True) -> Tuple[object, object]:
    """Set up OpenTelemetry tracing and logging."""
    # Create a unique ID for this simulation run
    simulation_id = str(uuid.uuid4())[:8]
    
    # Create a resource with service information
    resource = Resource.create({
        "service.name": "otel-simulation",
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
    tracer = trace.get_tracer("simulation-tracer")
    
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
    otel_logger = logging.getLogger("simulation-logger")
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    otel_logger.addHandler(otel_handler)
    otel_logger.setLevel(logging.INFO)
    
    return tracer, otel_logger

def simulate_service_call(
    tracer,
    otel_logger,
    service_name: str,
    operation_name: str,
    parent_context=None,
    is_error: bool = False,
    latency: float = None,
    use_baggage: bool = True,
    attributes: Dict = None,
    complex_workflow: bool = False
) -> context.Context:
    """
    Simulate a service call with proper telemetry.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        service_name: Name of the service making the call
        operation_name: Name of the operation being performed
        parent_context: Parent context to use (optional)
        is_error: Whether this operation should simulate an error
        latency: How long the operation should take (in seconds)
        use_baggage: Whether to include baggage items
        attributes: Additional span attributes
        complex_workflow: Whether to generate more complex workflow patterns
        
    Returns:
        The span's context for use as a parent in subsequent calls
    """
    service_info = SERVICES.get(service_name, {'name': service_name, 'version': '1.0.0', 'language': 'unknown', 'dependencies': []})
    
    # Prepare span attributes
    span_attributes = {
        'service.name': service_info['name'],
        'service.version': service_info['version'],
        'service.language': service_info['language'],
    }
    
    # Add custom attributes if provided
    if attributes:
        span_attributes.update(attributes)
    
    # Calculate a realistic latency if not specified
    if latency is None:
        # Base latency plus some randomness
        latency = 0.05 + random.uniform(0, 0.2)
        
        # Add occasional spikes for realism
        if random.random() < 0.1:
            latency += random.uniform(0.2, 0.5)
    
    # Set up context with baggage if needed
    current_context = context.get_current()
    if use_baggage and not parent_context:
        # Add baggage items for cross-service context propagation
        current_context = baggage.set_baggage("transaction.id", str(uuid.uuid4()), context=current_context)
        current_context = baggage.set_baggage("user.id", f"user-{random.randint(1000, 9999)}", context=current_context)
    
    # Use the provided parent context or the current context
    ctx = parent_context or current_context
    
    # Create and start the span
    with tracer.start_as_current_span(
        operation_name,
        context=ctx,
        kind=trace.SpanKind.SERVER if "receive" in operation_name else trace.SpanKind.CLIENT,
        attributes=span_attributes
    ) as span:
        span_ctx = trace.get_current_span().get_span_context()
        trace_id = trace.format_trace_id(span_ctx.trace_id)
        span_id = trace.format_span_id(span_ctx.span_id)
        
        # Log the operation start with trace context
        otel_logger.info(
            f"Service {service_name} executing {operation_name}",
            extra={
                "trace_id": trace_id,
                "span_id": span_id,
                "service": service_name,
                "operation": operation_name,
            }
        )
        
        # Simulate the work
        time.sleep(latency)
        
        # Simulate an error if requested
        if is_error:
            error_msg = f"Error in {service_name} during {operation_name}"
            otel_logger.error(
                error_msg,
                extra={
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "service": service_name,
                    "operation": operation_name,
                }
            )
            span.set_status(trace.StatusCode.ERROR, error_msg)
            span.record_exception(Exception(error_msg))
        else:
            # Log successful completion
            otel_logger.info(
                f"Service {service_name} completed {operation_name} successfully",
                extra={
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "service": service_name,
                    "operation": operation_name,
                }
            )
        
        # Return the current context for use as a parent in subsequent calls
        return context.get_current()

def simulate_api_request(
    tracer,
    otel_logger,
    endpoint: str,
    method: str = "GET",
    complex_workflow: bool = False
):
    """
    Simulate a complete API request flowing through multiple services.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        endpoint: API endpoint being called
        method: HTTP method being used
        complex_workflow: Whether to generate more complex workflow patterns
    """
    # Replace any ID placeholders in the endpoint
    if "{id}" in endpoint:
        endpoint = endpoint.replace("{id}", str(random.randint(1, 1000)))
    
    # Start with the API Gateway
    request_id = str(uuid.uuid4())
    
    # Prepare initial attributes
    attributes = {
        "http.method": method,
        "http.url": endpoint,
        "http.request_id": request_id,
    }
    
    # Generate ~10% of requests as errors
    is_error_case = random.random() < 0.1
    
    try:
        # Start with API Gateway receiving the request
        gateway_ctx = simulate_service_call(
            tracer,
            otel_logger,
            "api-gateway",
            f"receive_{method}_{endpoint.replace('/', '_')}",
            attributes=attributes,
            complex_workflow=complex_workflow
        )
        
        # Authenticate via auth-service (if not a GET request)
        if method != "GET":
            auth_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "api-gateway",
                "call_auth_service",
                parent_context=gateway_ctx,
                complex_workflow=complex_workflow
            )
            
            auth_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "auth-service",
                "receive_authenticate_request",
                parent_context=auth_ctx,
                complex_workflow=complex_workflow
            )
            
            # Auth service calls user service
            auth_user_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "auth-service",
                "call_user_service",
                parent_context=auth_receive_ctx,
                complex_workflow=complex_workflow
            )
            
            user_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "user-service",
                "receive_user_lookup",
                parent_context=auth_user_ctx,
                complex_workflow=complex_workflow
            )
            
            # User service calls database
            user_db_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "user-service",
                "call_database",
                parent_context=user_receive_ctx,
                complex_workflow=complex_workflow
            )
            
            db_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "db-service", 
                "receive_query",
                parent_context=user_db_ctx,
                complex_workflow=complex_workflow
            )
            
        # Handle based on endpoint
        if endpoint.startswith("/api/v1/products"):
            # Call product service
            product_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "api-gateway",
                "call_product_service",
                parent_context=gateway_ctx,
                complex_workflow=complex_workflow
            )
            
            product_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "product-service",
                "receive_product_request",
                parent_context=product_ctx,
                complex_workflow=complex_workflow
            )
            
            # Product service calls inventory service
            inventory_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "product-service",
                "call_inventory_service",
                parent_context=product_receive_ctx,
                is_error=is_error_case and endpoint.endswith("999"),  # Error for specific product ID
                complex_workflow=complex_workflow
            )
            
            if not (is_error_case and endpoint.endswith("999")):
                inventory_receive_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "inventory-service",
                    "receive_inventory_check",
                    parent_context=inventory_ctx,
                    complex_workflow=complex_workflow
                )
                
                # Inventory calls database
                inv_db_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "inventory-service",
                    "call_database",
                    parent_context=inventory_receive_ctx,
                    complex_workflow=complex_workflow
                )
                
                db_inv_receive_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "db-service",
                    "receive_query",
                    parent_context=inv_db_ctx,
                    complex_workflow=complex_workflow
                )
            
            # Product service calls pricing service
            pricing_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "product-service",
                "call_pricing_service",
                parent_context=product_receive_ctx,
                complex_workflow=complex_workflow
            )
            
            pricing_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "pricing-service",
                "receive_pricing_request",
                parent_context=pricing_ctx,
                complex_workflow=complex_workflow
            )
            
            # Pricing calls database
            pricing_db_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "pricing-service",
                "call_database",
                parent_context=pricing_receive_ctx,
                complex_workflow=complex_workflow
            )
            
            db_pricing_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "db-service",
                "receive_query",
                parent_context=pricing_db_ctx,
                complex_workflow=complex_workflow
            )
            
            # If we're getting a single product, get recommendations too
            if "/api/v1/products/" in endpoint and not endpoint.endswith("/products"):
                recommend_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "product-service",
                    "call_recommendation_service",
                    parent_context=product_receive_ctx,
                    complex_workflow=complex_workflow
                )
                
                recommend_receive_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "recommendation-service",
                    "receive_recommendation_request",
                    parent_context=recommend_ctx,
                    complex_workflow=complex_workflow
                )
                
                # Recommendation service calls DB
                rec_db_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "recommendation-service",
                    "call_database",
                    parent_context=recommend_receive_ctx,
                    complex_workflow=complex_workflow
                )
                
                db_rec_receive_ctx = simulate_service_call(
                    tracer,
                    otel_logger,
                    "db-service",
                    "receive_query",
                    parent_context=rec_db_ctx,
                    complex_workflow=complex_workflow
                )
                
                # Recommendation service calls analytics
                if complex_workflow:
                    rec_analytics_ctx = simulate_service_call(
                        tracer,
                        otel_logger,
                        "recommendation-service",
                        "call_analytics_service",
                        parent_context=recommend_receive_ctx,
                        complex_workflow=complex_workflow
                    )
                    
                    analytics_receive_ctx = simulate_service_call(
                        tracer,
                        otel_logger,
                        "analytics-service",
                        "receive_analytics_request",
                        parent_context=rec_analytics_ctx,
                        complex_workflow=complex_workflow
                    )
                    
                    # Analytics service calls DB
                    analytics_db_ctx = simulate_service_call(
                        tracer,
                        otel_logger,
                        "analytics-service",
                        "call_database",
                        parent_context=analytics_receive_ctx,
                        complex_workflow=complex_workflow
                    )
                    
                    db_analytics_receive_ctx = simulate_service_call(
                        tracer,
                        otel_logger,
                        "db-service",
                        "receive_query",
                        parent_context=analytics_db_ctx,
                        complex_workflow=complex_workflow
                    )
        
        elif endpoint.startswith("/api/v1/users"):
            # Call user service
            user_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "api-gateway",
                "call_user_service",
                parent_context=gateway_ctx,
                complex_workflow=complex_workflow
            )
            
            user_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "user-service",
                "receive_user_request",
                parent_context=user_ctx,
                complex_workflow=complex_workflow
            )
            
            # User service calls database
            user_db_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "user-service",
                "call_database",
                parent_context=user_receive_ctx,
                complex_workflow=complex_workflow
            )
            
            db_user_receive_ctx = simulate_service_call(
                tracer,
                otel_logger,
                "db-service",
                "receive_query",
                parent_context=user_db_ctx,
                complex_workflow=complex_workflow
            )
        
        # Additional complex workflows can be added here when complex_workflow=True
        
    except Exception as e:
        logger.error(f"Error simulating API request: {str(e)}", exc_info=True)

def main():
    """Main execution function."""
    args = parse_args()
    
    # Print configuration details
    logger.info("OpenTelemetry Multi-Agent Workflow Simulation")
    logger.info("-" * 50)
    
    try:
        # Set up telemetry
        tracer, otel_logger = setup_telemetry(
            endpoint=args.endpoint,
            insecure=args.insecure
        )
        
        # Simulate API requests
        logger.info(f"Simulating {args.num_requests} API requests with complex_workflow={args.complex}")
        
        for i in range(args.num_requests):
            # Randomly select endpoint and method
            endpoint = random.choice(ENDPOINTS)
            method = random.choice(METHODS)
            
            logger.info(f"Simulating request {i+1}/{args.num_requests}: {method} {endpoint}")
            simulate_api_request(
                tracer=tracer,
                otel_logger=otel_logger,
                endpoint=endpoint,
                method=method,
                complex_workflow=args.complex
            )
            
            # Small delay between requests
            time.sleep(random.uniform(0.5, 1.5))
        
        logger.info("Simulation complete! Check Jaeger to visualize the generated traces.")
        logger.info("Look for traces from service 'otel-simulation'")
        
        # Give time for exporters to flush
        time.sleep(5)
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
