# Testing & Validation Guide - v0.2

This guide walks you through testing every component of the Energy Monitor platform.

## Pre-Flight Checklist

Before testing, ensure:
- [ ] All services are running: `docker-compose ps`
- [ ] Setup completed: `./setup.sh` has been run
- [ ] .env file exists with generated passwords

## 1. System Health Check

Run the automated health checker:

```bash
python3 health_check.py
```

**Expected Output:**
```
✅ Status: HEALTHY
✅ Database: Connected
✅ MQTT: Connected
✅ Total devices: X
✅ Active readings: X
✅ Prometheus is running
✅ Grafana is running
```

**If checks fail:**
- Backend unreachable: `docker-compose logs backend`
- Database issues: `docker-compose logs timescaledb`
- MQTT issues: `docker-compose logs mosquitto`

## 2. MQTT Authentication Test

### Test 1: Anonymous Connection (Should Fail)

```bash
# Try to subscribe without credentials
mosquitto_sub -h localhost -p 1883 -t 'energy/#' -v
```

**Expected:** Connection refused or timeout (auth required)

### Test 2: Authenticated Connection (Should Succeed)

```bash
# Load password from .env
export MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

# Subscribe with credentials
mosquitto_sub -h localhost -p 1883 \
  -u energy_mqtt -P "$MQTT_PASSWORD" \
  -t 'energy/#' -v
```

**Expected:** Connection successful, waiting for messages

### Test 3: Publish Test Message

In another terminal:

```bash
export MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

mosquitto_pub -h localhost -p 1883 \
  -u energy_mqtt -P "$MQTT_PASSWORD" \
  -t 'energy/sensors/TEST001' \
  -m '{"device_id":"TEST001","power_watts":1500,"voltage":120,"current":12.5,"power_factor":0.95}'
```

**Expected:** Message appears in subscriber terminal

## 3. Data Ingestion Pipeline Test

### End-to-End Test

```bash
# Create test publisher script
cat > test_publish.sh << 'EOF'
#!/bin/bash
MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

for i in {1..5}; do
  mosquitto_pub -h localhost -p 1883 \
    -u energy_mqtt -P "$MQTT_PASSWORD" \
    -t "energy/sensors/TEST_DEVICE" \
    -m "{\"device_id\":\"TEST_DEVICE\",\"power_watts\":$((1000 + $i * 100)),\"voltage\":120,\"current\":$(($i + 10)),\"power_factor\":0.95,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
  echo "Published reading $i"
  sleep 2
done
EOF

chmod +x test_publish.sh
./test_publish.sh
```

### Verify in Database

```bash
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor -c \
  "SELECT time, device_id, power_watts FROM sensor_data WHERE device_id = 'TEST_DEVICE' ORDER BY time DESC LIMIT 5;"
```

**Expected:** 5 readings with increasing power values

### Verify in Dashboard

1. Open http://localhost:8501
2. Look for TEST_DEVICE in device list
3. Check Overview tab shows data
4. Select TEST_DEVICE in Device Details tab
5. Verify charts show the test data

## 4. API Testing

### Test Health Endpoint

```bash
curl http://localhost:8000/health | jq
```

**Expected:**
```json
{
  "status": "healthy",
  "database": true,
  "mqtt": true,
  "timestamp": "2024-04-21T..."
}
```

### Test Devices Endpoint

```bash
curl http://localhost:8000/devices | jq
```

**Expected:** Array of devices (at least TEST_DEVICE)

### Test Current Readings

```bash
curl http://localhost:8000/sensors/current | jq
```

**Expected:** Current power readings for all devices

### Test Device History

```bash
curl "http://localhost:8000/sensors/TEST_DEVICE/history?hours=1&limit=10" | jq
```

**Expected:** Last 10 readings for TEST_DEVICE

### Test Cost Calculation

```bash
curl "http://localhost:8000/analytics/cost-estimate?hours=1" | jq
```

**Expected:**
```json
{
  "device_id": "all",
  "period_hours": 1,
  "estimated_cost_usd": 0.XX,
  "timestamp": "..."
}
```

## 5. Authentication Testing (if enabled)

### Enable Authentication

```bash
# Edit .env
sed -i 's/AUTH_ENABLED=false/AUTH_ENABLED=true/' .env

# Restart backend
docker-compose restart backend
sleep 5
```

### Test Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret" | jq
```

**Expected:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_in": 3600,
  "scopes": ["read", "write", "admin"]
}
```

### Test Protected Endpoint

```bash
# Without token (should fail)
curl http://localhost:8000/devices

# With token (should succeed)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret" | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/devices | jq
```

## 6. Machine Learning Testing

### Check ML Status

```bash
# View ML-related logs
docker-compose logs backend | grep -i "model\|ML"
```

