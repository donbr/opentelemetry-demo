#!/usr/bin/env python3
"""
Error Path Analysis Simulation for OpenTelemetry

This script simulates various error scenarios in a distributed system and demonstrates
how errors propagate across service boundaries. The script creates realistic error
patterns including retries, timeouts, and cascading failures.

Usage:
    python error_path_analysis.py --endpoint http://localhost:4317

Requirements:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

import argparse
import logging
import os
import random
import sys
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple

# Import OpenTelemetry components
from opentelemetry import trace
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
logger = logging.getLogger('otel-error-simulation')

# Define error types for simulation
class ErrorType(Enum):
    TIMEOUT = "timeout"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"

# Service definitions
SERVICES = {
    'api-gateway': {
        'name': 'api-gateway',
        'version': '1.0.0',
        'language': 'python',
        'retry_enabled': True,
        'circuit_breaker_enabled': True,
    },
    'auth-service': {
        'name': 'auth-service',
        'version': '2.1.0',
        'language': 'go', 
        'retry_enabled': True,
        'circuit_breaker_enabled': False,
    },
    'payment-service': {
        'name': 'payment-service',
        'version': '1.2.0',
        'language': 'node',
        'retry_enabled': True,
        'circuit_breaker_enabled': True,
    },
    'inventory-service': {
        'name': 'inventory-service',
        'version': '1.0.1',
        'language': 'java',
        'retry_enabled': False,
        'circuit_breaker_enabled': False,
    },
    'shipping-service': {
        'name': 'shipping-service',
        'version': '1.1.0',
        'language': 'go',
        'retry_enabled': True,
        'circuit_breaker_enabled': False,
    },
    'user-service': {
        'name': 'user-service',
        'version': '2.0.0',
        'language': 'python',
        'retry_enabled': True,
        'circuit_breaker_enabled': False,
    },
    'database-service': {
        'name': 'database-service',
        'version': '1.0.0',
        'language': 'internal',
        'retry_enabled': False,
        'circuit_breaker_enabled': False,
    },
    'cache-service': {
        'name': 'cache-service',
        'version': '1.0.0',
        'language': 'internal',
        'retry_enabled': False,
        'circuit_breaker_enabled': False,
    },
    'notification-service': {
        'name': 'notification-service',
        'version': '1.0.0',
        'language': 'python',
        'retry_enabled': True,
        'circuit_breaker_enabled': False,
    },
}

# Error scenarios to simulate
ERROR_SCENARIOS = [
    {
        'name': 'database_timeout',
        'service': 'database-service',
        'error_type': ErrorType.TIMEOUT,
        'description': 'Database query timeout',
        'retryable': True,
        'retry_count': 3,
        'status_code': 500,
    },
    {
        'name': 'payment_validation_failure',
        'service': 'payment-service',
        'error_type': ErrorType.VALIDATION_ERROR,
        'description': 'Invalid payment information',
        'retryable': False,
        'retry_count': 0,
        'status_code': 400,
    },
    {
        'name': 'auth_service_unavailable',
        'service': 'auth-service',
        'error_type': ErrorType.SERVICE_UNAVAILABLE,
        'description': 'Authentication service is unavailable',
        'retryable': True,
        'retry_count': 2,
        'status_code': 503,
    },
    {
        'name': 'user_not_found',
        'service': 'user-service',
        'error_type': ErrorType.RESOURCE_NOT_FOUND,
        'description': 'User ID not found',
        'retryable': False,
        'retry_count': 0,
        'status_code': 404,
    },
    {
        'name': 'inventory_db_error',
        'service': 'inventory-service',
        'error_type': ErrorType.DATABASE_ERROR,
        'description': 'Database query failed',
        'retryable': True,
        'retry_count': 1,
        'status_code': 500,
    },
    {
        'name': 'shipping_rate_limited',
        'service': 'shipping-service',
        'error_type': ErrorType.RATE_LIMITED,
        'description': 'Too many requests to shipping service',
        'retryable': True,
        'retry_count': 3,
        'status_code': 429,
    },
    {
        'name': 'gateway_timeout',
        'service': 'api-gateway',
        'error_type': ErrorType.TIMEOUT,
        'description': 'Request timed out at gateway',
        'retryable': False,
        'retry_count': 0,
        'status_code': 504,
    },
    {
        'name': 'cache_network_error',
        'service': 'cache-service',
        'error_type': ErrorType.NETWORK_ERROR,
        'description': 'Network error connecting to cache',
        'retryable': True,
        'retry_count': 2,
        'status_code': 500,
    },
    {
        'name': 'notification_authorization_error',
        'service': 'notification-service',
        'error_type': ErrorType.AUTHORIZATION_ERROR,
        'description': 'Not authorized to send notifications',
        'retryable': False,
        'retry_count': 0,
        'status_code': 403,
    },
]

# Workflow definitions
WORKFLOWS = [
    {
        'name': 'checkout_flow',
        'description': 'Customer checkout process',
        'steps': [
            {'service': 'api-gateway', 'operation': 'receive_checkout_request'},
            {'service': 'auth-service', 'operation': 'validate_session'},
            {'service': 'user-service', 'operation': 'get_user_details'},
            {'service': 'payment-service', 'operation': 'process_payment'},
            {'service': 'inventory-service', 'operation': 'update_inventory'},
            {'service': 'shipping-service', 'operation': 'create_shipment'},
            {'service': 'notification-service', 'operation': 'send_order_confirmation'},
        ]
    },
    {
        'name': 'user_registration',
        'description': 'New user registration',
        'steps': [
            {'service': 'api-gateway', 'operation': 'receive_registration_request'},
            {'service': 'user-service', 'operation': 'validate_user_data'},
            {'service': 'user-service', 'operation': 'create_user'},
            {'service': 'database-service', 'operation': 'store_user_record'},
            {'service': 'auth-service', 'operation': 'generate_credentials'},
            {'service': 'notification-service', 'operation': 'send_welcome_email'},
        ]
    },
    {
        'name': 'product_search',
        'description': 'Search for products',
        'steps': [
            {'service': 'api-gateway', 'operation': 'receive_search_request'},
            {'service': 'cache-service', 'operation': 'check_cache'},
            {'service': 'inventory-service', 'operation': 'search_products'},
            {'service': 'database-service', 'operation': 'query_product_database'},
            {'service': 'cache-service', 'operation': 'update_cache'},
        ]
    }
]

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Error Path Analysis Simulation for OpenTelemetry')
    parser.add_argument('--endpoint', default=os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317'),
                        help='OTLP endpoint URL (default: http://localhost:4317)')
    parser.add_argument('--insecure', action='store_true', default=True,
                        help='Use insecure connection (default: True)')
    parser.add_argument('--num-workflows', type=int, default=5,
                        help='Number of workflows to simulate (default: 5)')
    parser.add_argument('--error-probability', type=float, default=0.7,
                        help='Probability of introducing an error (0-1, default: 0.7)')
    return parser.parse_args()

def setup_telemetry(endpoint: str, insecure: bool = True) -> Tuple[object, object]:
    """Set up OpenTelemetry tracing and logging."""
    # Create a unique ID for this simulation run
    simulation_id = str(uuid.uuid4())[:8]
    
    # Create a resource with service information
    resource = Resource.create({
        "service.name": "otel-error-simulation",
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
    tracer = trace.get_tracer("error-simulation-tracer")
    
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
    otel_logger = logging.getLogger("error-simulation-logger")
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    otel_logger.addHandler(otel_handler)
    otel_logger.setLevel(logging.INFO)
    
    return tracer, otel_logger

def create_span(
    tracer,
    otel_logger,
    service_name: str,
    operation_name: str,
    parent_context=None,
    attributes: Dict = None,
    error_scenario=None,
    retry_attempt: int = 0
) -> Optional[trace.SpanContext]:
    """
    Create a span for a service operation, optionally with an error scenario.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        service_name: Name of the service 
        operation_name: Name of the operation
        parent_context: Parent context for the span
        attributes: Additional span attributes
        error_scenario: Error scenario to simulate (if any)
        retry_attempt: Current retry attempt (0 = first attempt)
        
    Returns:
        The span's context or None if span creation failed
    """
    service_info = SERVICES.get(service_name, {
        'name': service_name, 
        'version': '1.0.0',
        'language': 'unknown',
        'retry_enabled': False,
        'circuit_breaker_enabled': False,
    })
    
    # Prepare span attributes
    span_attributes = {
        'service.name': service_info['name'],
        'service.version': service_info['version'],
        'service.language': service_info['language'],
        'retry.enabled': service_info['retry_enabled'],
        'circuit_breaker.enabled': service_info['circuit_breaker_enabled'],
    }
    
    # Add retry information if this is a retry
    if retry_attempt > 0:
        span_attributes['retry.attempt'] = retry_attempt
    
    # Add custom attributes if provided
    if attributes:
        span_attributes.update(attributes)
    
    # Calculate a realistic latency (higher for errors)
    if error_scenario:
        latency = 0.1 + random.uniform(0.3, 1.0)  # Errors take longer
    else:
        latency = 0.05 + random.uniform(0, 0.2)   # Normal operations are faster
    
    # Create and start the span
    with tracer.start_as_current_span(
        operation_name,
        context=parent_context,
        kind=trace.SpanKind.SERVER if "receive" in operation_name else trace.SpanKind.CLIENT,
        attributes=span_attributes
    ) as span:
        span_ctx = trace.get_current_span().get_span_context()
        trace_id = trace.format_trace_id(span_ctx.trace_id)
        span_id = trace.format_span_id(span_ctx.span_id)
        
        # Prepare log context
        log_context = {
            "trace_id": trace_id,
            "span_id": span_id,
            "service": service_name,
            "operation": operation_name,
        }
        
        # Log the operation start
        if retry_attempt > 0:
            otel_logger.info(
                f"Service {service_name} executing {operation_name} (retry attempt {retry_attempt})",
                extra=log_context
            )
        else:
            otel_logger.info(
                f"Service {service_name} executing {operation_name}",
                extra=log_context
            )
        
        # Simulate the work
        time.sleep(latency)
        
        # Handle error scenario if present
        if error_scenario:
            error_type = error_scenario['error_type']
            error_desc = error_scenario['description']
            status_code = error_scenario['status_code']
            
            # Add error attributes
            span.set_attribute("error", True)
            span.set_attribute("error.type", error_type.value)
            span.set_attribute("error.description", error_desc)
            span.set_attribute("http.status_code", status_code)
            
            # Create specific error message
            error_msg = f"Error in {service_name} during {operation_name}: {error_desc}"
            
            # Log the error with context
            otel_logger.error(
                error_msg,
                extra=log_context
            )
            
            # Set span status to error
            span.set_status(trace.StatusCode.ERROR, error_msg)
            
            # Create an exception based on the error type
            if error_type == ErrorType.TIMEOUT:
                exception = TimeoutError(error_msg)
            elif error_type == ErrorType.DATABASE_ERROR:
                exception = Exception(f"Database error: {error_msg}")
            elif error_type == ErrorType.VALIDATION_ERROR:
                exception = ValueError(error_msg)
            elif error_type == ErrorType.AUTHORIZATION_ERROR:
                exception = PermissionError(error_msg)
            elif error_type == ErrorType.RESOURCE_NOT_FOUND:
                exception = FileNotFoundError(error_msg)
            elif error_type == ErrorType.SERVICE_UNAVAILABLE:
                exception = ConnectionRefusedError(error_msg)
            elif error_type == ErrorType.RATE_LIMITED:
                exception = Exception(f"Rate limited: {error_msg}")
            elif error_type == ErrorType.NETWORK_ERROR:
                exception = ConnectionError(error_msg)
            else:
                exception = Exception(error_msg)
                
            # Record the exception
            span.record_exception(exception)
            
            # Return None to indicate failure
            return None
        else:
            # Log successful completion
            otel_logger.info(
                f"Service {service_name} completed {operation_name} successfully",
                extra=log_context
            )
            
            # Return the span's context for use as a parent in subsequent calls
            return span_ctx

def simulate_workflow_step(
    tracer,
    otel_logger,
    workflow_name: str,
    step: Dict,
    parent_context=None,
    error_probability: float = 0.0,
    current_step: int = 0,
    total_steps: int = 0
) -> Tuple[Optional[trace.SpanContext], bool]:
    """
    Simulate a single step in a workflow, with possibility of error.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger  
        workflow_name: Name of the workflow
        step: Step definition (service and operation)
        parent_context: Parent context for the span
        error_probability: Probability of introducing an error (0-1)
        current_step: Current step number
        total_steps: Total number of steps
        
    Returns:
        Tuple of (span_context, success)
    """
    service_name = step['service']
    operation_name = step['operation']
    
    # Prepare span attributes
    attributes = {
        'workflow.name': workflow_name,
        'step.number': current_step,
        'step.total': total_steps,
    }
    
    # Determine if we should introduce an error
    introduce_error = random.random() < error_probability
    error_scenario = None
    
    if introduce_error:
        # Find eligible error scenarios for this service
        eligible_scenarios = [
            scenario for scenario in ERROR_SCENARIOS
            if scenario['service'] == service_name
        ]
        
        if eligible_scenarios:
            error_scenario = random.choice(eligible_scenarios)
            
    # Create the span
    span_ctx = create_span(
        tracer=tracer,
        otel_logger=otel_logger,
        service_name=service_name,
        operation_name=operation_name,
        parent_context=parent_context,
        attributes=attributes,
        error_scenario=error_scenario
    )
    
    # Handle retries if the operation failed and is retryable
    if span_ctx is None and error_scenario and error_scenario['retryable'] and SERVICES[service_name]['retry_enabled']:
        retry_count = error_scenario['retry_count']
        retry_success = False
        
        for retry_attempt in range(1, retry_count + 1):
            # Add some delay before retry
            time.sleep(0.1 * (2 ** retry_attempt))  # Exponential backoff
            
            # Prepare retry attributes 
            retry_attributes = attributes.copy()
            retry_attributes['retry.attempt'] = retry_attempt
            retry_attributes['retry.max_attempts'] = retry_count
            
            # Determine if this retry will succeed (higher chance of success with each retry)
            retry_error_prob = error_probability * (0.5 ** retry_attempt)
            retry_error = random.random() < retry_error_prob
            
            # Create span for the retry
            retry_error_scenario = error_scenario if retry_error else None
            span_ctx = create_span(
                tracer=tracer,
                otel_logger=otel_logger,
                service_name=service_name,
                operation_name=operation_name,
                parent_context=parent_context,
                attributes=retry_attributes,
                error_scenario=retry_error_scenario,
                retry_attempt=retry_attempt
            )
            
            # If retry succeeded, we're done
            if span_ctx is not None:
                retry_success = True
                break
                
        # Return the result of the retry attempt
        return span_ctx, retry_success
    
    # Return success if we got a span context
    return span_ctx, span_ctx is not None

def simulate_workflow(
    tracer,
    otel_logger,
    workflow: Dict,
    error_probability: float = 0.0
):
    """
    Simulate a complete workflow with potential errors and retries.
    
    Args:
        tracer: OpenTelemetry tracer
        otel_logger: OpenTelemetry logger
        workflow: Workflow definition
        error_probability: Probability of introducing an error at each step
    """
    workflow_name = workflow['name']
    steps = workflow['steps']
    total_steps = len(steps)
    
    logger.info(f"Simulating workflow: {workflow_name} ({workflow['description']})")
    
    # Generate a correlation ID for this workflow
    correlation_id = str(uuid.uuid4())
    
    # Start with the first step
    parent_context = None
    workflow_success = True
    
    for i, step in enumerate(steps):
        # If a previous step failed without recovery, we'll follow the error path
        if not workflow_success and step['service'] != 'notification-service':
            # Skip this step because of earlier failure, unless it's notification service
            # (which might send failure notifications)
            continue
            
        step_ctx, step_success = simulate_workflow_step(
            tracer=tracer,
            otel_logger=otel_logger,
            workflow_name=workflow_name,
            step=step,
            parent_context=parent_context,
            error_probability=error_probability,
            current_step=i+1,
            total_steps=total_steps
        )
        
        # Update workflow status based on step result
        workflow_success = workflow_success and step_success
        
        # Use this step's context for the next step
        if step_ctx is not None:
            parent_context = step_ctx
            
    # Log overall workflow result
    if workflow_success:
        logger.info(f"Workflow {workflow_name} completed successfully")
    else:
        logger.info(f"Workflow {workflow_name} failed")
        
    return workflow_success

def main():
    """Main execution function."""
    args = parse_args()
    
    # Print configuration details
    logger.info("OpenTelemetry Error Path Analysis Simulation")
    logger.info("-" * 50)
    
    try:
        # Set up telemetry
        tracer, otel_logger = setup_telemetry(
            endpoint=args.endpoint,
            insecure=args.insecure
        )
        
        # Simulate workflows
        logger.info(f"Simulating {args.num_workflows} workflows with error probability {args.error_probability}")
        
        for i in range(args.num_workflows):
            # Select a random workflow
            workflow = random.choice(WORKFLOWS)
            
            logger.info(f"Workflow {i+1}/{args.num_workflows}: {workflow['name']}")
            workflow_success = simulate_workflow(
                tracer=tracer,
                otel_logger=otel_logger,
                workflow=workflow,
                error_probability=args.error_probability
            )
            
            # Small delay between workflows
            time.sleep(random.uniform(0.5, 1.5))
        
        logger.info("Simulation complete! Check Jaeger to visualize the error paths.")
        logger.info("Look for traces from service 'otel-error-simulation'")
        
        # Give time for exporters to flush
        time.sleep(5)
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
