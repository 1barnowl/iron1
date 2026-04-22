-- Initialize TimescaleDB extension and create schema for energy monitoring

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create sensor_data table for real-time power measurements
CREATE TABLE sensor_data (
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    location VARCHAR(100),
    power_watts DOUBLE PRECISION,
    voltage DOUBLE PRECISION,
    current DOUBLE PRECISION,
    power_factor DOUBLE PRECISION,
    frequency DOUBLE PRECISION,
    metadata JSONB
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('sensor_data', 'time');

-- Create indexes for common queries
CREATE INDEX idx_device_id ON sensor_data (device_id, time DESC);
CREATE INDEX idx_location ON sensor_data (location, time DESC);

-- Create continuous aggregate for hourly rollups
CREATE MATERIALIZED VIEW sensor_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    location,
    AVG(power_watts) AS avg_power,
    MAX(power_watts) AS max_power,
    MIN(power_watts) AS min_power,
    AVG(voltage) AS avg_voltage,
    AVG(current) AS avg_current,
    AVG(power_factor) AS avg_power_factor,
    COUNT(*) AS sample_count
FROM sensor_data
GROUP BY bucket, device_id, location;

-- Add refresh policy for continuous aggregate (refresh every 30 minutes)
SELECT add_continuous_aggregate_policy('sensor_data_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '30 minutes',
    schedule_interval => INTERVAL '30 minutes');

-- Create daily rollup view
CREATE MATERIALIZED VIEW sensor_data_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    device_id,
    location,
    AVG(power_watts) AS avg_power,
    MAX(power_watts) AS max_power,
    MIN(power_watts) AS min_power,
    SUM(power_watts) / 1000.0 AS total_kwh_approx,
    COUNT(*) AS sample_count
FROM sensor_data
GROUP BY bucket, device_id, location;

-- Add refresh policy for daily aggregate
SELECT add_continuous_aggregate_policy('sensor_data_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- Create devices table for device metadata
CREATE TABLE devices (
    device_id VARCHAR(50) PRIMARY KEY,
    device_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    device_type VARCHAR(50),
    rated_power DOUBLE PRECISION,
    installation_date TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Alert thresholds (configurable per device)
    power_threshold_high DOUBLE PRECISION DEFAULT 20000.0,
    power_threshold_low DOUBLE PRECISION DEFAULT 0.0,
    voltage_threshold_high DOUBLE PRECISION DEFAULT 130.0,
    voltage_threshold_low DOUBLE PRECISION DEFAULT 110.0,
    alert_enabled BOOLEAN DEFAULT TRUE
);

-- Create device_rates table for time-of-use billing
CREATE TABLE device_rates (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) REFERENCES devices(device_id),
    rate_name VARCHAR(100),
    rate_per_kwh DOUBLE PRECISION NOT NULL,
    start_hour INT CHECK (start_hour >= 0 AND start_hour < 24),
    end_hour INT CHECK (end_hour >= 0 AND end_hour < 24),
    days_of_week INT[] DEFAULT ARRAY[0,1,2,3,4,5,6], -- 0=Sunday
    effective_start DATE,
    effective_end DATE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create index on device rates
CREATE INDEX idx_device_rates_device ON device_rates(device_id, is_active);

-- Create alerts table for anomaly detection
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) REFERENCES devices(device_id),
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    threshold_value DOUBLE PRECISION,
    actual_value DOUBLE PRECISION,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_alerts_time ON alerts (time DESC);
CREATE INDEX idx_alerts_device ON alerts (device_id, time DESC);

-- Insert sample devices for testing
INSERT INTO devices (device_id, device_name, location, device_type, rated_power) VALUES
    ('DEVICE001', 'Main HVAC Unit', 'Building A - Roof', 'HVAC', 15000.0),
    ('DEVICE002', 'Lighting Circuit 1', 'Building A - Floor 1', 'Lighting', 2400.0),
    ('DEVICE003', 'Server Room AC', 'Building A - Basement', 'HVAC', 5000.0),
    ('DEVICE004', 'Elevator Motor', 'Building A - Shaft 1', 'Elevator', 12000.0),
    ('DEVICE005', 'Water Heater', 'Building A - Mechanical', 'Water Heating', 4500.0);

-- Create function for cost calculation using trapezoidal integration
-- This correctly handles variable sample intervals
CREATE OR REPLACE FUNCTION calculate_cost(
    p_device_id VARCHAR,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    total_kwh DOUBLE PRECISION;
    total_cost DOUBLE PRECISION;
    rate_per_kwh DOUBLE PRECISION := 0.12;
BEGIN
    -- Calculate energy using trapezoidal integration
    -- Energy = integral of power over time
    -- For discrete samples: sum of ((P1 + P2)/2 * dt) where dt is in hours
    WITH time_series AS (
        SELECT 
            time,
            power_watts,
            LEAD(time) OVER (ORDER BY time) as next_time,
            LEAD(power_watts) OVER (ORDER BY time) as next_power
        FROM sensor_data
        WHERE device_id = p_device_id
          AND time BETWEEN p_start_time AND p_end_time
        ORDER BY time
    ),
    energy_intervals AS (
        SELECT
            -- Average power over interval
            (power_watts + COALESCE(next_power, power_watts)) / 2.0 / 1000.0 as avg_kw,
            -- Time difference in hours
            EXTRACT(EPOCH FROM (next_time - time)) / 3600.0 as hours
        FROM time_series
        WHERE next_time IS NOT NULL
    )
    SELECT SUM(avg_kw * hours) INTO total_kwh
    FROM energy_intervals;
    
    -- Apply rate
    total_cost := COALESCE(total_kwh, 0.0) * rate_per_kwh;
    
    RETURN total_cost;
END;
$$ LANGUAGE plpgsql;

-- Create view for real-time power consumption
CREATE VIEW current_power AS
SELECT DISTINCT ON (device_id)
    device_id,
    location,
    power_watts,
    voltage,
    current,
    time
FROM sensor_data
ORDER BY device_id, time DESC;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO energy_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO energy_user;

-- Add compression policy for sensor_data (compress data older than 7 days)
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('sensor_data', INTERVAL '7 days');

-- Add retention policy (drop data older than 90 days)
SELECT add_retention_policy('sensor_data', INTERVAL '90 days');

-- Create function to refresh materialized views manually if needed
CREATE OR REPLACE FUNCTION refresh_continuous_aggregates()
RETURNS VOID AS $$
BEGIN
    CALL refresh_continuous_aggregate('sensor_data_hourly', NULL, NULL);
    CALL refresh_continuous_aggregate('sensor_data_daily', NULL, NULL);
END;
$$ LANGUAGE plpgsql;
