# Energy Consumption Monitor - v0.2 Production Release

## 🚀 What's New in v0.2

**CRITICAL FIXES:**
- ✅ **Fixed Energy Math**: Proper trapezoidal integration (was off by 180x)
- ✅ **MQTT Authentication**: Password-protected broker
- ✅ **Real ML Anomaly Detection**: Isolation Forest per device
- ✅ **Configurable Alerts**: Device-specific thresholds
- ✅ **Data Retention**: Automatic compression & cleanup
- ✅ **Production Observability**: Prometheus + Grafana

**See CHANGELOG_v0.2.md for complete details**

---

## Overview

This is an enterprise-grade Energy Consumption Monitoring platform built entirely with open-source technologies. It provides real-time monitoring, historical analytics, ML-based anomaly detection, and cost estimation for electrical energy consumption.

**NO SIMULATORS. REAL DATA ONLY.**

## Architecture

The system consists of five main components:

1. **TimescaleDB** - PostgreSQL with TimescaleDB extension for time-series data storage
2. **Eclipse Mosquitto** - MQTT broker for real-time sensor data ingestion
3. **FastAPI Backend** - REST API service handling data processing and business logic
4. **Streamlit Dashboard** - Interactive web-based visualization interface
5. **Data Simulator** - Generates realistic sensor data for testing

## Features (v0.1)

### Current Capabilities
- ✅ Real-time power monitoring (sub-second latency)
- ✅ Multi-device tracking with location-based organization
- ✅ Historical data storage with automatic downsampling
- ✅ Interactive dashboards with auto-refresh
- ✅ Basic cost estimation
- ✅ Device statistics and analytics
- ✅ RESTful API for integration
- ✅ MQTT-based data ingestion
- ✅ Docker containerized deployment

### Planned Enhancements (Roadmap)
- 🔄 Advanced anomaly detection using ML models
- 🔄 Predictive maintenance alerts
- 🔄 Time-of-Use (TOU) billing simulation
- 🔄 Demand charge optimization
- 🔄 NILM (Non-Intrusive Load Monitoring) disaggregation
- 🔄 OpenADR integration for demand response
- 🔄 Grafana dashboards for operational metrics
- 🔄 Node-RED flows for automation
- 🔄 Authentication and multi-tenancy

## Prerequisites

### System Requirements
- **OS**: Kali Linux (or any Linux distribution with Docker support)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space
- **CPU**: 2 cores minimum, 4 cores recommended

### Software Requirements
- Docker (version 20.10 or higher)
- Docker Compose (version 1.29 or higher)

## Installation

### 1. Install Docker and Docker Compose

On Kali Linux:
```bash
# Update package list
sudo apt update

# Install Docker
sudo apt install -y docker.io

# Install Docker Compose
sudo apt install -y docker-compose

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Log out and log back in, or run:
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

### 2. Extract and Navigate to Project

```bash
# Extract the project (if zipped)
unzip energy-monitor-starter.zip
cd energy-monitor-starter

# Verify directory structure
ls -la
```

### 3. Start the Platform

```bash
# Build and start all services
docker-compose up -d

# Check if all containers are running
docker-compose ps

# View logs
docker-compose logs -f
```

The first startup will take several minutes as it:
- Downloads Docker images
- Builds custom containers
- Initializes the database schema
- Starts all services

### 4. Access the Platform

Once all services are running:

- **Dashboard**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **MQTT Broker**: localhost:1883 (for external clients)
- **Database**: localhost:5432 (credentials in docker-compose.yml)

## Usage

### Viewing the Dashboard

1. Open browser to http://localhost:8501
2. The dashboard shows:
   - **Overview Tab**: Real-time power consumption across all devices
   - **Device Details Tab**: Historical trends for individual devices
   - **Cost Analysis Tab**: Energy cost estimates
   - **Alerts Tab**: (Coming soon) Anomaly detection and warnings

### Using the API

The FastAPI backend provides a comprehensive REST API:

```bash
# Get system health
curl http://localhost:8000/health

# Get all devices
curl http://localhost:8000/devices

# Get current power readings
curl http://localhost:8000/sensors/current

# Get device history (last 24 hours)
curl http://localhost:8000/sensors/DEVICE001/history?hours=24

