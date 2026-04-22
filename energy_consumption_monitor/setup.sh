{
  "dashboard": {
    "title": "Energy Monitor - System Overview",
    "tags": ["energy", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Total Power Consumption",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "datasource": "TimescaleDB",
            "rawSql": "SELECT time, SUM(power_watts) as total_power FROM sensor_data WHERE $__timeFilter(time) GROUP BY time ORDER BY time",
            "format": "time_series"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "watt",
            "color": {"mode": "palette-classic"}
          }
        }
      },
      {
        "id": 2,
        "title": "Power by Device",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "datasource": "TimescaleDB",
            "rawSql": "SELECT time, device_id, power_watts FROM sensor_data WHERE $__timeFilter(time) ORDER BY time",
            "format": "time_series"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "watt"
          }
        }
      },
      {
        "id": 3,
        "title": "Active Devices",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "energy_monitor_active_devices"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "none",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": null, "color": "green"},
                {"value": 0, "color": "red"}
              ]
            }
          }
        }
      },
      {
        "id": 4,
        "title": "MQTT Messages/sec",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "rate(energy_monitor_mqtt_messages_received_total[1m])"
          }
        ]
      },
      {
        "id": 5,
        "title": "ML Anomalies Detected",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "increase(energy_monitor_ml_anomalies_detected_total[5m])"
          }
        ]
      },
      {
        "id": 6,
        "title": "System Health",
        "type": "stat",
        "gridPos": {"h": 4, "w": 12, "x": 12, "y": 8},
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "energy_monitor_mqtt_connected"
          },
          {
            "datasource": "Prometheus",
            "expr": "energy_monitor_database_connected"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {"type": "value", "options": {"0": {"text": "Disconnected", "color": "red"}}},
              {"type": "value", "options": {"1": {"text": "Connected", "color": "green"}}}
            ]
          }
        }
      },
      {
        "id": 7,
        "title": "Energy Consumption (kWh)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 20},
        "targets": [
          {
            "datasource": "TimescaleDB",
            "rawSql": "SELECT bucket as time, device_id, total_kwh_approx FROM sensor_data_daily WHERE $__timeFilter(bucket) ORDER BY bucket",
            "format": "time_series"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "kwatth"
          }
        }
      },
      {
        "id": 8,
        "title": "Alert Rate",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
        "targets": [
          {
            "datasource": "Prometheus",
            "expr": "rate(energy_monitor_alerts_created_total[5m])"
          }
        ]
      }
    ],
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {
      "refresh_intervals": ["5s", "10s", "30s", "1m", "5m"]
    }
  }
}
