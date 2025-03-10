# Running OpenTelemetry Demo in Telemetry-Only Mode

This guide explains how to run just the telemetry components of the OpenTelemetry Demo while disabling the core demo services. This configuration is useful when you want to:

1. Run a lightweight version with minimal resources
2. Use the telemetry stack for monitoring your own applications
3. Explore Jaeger and Grafana without the demo services

## Based on OpenTelemetry Demo Architecture

- https://opentelemetry.io/docs/demo/architecture/


```mermaid
graph TB
subgraph tdf[Telemetry Data Flow]
    subgraph subgraph_padding [ ]
        style subgraph_padding fill:none,stroke:none;
        %% padding to stop the titles clashing
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

## Setup Instructions

### 1. Create the Telemetry-Only Compose File

Save the provided `docker-compose-telemetry-only.yml` file to your OpenTelemetry Demo directory.

### 2. Start the Telemetry-Only Stack

Run the following command to start just the telemetry components:

```bash
docker compose -f docker-compose-telemetry-only.yml up -d
```

### 3. Access the Telemetry UIs

Once the services are up and running, you can access:

- **Jaeger UI**: http://localhost:8080/jaeger/ui/
- **Grafana**: http://localhost:8080/grafana/
- **Prometheus**: http://localhost:9090

## How It Works

This configuration:

1. **Keeps all telemetry components**:
   - OpenTelemetry Collector
   - Jaeger
   - Grafana
   - Prometheus
   - OpenSearch

2. **Uses minimal dummy services** for essential dependencies:
   - A minimal Nginx container for the frontend
   - Alpine-based dummy containers for other required services

3. **Configures the frontend-proxy (Envoy)** to route UI requests to the appropriate telemetry UIs

## Sending Telemetry from Your Applications

You can now send telemetry data from your own applications to this stack:

1. **For traces and metrics**:
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   ```

2. **For HTTP-based OTLP export**:
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   ```

## Resource Requirements

This configuration requires significantly fewer resources than the full demo:

- **RAM**: ~1.9GB (vs ~6GB for the full demo)
- **CPU**: Minimal usage compared to the full demo
- **Disk**: ~2GB of Docker image storage

## Troubleshooting

If you encounter issues:

1. **Verify service status**:
   ```bash
   docker compose -f docker-compose-telemetry-only.yml ps
   ```

2. **Check service logs**:
   ```bash
   docker compose -f docker-compose-telemetry-only.yml logs otel-collector
   docker compose -f docker-compose-telemetry-only.yml logs frontend-proxy
   ```

3. **Verify port accessibility**:
   ```bash
   curl -I http://localhost:8080/grafana/
   curl -I http://localhost:8080/jaeger/ui/
   ```

4. **Ensure collector is accessible**:
   ```bash
   curl -I http://localhost:4318
   ```

## Returning to Full Demo Mode

To switch back to the complete demo:

```bash
# Stop telemetry-only mode
docker compose -f docker-compose-telemetry-only.yml down

# Start full demo
docker compose up -d
```
