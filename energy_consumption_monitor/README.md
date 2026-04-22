# Energy Consumption Monitor  v0.1

A Dockerized energy telemetry platform that ingests MQTT sensor readings, stores time-series data in TimescaleDB, exposes a FastAPI backend for analytics, and surfaces live consumption in a Streamlit dashboard — all in a local, container-friendly Python stack.




## Features

- **MQTT ingestion pipeline**: publishes and consumes live sensor telemetry over Eclipse Mosquitto
- **TimescaleDB storage**: stores timestamped readings as a hypertable for fast time-series queries
- **FastAPI backend**: serves health, device, history, stats, alerts, and cost endpoints
- **Streamlit dashboard**: live overview, per-device history charts, and cost analysis
- **Built-in simulator**: generates realistic power usage patterns for multiple device types
- **Alert support**: simple threshold-based alerts with resolution workflow
- **Docker Compose deployment**: one command starts the whole stack
- **Project scaffolding**: clear separation between database, backend, dashboard, and simulator

---

## Install

### 1. Clone or extract

```bash
git clone https://github.com/yourname/energy-monitor-starter.git
cd energy-monitor-starter
```

### 2. Start Docker if needed

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### 3. Build and run the stack

```bash
docker compose up --build
```

If your system uses the older Docker Compose binary, this also works:

```bash
docker-compose up --build
```

---

## Configure

The default compose file already wires the services together. The main environment values are:

```bash
DATABASE_URL=postgresql://energy_user:energy_pass@timescaledb:5432/energy_monitor
MQTT_BROKER=mosquitto
MQTT_PORT=1883
BACKEND_URL=http://backend:8000
```

You can adjust these in `docker-compose.yml` if you want different credentials, ports, or hostnames.

---

## Initialize the database

The database schema is loaded automatically from `database/init.sql` the first time the TimescaleDB container starts.

If you want to reset it manually, remove the volume and start again:

```bash
docker compose down -v
docker compose up --build
```

---

## Run

When the stack is up:

- **Dashboard**: `http://localhost:8501`
- **API docs**: `http://localhost:8000/docs`
- **API health**: `http://localhost:8000/health`

### Key endpoints

```bash
curl http://localhost:8000/health
curl http://localhost:8000/devices
curl http://localhost:8000/sensors/current
curl http://localhost:8000/analytics/total-consumption?hours=24
curl http://localhost:8000/analytics/cost-estimate?hours=24
```

### Dashboard views

- **Overview**: current total power, device distribution, and live readings
- **Device Details**: historical power, voltage, current, and power factor charts
- **Cost Analysis**: estimated daily, monthly, and yearly cost
- **Alerts**: placeholder panel for threshold and anomaly workflows

---

## Simulator

The simulator publishes synthetic readings to topics like:

```bash
energy/sensors/DEVICE001
energy/sensors/DEVICE002
energy/sensors/DEVICE003
```

It runs with a default interval of **5 seconds** and creates readings for HVAC, lighting, elevator, and water-heating loads.

---

## Project layout

```
energy-monitor-starter/
├─ docker-compose.yml
├─ start.sh
├─ stop.sh
├─ database/
│  └─ init.sql                  # TimescaleDB schema, views, and cost function
├─ mosquitto/
│  └─ config/
│     └─ mosquitto.conf         # MQTT broker config
├─ backend/
│  ├─ main.py                   # FastAPI app + endpoints
│  ├─ database.py               # Async DB access layer
│  ├─ mqtt_handler.py           # MQTT subscriber + alert creation
│  ├─ models.py                 # Pydantic request/response models
│  ├─ requirements.txt
│  └─ Dockerfile
├─ dashboard/
│  ├─ app.py                    # Streamlit dashboard
│  ├─ requirements.txt
│  └─ Dockerfile
├─ simulator/
│  ├─ simulator.py              # Telemetry generator
│  ├─ requirements.txt
│  └─ Dockerfile
├─ README.md
├─ QUICK_REFERENCE.md
├─ TROUBLESHOOTING.md
├─ ROADMAP.md
└─ CHANGELOG.md
```

---

## How to extract, install:

# ===== 1) Go to the folder where the zip is =====
cd /path/to/the/folder/that/contains/the/zip

# ===== 2) Extract it =====
unzip energy-monitor-starter.zip

# ===== 3) Enter the extracted project folder =====
cd energy-monitor-starter

# ===== 4) Start Docker if it is not running =====
sudo systemctl start docker

# ===== 5) Build and launch everything =====
docker compose up --build

# ===== 6) Open the apps =====
# Dashboard: http://localhost:8501
# API docs:  http://localhost:8000/docs

---

If `docker compose up --build` fails because of an old Docker Compose setup, use:

```bash
docker-compose up --build
```

A clean checklist version is:

```bash
cd /path/to/project
unzip energy-monitor-starter.zip
cd energy-monitor-starter
sudo systemctl start docker
docker compose up --build
```

---

## Roadmap (v0.2+)

- [ ] Robust startup checks for TimescaleDB and MQTT broker
- [ ] Authenticated API access and role-based permissions
- [ ] Configurable alert thresholds per device
- [ ] Better cost math based on actual sample intervals
- [ ] Per-device anomaly detection
- [ ] Retention and compression policies for historical data
- [ ] Export to CSV/Parquet
- [ ] Grafana or Prometheus observability
- [ ] Multi-site support
- [ ] WebSocket live updates for the dashboard