# Get cost estimate
curl http://localhost:8000/analytics/cost-estimate?hours=24
```

Interactive API documentation: http://localhost:8000/docs

### Publishing Custom Sensor Data

You can publish your own sensor data to MQTT:

```python
import paho.mqtt.client as mqtt
import json
from datetime import datetime

client = mqtt.Client()
client.connect("localhost", 1883, 60)

data = {
    "device_id": "CUSTOM001",
    "location": "My Lab",
    "power_watts": 1234.56,
    "voltage": 120.0,
    "current": 10.3,
    "power_factor": 0.95,
    "frequency": 60.0,
    "timestamp": datetime.utcnow().isoformat()
}

client.publish("energy/sensors/CUSTOM001", json.dumps(data))
```

## Project Structure

```
energy-monitor-starter/
├── docker-compose.yml          # Main orchestration file
├── database/
│   └── init.sql               # Database schema initialization
├── mosquitto/
│   └── config/
│       └── mosquitto.conf     # MQTT broker configuration
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI application
│   ├── database.py           # Database operations
│   ├── mqtt_handler.py       # MQTT client and message processing
│   └── models.py             # Pydantic data models
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py               # Streamlit dashboard
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── simulator.py         # Test data generator
└── README.md
```

## Management Commands

### Start/Stop Services

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart backend

# View logs for specific service
docker-compose logs -f dashboard
```

### Database Operations

```bash
# Connect to PostgreSQL
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor

# Useful SQL queries:
SELECT * FROM current_power;  # Latest readings
SELECT COUNT(*) FROM sensor_data;  # Total data points
SELECT * FROM devices;  # All devices
```

### Troubleshooting

```bash
# Check container status
docker-compose ps

# View all logs
docker-compose logs

# Restart everything
docker-compose down
docker-compose up -d

# Clear all data and restart fresh
docker-compose down -v
docker-compose up -d
```

## Development

### Modifying the Backend

1. Edit files in `backend/`
2. The backend container has hot-reload enabled, so changes will apply automatically
3. If you change `requirements.txt`, rebuild:
   ```bash
   docker-compose up -d --build backend
   ```

### Modifying the Dashboard

1. Edit `dashboard/app.py`
2. Streamlit auto-reloads on file changes
3. For requirement changes:
   ```bash
   docker-compose up -d --build dashboard
   ```

### Adding New Devices

1. Insert into database:
   ```sql
   INSERT INTO devices (device_id, device_name, location, device_type, rated_power)
   VALUES ('DEVICE006', 'New Device', 'Location', 'Type', 5000.0);
   ```
2. Start publishing data to `energy/sensors/DEVICE006`

## Performance Tuning

### For Production Use

1. **Enable authentication** on MQTT broker
2. **Configure PostgreSQL** connection pooling
3. **Add reverse proxy** (nginx) for the dashboard
4. **Set up monitoring** with Prometheus + Grafana
5. **Implement data retention policies** in TimescaleDB
6. **Enable SSL/TLS** for all network communications

### Scaling

- Each service can be scaled independently
- For high data volumes, migrate to Kafka as the message bus
- Consider deploying to Kubernetes for true horizontal scaling

## Next Steps

This starter project provides the foundation. To build toward the full blueprint:

1. **Week 1-2**: Integrate real Zigbee/Z-Wave devices using Zigbee2MQTT
2. **Week 3-4**: Add Node-RED for visual automation flows
3. **Week 5-6**: Implement ML-based anomaly detection with Scikit-learn
4. **Week 7-8**: Add Grafana for operational dashboards
5. **Week 9-10**: Integrate time-of-use billing calculations
6. **Ongoing**: Add features incrementally based on your requirements

## Resources

- **TimescaleDB Docs**: https://docs.timescale.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **MQTT Protocol**: https://mqtt.org/
- **Streamlit Docs**: https://docs.streamlit.io/
- **Full Blueprint**: See the original document for the complete vision

## Support

For issues or questions:
1. Check logs: `docker-compose logs`
2. Verify all containers are running: `docker-compose ps`
3. Check database connectivity: `docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor`

## License

This starter project uses open-source components:
- FastAPI: MIT License
- TimescaleDB: Apache 2.0 (Community Edition)
- Eclipse Mosquitto: EPL/EDL
- Streamlit: Apache 2.0

Your modifications and extensions can use any compatible license.

## Credits

Built following the open-source Energy Consumption Monitor blueprint.
All components selected for production-readiness and zero licensing costs.
