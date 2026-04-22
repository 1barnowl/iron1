"""
MQTT Handler - Subscribes to sensor topics and processes incoming data
"""

import paho.mqtt.client as mqtt
import json
import logging
import os
import asyncio
import time
from datetime import datetime
from typing import Optional
from threading import Thread

from metrics import (
    mqtt_messages_received_total,
    mqtt_messages_processed_total,
    mqtt_messages_failed_total,
    database_inserts_total,
    database_insert_errors_total,
    alerts_created_total,
    ml_anomalies_detected_total
)

logger = logging.getLogger(__name__)


class MQTTHandler:
    def __init__(self, db_manager, anomaly_detector=None):
        self.db_manager = db_manager
        self.anomaly_detector = anomaly_detector
        self.broker = os.getenv("MQTT_BROKER", "mosquitto")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME")
        self.password = os.getenv("MQTT_PASSWORD")
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.loop = None
        self.thread = None
        
        # MQTT topics
        self.sensor_topic = "energy/sensors/+"
        self.device_topic = "energy/devices/+"
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.connected = True
            
            # Subscribe to topics
            client.subscribe(self.sensor_topic)
            client.subscribe(self.device_topic)
            logger.info(f"Subscribed to topics: {self.sensor_topic}, {self.device_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker, return code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Track message received
            mqtt_messages_received_total.labels(topic=topic).inc()
            
            logger.debug(f"Received message on topic {topic}: {payload}")
            
            # Parse JSON payload
            data = json.loads(payload)
            
            # Process based on topic
            if topic.startswith("energy/sensors/"):
                self._process_sensor_data(data)
                mqtt_messages_processed_total.inc()
            elif topic.startswith("energy/devices/"):
                self._process_device_event(data)
                mqtt_messages_processed_total.inc()
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            mqtt_messages_failed_total.labels(error_type="json_decode").inc()
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            mqtt_messages_failed_total.labels(error_type="processing").inc()
    
    def _process_sensor_data(self, data: dict):
        """Process incoming sensor data"""
        try:
            # Handle both 'time' and 'timestamp' fields from different sources
            if "time" in data:
                timestamp = data["time"]
            elif "timestamp" in data:
                timestamp = data["timestamp"]
            else:
                timestamp = datetime.utcnow()
            
            # Parse timestamp if it's a string
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    timestamp = datetime.utcnow()
            
            data["time"] = timestamp
            
            # Schedule database insert in the event loop
            if self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.db_manager.insert_sensor_data(data),
                    self.loop
                )
                # Track future to catch errors
                future.add_done_callback(self._handle_insert_result)
            
            # Check for anomalies using threshold-based detection
            self._check_threshold_anomalies(data)
            
            # Check for anomalies using ML if detector is available
            if self.anomaly_detector and self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._check_ml_anomalies(data),
                    self.loop
                )
                future.add_done_callback(lambda f: None)  # Ignore result
        
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
            mqtt_messages_failed_total.labels(error_type="sensor_processing").inc()
    
    def _handle_insert_result(self, future):
        """Handle result of async database insert"""
        try:
            future.result()  # This will raise if insert failed
            database_inserts_total.inc()
        except Exception as e:
            logger.error(f"Database insert failed: {e}")
            database_insert_errors_total.inc()
    
    async def _check_ml_anomalies(self, data: dict):
        """Check for ML-detected anomalies"""
        try:
            device_id = data.get("device_id")
            if not device_id:
                return
            
            alert = await self.anomaly_detector.detect_anomaly(device_id, data)
            
            if alert:
                await self.db_manager.create_alert(alert)
                ml_anomalies_detected_total.labels(device_id=device_id).inc()
                alerts_created_total.labels(
                    alert_type=alert["alert_type"],
                    severity=alert["severity"]
                ).inc()
                logger.warning(f"ML anomaly detected: {alert['message']}")
        
        except Exception as e:
            logger.error(f"Error in ML anomaly detection: {e}")
    
    def _process_device_event(self, data: dict):
        """Process device events (status changes, etc.)"""
        try:
            event_type = data.get("event_type")
            device_id = data.get("device_id")
            
            logger.info(f"Device event: {event_type} for {device_id}")
            
            # Handle different event types
            if event_type == "online":
                logger.info(f"Device {device_id} came online")
            elif event_type == "offline":
                logger.info(f"Device {device_id} went offline")
                # Could create an alert here
        
        except Exception as e:
            logger.error(f"Error processing device event: {e}")
    
    def _check_threshold_anomalies(self, data: dict):
        """Anomaly detection using device-specific thresholds from database"""
        try:
            device_id = data.get("device_id")
            power_watts = data.get("power_watts")
            voltage = data.get("voltage")
            
            if not device_id:
                return
            
            # Get device thresholds from database
            if self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._get_device_thresholds(device_id),
                    self.loop
                )
                
                try:
                    thresholds = future.result(timeout=1.0)
                except Exception as e:
                    logger.warning(f"Could not fetch thresholds for {device_id}: {e}")
                    return
                
                if not thresholds or not thresholds.get("alert_enabled"):
                    return
                
                # Check power thresholds
                if power_watts is not None:
                    high_threshold = thresholds.get("power_threshold_high")
                    low_threshold = thresholds.get("power_threshold_low")
                    
                    if high_threshold and power_watts > high_threshold:
                        self._create_alert(
                            device_id=device_id,
                            alert_type="high_power",
                            severity="warning",
                            message=f"Power consumption {power_watts:.2f}W exceeds threshold {high_threshold:.2f}W",
                            threshold_value=high_threshold,
                            actual_value=power_watts
                        )
                    elif low_threshold and power_watts < low_threshold and power_watts > 0:
                        self._create_alert(
                            device_id=device_id,
                            alert_type="low_power",
                            severity="info",
                            message=f"Unusually low power consumption: {power_watts:.2f}W",
                            threshold_value=low_threshold,
                            actual_value=power_watts
                        )
                
                # Check voltage thresholds
                if voltage is not None:
                    high_threshold = thresholds.get("voltage_threshold_high")
                    low_threshold = thresholds.get("voltage_threshold_low")
                    
                    if high_threshold and voltage > high_threshold:
                        self._create_alert(
                            device_id=device_id,
                            alert_type="high_voltage",
                            severity="critical",
                            message=f"Dangerous voltage level: {voltage:.2f}V",
                            threshold_value=high_threshold,
                            actual_value=voltage
                        )
                    elif low_threshold and voltage < low_threshold:
                        self._create_alert(
                            device_id=device_id,
                            alert_type="low_voltage",
                            severity="warning",
                            message=f"Low voltage detected: {voltage:.2f}V",
                            threshold_value=low_threshold,
                            actual_value=voltage
                        )
        
        except Exception as e:
            logger.error(f"Error checking threshold anomalies: {e}")
    
    async def _get_device_thresholds(self, device_id: str) -> dict:
        """Fetch device threshold configuration from database"""
        async with self.db_manager.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT alert_enabled, power_threshold_high, power_threshold_low,
                       voltage_threshold_high, voltage_threshold_low
                FROM devices
                WHERE device_id = $1
                """,
                device_id
            )
            return dict(row) if row else {}
    
    def _create_alert(self, **alert_data):
        """Create alert in database and track metrics"""
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.db_manager.create_alert(alert_data),
                self.loop
            )
            
            # Track metrics
            alerts_created_total.labels(
                alert_type=alert_data.get("alert_type", "unknown"),
                severity=alert_data.get("severity", "unknown")
            ).inc()
    
    def _run_event_loop(self):
        """Run asyncio event loop in separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def start(self):
        """Start MQTT client with retry logic"""
        max_retries = 10
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Start event loop in separate thread
                if not self.thread or not self.thread.is_alive():
                    self.thread = Thread(target=self._run_event_loop, daemon=True)
                    self.thread.start()
                    time.sleep(0.5)  # Give thread time to start
                
                # Create MQTT client
                self.client = mqtt.Client()
                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect
                self.client.on_message = self._on_message
                
                # Set username and password if provided
                if self.username and self.password:
                    self.client.username_pw_set(self.username, self.password)
                    logger.info(f"MQTT authentication enabled for user: {self.username}")
                
                # Connect to broker
                logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port} (attempt {attempt + 1}/{max_retries})")
                self.client.connect(self.broker, self.port, 60)
                
                # Start network loop in separate thread
                self.client.loop_start()
                
                # Wait for connection with timeout
                timeout = 10
                while not self.connected and timeout > 0:
                    time.sleep(0.5)
                    timeout -= 0.5
                
                if self.connected:
                    logger.info("MQTT handler started successfully")
                    return
                else:
                    raise Exception("Connection timeout")
            
            except Exception as e:
                logger.error(f"Error starting MQTT handler (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
                else:
                    logger.error("Failed to connect to MQTT broker after all retries")
                    raise
    
    def stop(self):
        """Stop MQTT client"""
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
            
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
            
            logger.info("MQTT handler stopped")
        
        except Exception as e:
            logger.error(f"Error stopping MQTT handler: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker"""
        return self.connected
    
    def publish(self, topic: str, payload: dict):
        """Publish message to MQTT topic"""
        try:
            if self.client and self.connected:
                message = json.dumps(payload)
                self.client.publish(topic, message)
                logger.debug(f"Published to {topic}: {message}")
            else:
                logger.warning("Cannot publish - not connected to MQTT broker")
        
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