**Expected output:**
```
ML anomaly detector initialized
```

### Generate Training Data

ML models need 1000+ samples per device. Generate test data:

```bash
cat > generate_ml_data.sh << 'EOF'
#!/bin/bash
MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

echo "Generating 1200 samples for ML training..."
for i in {1..1200}; do
  # Normal pattern: oscillate between 1000-1500W
  POWER=$((1000 + ($i % 500)))
  
  # Add some anomalies (10% of samples)
  if [ $((i % 10)) -eq 0 ]; then
    POWER=3000  # Spike
  fi
  
  mosquitto_pub -h localhost -p 1883 \
    -u energy_mqtt -P "$MQTT_PASSWORD" \
    -t "energy/sensors/ML_TEST" \
    -m "{\"device_id\":\"ML_TEST\",\"power_watts\":$POWER,\"voltage\":120,\"current\":$(echo "scale=2; $POWER/120" | bc),\"power_factor\":0.95}"
  
  if [ $((i % 100)) -eq 0 ]; then
    echo "Progress: $i/1200"
  fi
  
  sleep 0.1
done

echo "Data generation complete!"
EOF

chmod +x generate_ml_data.sh
./generate_ml_data.sh
```

### Trigger Manual Model Training

```bash
# Force model training
docker exec -it energy-backend python3 << EOF
import asyncio
from ml_anomaly import AnomalyDetector
from database import DatabaseManager

async def train():
    db = DatabaseManager()
    await db.connect()
    detector = AnomalyDetector(db)
    await detector._train_model("ML_TEST")
    await db.disconnect()

asyncio.run(train())
EOF
```

### Verify Model Created

```bash
# Check if model file exists
docker exec -it energy-backend ls -lh /app/models/
```

**Expected:** `ML_TEST_model.joblib` and `ML_TEST_scaler.joblib`

### Send Anomalous Data

```bash
MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

# Send normal reading
mosquitto_pub -h localhost -p 1883 \
  -u energy_mqtt -P "$MQTT_PASSWORD" \
  -t "energy/sensors/ML_TEST" \
  -m '{"device_id":"ML_TEST","power_watts":1200,"voltage":120,"current":10,"power_factor":0.95}'

sleep 2

# Send anomalous reading (way out of normal pattern)
mosquitto_pub -h localhost -p 1883 \
  -u energy_mqtt -P "$MQTT_PASSWORD" \
  -t "energy/sensors/ML_TEST" \
  -m '{"device_id":"ML_TEST","power_watts":5000,"voltage":120,"current":42,"power_factor":0.95}'
```

### Check for ML Alert

```bash
curl "http://localhost:8000/alerts?resolved=false" | jq '.[] | select(.alert_type == "ml_anomaly")'
```

**Expected:** Alert for ML_TEST with anomaly score

## 7. Prometheus Metrics Testing

### Check Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

**Expected:** Prometheus-formatted metrics output

### Query Specific Metrics

```bash
# MQTT message count
curl -s http://localhost:8000/metrics | grep energy_monitor_mqtt_messages_received_total

# Database inserts
curl -s http://localhost:8000/metrics | grep energy_monitor_database_inserts_total

# Active devices
curl -s http://localhost:8000/metrics | grep energy_monitor_active_devices
```

### Test Prometheus UI

1. Open http://localhost:9090
2. In expression box: `energy_monitor_mqtt_messages_received_total`
3. Click "Execute"
4. Switch to "Graph" tab

**Expected:** Graph showing message count over time

## 8. Grafana Testing

### Login to Grafana

1. Open http://localhost:3000
2. Username: `admin`
3. Password: From .env file (`grep GRAFANA_PASSWORD .env`)

### Verify Data Sources

1. Navigate to Configuration → Data Sources
2. Verify "Prometheus" is listed and working
3. Verify "TimescaleDB" is listed
4. Click "Test" on each

**Expected:** Both show green "Data source is working"

### Load System Dashboard

1. Navigate to Dashboards
2. Import dashboard JSON from `grafana/dashboards/system-overview.json`
3. View dashboard

**Expected:** Panels show live data

### Create Custom Query

1. Create new panel
2. Select TimescaleDB data source
3. Query:
```sql
SELECT 
  time AS "time",
  device_id,
  power_watts
FROM sensor_data
WHERE $__timeFilter(time)
  AND device_id = 'TEST_DEVICE'
ORDER BY time
```

**Expected:** Time series graph of TEST_DEVICE power

## 9. Data Retention & Compression Testing

### Check Compression Status

```bash
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor << EOF
-- View compression statistics
SELECT * FROM timescaledb_information.compression_settings;

-- View chunks
SELECT * FROM timescaledb_information.chunks 
WHERE hypertable_name = 'sensor_data' 
LIMIT 5;
EOF
```

