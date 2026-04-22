# Energy Monitor Environment Configuration
# Copy this file to .env and update with your actual values

# Database Configuration
DB_PASSWORD=change_me_in_production

# MQTT Broker Authentication
MQTT_USER=energy_mqtt
MQTT_PASSWORD=change_me_in_production

# JWT Secret for API Authentication
# Generate with: openssl rand -hex 32
JWT_SECRET=change_me_in_production_use_openssl_rand_hex_32

# API Authentication (set to 'true' to require JWT tokens)
AUTH_ENABLED=false

# Grafana Admin Password
GRAFANA_PASSWORD=admin

# CORS Origins (comma-separated)
ALLOWED_ORIGINS=*

# Logging Level
LOG_LEVEL=INFO
