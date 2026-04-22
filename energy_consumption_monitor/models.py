"""
Prometheus Metrics for Energy Monitor
Exports operational metrics for monitoring
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import logging

logger = logging.getLogger(__name__)

# API metrics
api_requests_total = Counter(
    'energy_monitor_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

api_request_duration_seconds = Histogram(
    'energy_monitor_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint']
)

# Data ingestion metrics
mqtt_messages_received_total = Counter(
    'energy_monitor_mqtt_messages_received_total',
    'Total MQTT messages received',
    ['topic']
)

mqtt_messages_processed_total = Counter(
    'energy_monitor_mqtt_messages_processed_total',
    'Total MQTT messages successfully processed'
)

mqtt_messages_failed_total = Counter(
    'energy_monitor_mqtt_messages_failed_total',
    'Total MQTT messages that failed processing',
    ['error_type']
)

database_inserts_total = Counter(
    'energy_monitor_database_inserts_total',
    'Total database inserts'
)

database_insert_errors_total = Counter(
    'energy_monitor_database_insert_errors_total',
    'Total database insert errors'
)

database_query_duration_seconds = Histogram(
    'energy_monitor_database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type']
)

# Alert metrics
alerts_created_total = Counter(
    'energy_monitor_alerts_created_total',
    'Total alerts created',
    ['alert_type', 'severity']
)

alerts_resolved_total = Counter(
    'energy_monitor_alerts_resolved_total',
    'Total alerts resolved',
    ['alert_type']
)

# Device metrics
active_devices = Gauge(
    'energy_monitor_active_devices',
    'Number of active devices reporting data'
)

# Current power metrics (updated periodically)
device_power_watts = Gauge(
    'energy_monitor_device_power_watts',
    'Current power consumption in watts',
    ['device_id', 'location']
)

device_voltage_volts = Gauge(
    'energy_monitor_device_voltage_volts',
    'Current voltage in volts',
    ['device_id', 'location']
)

device_current_amps = Gauge(
    'energy_monitor_device_current_amps',
    'Current draw in amps',
    ['device_id', 'location']
)

# ML model metrics
ml_anomalies_detected_total = Counter(
    'energy_monitor_ml_anomalies_detected_total',
    'Total ML anomalies detected',
    ['device_id']
)

ml_model_training_duration_seconds = Histogram(
    'energy_monitor_ml_model_training_duration_seconds',
    'ML model training duration in seconds',
    ['device_id']
)

ml_models_active = Gauge(
    'energy_monitor_ml_models_active',
    'Number of active ML models'
)

# System health metrics
mqtt_connected = Gauge(
    'energy_monitor_mqtt_connected',
    'MQTT broker connection status (1=connected, 0=disconnected)'
)

database_connected = Gauge(
    'energy_monitor_database_connected',
    'Database connection status (1=connected, 0=disconnected)'
)


def metrics_response() -> Response:
    """Generate Prometheus metrics response"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


class MetricsMiddleware:
    """Middleware to track API request metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope["method"]
        path = scope["path"]
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return
        
        # Track request
        with api_request_duration_seconds.labels(method=method, endpoint=path).time():
            
            # Capture status code
            status_code = 500  # Default
            
            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)
            
            try:
                await self.app(scope, receive, send_wrapper)
                api_requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=status_code
                ).inc()
            except Exception as e:
                api_requests_total.labels(
                    method=method,
                    endpoint=path,
                    status=500
                ).inc()
                raise