### Verify Retention Policy

```bash
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor << EOF
-- View retention policies
SELECT * FROM timescaledb_information.jobs 
WHERE proc_name LIKE '%retention%';
EOF
```

**Expected:** Policy to drop data older than 90 days

## 10. Load Testing

### Generate High-Volume Data

```bash
cat > load_test.sh << 'EOF'
#!/bin/bash
MQTT_PASSWORD=$(grep MQTT_PASSWORD .env | cut -d= -f2)

echo "Starting load test: 1000 messages in 10 seconds"
start_time=$(date +%s)

for i in {1..1000}; do
  mosquitto_pub -h localhost -p 1883 \
    -u energy_mqtt -P "$MQTT_PASSWORD" \
    -t "energy/sensors/LOAD_TEST_$((i % 10))" \
    -m "{\"device_id\":\"LOAD_TEST_$((i % 10))\",\"power_watts\":$((RANDOM % 2000 + 1000)),\"voltage\":120,\"current\":10,\"power_factor\":0.95}" &
  
  if [ $((i % 100)) -eq 0 ]; then
    wait
    echo "Sent $i messages"
  fi
done

wait
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Complete! Sent 1000 messages in ${duration} seconds"
echo "Rate: $((1000 / duration)) msg/sec"
EOF

chmod +x load_test.sh
./load_test.sh
```

### Monitor Performance

```bash
# Check Docker stats
docker stats --no-stream

# Check metrics
curl -s http://localhost:8000/metrics | grep mqtt_messages_received_total

# Check database
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor -c \
  "SELECT COUNT(*) FROM sensor_data WHERE device_id LIKE 'LOAD_TEST%';"
```

## 11. Integration Examples Testing

### Test Shelly Integration (if you have Shelly devices)

```bash
cd examples

# Install requirements
pip3 install -r requirements.txt

# Discover Shelly devices
python3 shelly_integration.py --discover --network 192.168.1

# Monitor specific device
# (Edit shelly_integration.py to add your device IPs first)
python3 shelly_integration.py --interval 10
```

### Test Modbus Integration (if you have Modbus meters)

```bash
cd examples

# Example: Carlo Gavazzi EM340 via TCP
python3 modbus_integration.py \
  --type em340 \
  --mode tcp \
  --ip 192.168.1.50 \
  --device-id MODBUS_MAIN \
  --interval 10

# Example: Via RS485 serial
python3 modbus_integration.py \
  --type em340 \
  --mode rtu \
  --serial-port /dev/ttyUSB0 \
  --baudrate 9600 \
  --device-id MODBUS_PANEL_A \
  --interval 10
```

## 12. Clean Up Test Data

After testing, remove test devices:

```bash
docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor << EOF
-- Remove test data
DELETE FROM sensor_data WHERE device_id LIKE 'TEST%' OR device_id LIKE 'ML_TEST' OR device_id LIKE 'LOAD_TEST%';

-- Remove test devices
DELETE FROM devices WHERE device_id LIKE 'TEST%' OR device_id LIKE 'ML_TEST' OR device_id LIKE 'LOAD_TEST%';

-- Vacuum to reclaim space
VACUUM ANALYZE sensor_data;
EOF
```

## Success Criteria

Platform is ready for production use when:

- [ ] All health checks pass
- [ ] MQTT authentication works
- [ ] Data flows from MQTT → Database → Dashboard
- [ ] API returns correct data
- [ ] Energy calculations are accurate (test with known load)
- [ ] ML models train successfully (with sufficient data)
- [ ] Prometheus collects metrics
- [ ] Grafana displays data
- [ ] Alerts trigger correctly
- [ ] At least one real device is integrated and working

## Troubleshooting Common Test Failures

### "Connection refused" on MQTT
- Check mosquitto is running: `docker-compose ps mosquitto`
- Verify password: `cat .env | grep MQTT_PASSWORD`
- Check logs: `docker-compose logs mosquitto`

### Data not appearing in database
- Check backend logs: `docker-compose logs backend | grep ERROR`
- Verify MQTT subscription: `docker-compose logs backend | grep "Received message"`
- Check database connection: `docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor -c "SELECT 1;"`

### ML models not training
- Verify data count: Must have 1000+ samples
- Check logs: `docker-compose logs backend | grep -i model`
- Verify /app/models directory exists: `docker exec -it energy-backend ls -lh /app/models/`

### Grafana shows "No Data"
- Verify datasource connection
- Check query syntax
- Ensure time range includes data
- Verify database has data: `docker exec -it energy-timescaledb psql -U energy_user -d energy_monitor -c "SELECT COUNT(*) FROM sensor_data;"`

---

**After all tests pass, your Energy Monitor v0.2 platform is production-ready!**
