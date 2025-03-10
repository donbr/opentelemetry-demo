# OpenTelemetry Validation Scripts

## Three Specialized Scripts

1. **Multi-Agent Workflow Simulation** (`multi-agent-workflow.py`):
   - Simulates realistic microservices interactions with parent-child relationships
   - Creates spans across multiple services in an e-commerce checkout flow
   - Demonstrates how distributed traces appear in Jaeger

2. **Error Path Analysis** (`error-path-analysis.py`):
   - Simulates various error scenarios (timeouts, validation failures, etc.)
   - Shows retry patterns and how errors propagate through services
   - Creates realistic error states with attributes and exceptions

3. **Cross-Service Context Propagation** (`baggage-propagation.py`):
   - Demonstrates how to use baggage to carry business context across services
   - Shows context enrichment at service boundaries
   - Creates business-meaningful traces with domain-specific attributes

## Enhanced Unified Validation Script

A unified script (`otel-validation-updated.py`) that combines all three approaches in a single tool with multiple modes:

- **Connectivity mode**: Basic validation that your collector is reachable
- **Multi-agent mode**: Complex workflow simulation
- **Error-path mode**: Error propagation testing
- **Context mode**: Baggage propagation testing

## Why These Scenarios Are Meaningful

These scenarios were chosen to showcase key strengths of OpenTelemetry and Jaeger:

1. **Multi-Agent Workflows** demonstrate the core value proposition of distributed tracing - understanding how requests flow across service boundaries, where time is spent, and how services interact.

2. **Error Path Analysis** provides visibility into failure modes, which is critical for reliability. This script helps you:
   - Understand how errors propagate through your microservices architecture
   - Visualize retry patterns and their effectiveness
   - See how circuit breakers and fallback mechanisms behave under real conditions
   - Identify cascading failures before they happen in production

3. **Cross-Service Context Propagation** demonstrates how to carry business-meaningful information alongside your traces, which is essential for:
   - Correlating technical operations with business transactions
   - Filtering traces by business dimensions (user tier, geography, etc.)
   - Enriching observability data with business context

## Using the Scripts

The most important aspect is specifying the right endpoint URL with your Docker port mapping:

```bash
python otel_validation_updated.py --endpoint http://localhost:55762 --mode multi-agent
```

Remember to replace `55762` with the actual port mapped to your collector's gRPC endpoint (4317).

## Recommended Next Steps

1. Start with basic connectivity testing:
   ```bash
   python otel_validation_updated.py --endpoint http://localhost:<port>
   ```

2. Explore multi-agent workflows to see complete request flows:
   ```bash
   python otel_validation_updated.py --endpoint http://localhost:<port> --mode multi-agent
   ```

3. Test error scenarios and see how they appear in Jaeger:
   ```bash
   python otel_validation_updated.py --endpoint http://localhost:<port> --mode error-path
   ```

4. Examine context propagation capabilities:
   ```bash
   python otel_validation_updated.py --endpoint http://localhost:<port> --mode context
   ```

Each of these scenarios will help you validate different aspects of your OpenTelemetry deployment and give you confidence that your instrumentation is working correctly.
