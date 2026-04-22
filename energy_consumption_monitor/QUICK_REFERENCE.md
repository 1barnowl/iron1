global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'energy-monitor'

# Alerting configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets: []

# Scrape configurations
scrape_configs:
  # Backend API metrics
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # PostgreSQL/TimescaleDB metrics (if exporter is added later)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    honor_labels: true
