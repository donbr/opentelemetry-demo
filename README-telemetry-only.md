# Running OpenTelemetry Demo in Telemetry-Only Mode

This guide explains how to run just the telemetry components of the OpenTelemetry Demo without the core demo services. This lightweight configuration is ideal for:

- Running with minimal resource consumption
- Monitoring your own applications with a complete telemetry stack
- Exploring Jaeger and Grafana functionality independently

## Architecture Overview

This setup is based on the [OpenTelemetry Demo Architecture](https://opentelemetry.io/docs/demo/architecture/).

```mermaid
graph TB
subgraph tdf[Telemetry Data Flow]
    subgraph subgraph_padding [ ]
        style subgraph_padding fill:none,stroke:none;
        subgraph od[OpenTelemetry Demo]
        ms(Microservice)
        end

        ms -.->|"OTLP<br/>gRPC"| oc-grpc
        ms -.->|"OTLP<br/>HTTP POST"| oc-http

        subgraph oc[OTel Collector]
            style oc fill:#97aef3,color:black;
            oc-grpc[/"OTLP Receiver<br/>listening on<br/>grpc://localhost:4317"/]
            oc-http[/"OTLP Receiver<br/>listening on <br/>localhost:4318<br/>"/]
            oc-proc(Processors)
            oc-prom[/"OTLP HTTP Exporter"/]
            oc-otlp[/"OTLP Exporter"/]

            oc-grpc --> oc-proc
            oc-http --> oc-proc

            oc-proc --> oc-prom
            oc-proc --> oc-otlp
        end

        oc-prom -->|"localhost:9090/api/v1/otlp"| pr-sc
        oc-otlp -->|gRPC| ja-col

        subgraph pr[Prometheus]
            style pr fill:#e75128,color:black;
            pr-sc[/"Prometheus OTLP Write Receiver"/]
            pr-tsdb[(Prometheus TSDB)]
            pr-http[/"Prometheus HTTP<br/>listening on<br/>localhost:9090"/]

            pr-sc --> pr-tsdb
            pr-tsdb --> pr-http
        end

        pr-b{{"Browser<br/>Prometheus UI"}}
        pr-http ---->|"localhost:9090/graph"| pr-b

        subgraph ja[Jaeger]
            style ja fill:#60d0e4,color:black;
            ja-col[/"Jaeger Collector<br/>listening on<br/>grpc://jaeger:4317"/]
            ja-db[(Jaeger DB)]
            ja-http[/"Jaeger HTTP<br/>listening on<br/>localhost:16686"/]

            ja-col --> ja-db
            ja-db --> ja-http
        end

        subgraph gr[Grafana]
            style gr fill:#f8b91e,color:black;
            gr-srv["Grafana Server"]
            gr-http[/"Grafana HTTP<br/>listening on<br/>localhost:3000"/]

            gr-srv --> gr-http
        end

        pr-http --> |"localhost:9090/api"| gr-srv
        ja-http --> |"localhost:16686/api"| gr-srv

        ja-b{{"Browser<br/>Jaeger UI"}}
        ja-http ---->|"localhost:16686/search"| ja-b

        gr-b{{"Browser<br/>Grafana UI"}}
        gr-http -->|"localhost:3000/dashboard"| gr-b
    end
end
```

## Quick Start

### 1. Launch the Stack

```bash
docker compose -f docker-compose-telemetry-only.yml up -d
```

### 2. Access the UIs

- **Jaeger**: [http://localhost:8080/jaeger/ui/](http://localhost:8080/jaeger/ui/)
- **Grafana**: [http://localhost:8080/grafana/](http://localhost:8080/grafana/)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)

## Implementation Details

This configuration:

- **Retains all telemetry components** (OTel Collector, Jaeger, Grafana, Prometheus, OpenSearch)
- **Minimizes dependencies** using lightweight containers for required services
- **Configures frontend-proxy (Envoy)** to route requests to appropriate telemetry UIs

## Sending Your Application's Telemetry

Configure your applications to send telemetry data to this stack:

- **For gRPC-based OTLP export**:
  ```
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
  ```

- **For HTTP-based OTLP export**:
  ```
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  ```

## Resource Requirements

Significantly lighter than the full demo:
- **RAM**: ~1.9GB (vs ~6GB for full demo)
- **CPU**: Minimal usage
- **Disk**: ~2GB for Docker images

## Troubleshooting

If you encounter issues:

```bash
# Check service status
docker compose -f docker-compose-telemetry-only.yml ps

# View logs
docker compose -f docker-compose-telemetry-only.yml logs otel-collector
docker compose -f docker-compose-telemetry-only.yml logs frontend-proxy

# Verify endpoint accessibility
curl -I http://localhost:8080/grafana/
curl -I http://localhost:8080/jaeger/ui/
curl -I http://localhost:4318
```

## Switching Back to Full Demo

```bash
# Stop telemetry-only stack
docker compose -f docker-compose-telemetry-only.yml down

# Start full demo
docker compose up -d
```