"""
ML-Based Anomaly Detection Engine
Uses Isolation Forest trained on historical data for each device
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects anomalies in power consumption using Isolation Forest
    Models are trained per-device on historical data
    """
    
    def __init__(self, db_manager, model_dir="/app/models"):
        self.db_manager = db_manager
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Device models cache: {device_id: (model, scaler, last_trained)}
        self.models: Dict[str, Tuple[IsolationForest, StandardScaler, datetime]] = {}
        
        # Model parameters
        self.contamination = 0.05  # Expected percentage of anomalies
        self.n_estimators = 100
        self.random_state = 42
        
        # Training parameters
        self.min_samples_for_training = 1000  # Minimum data points needed
        self.retrain_interval_hours = 24  # Retrain every 24 hours
    
    async def detect_anomaly(self, device_id: str, sensor_data: dict) -> Optional[dict]:
        """
        Detect if current sensor reading is anomalous
        Returns alert dict if anomaly detected, None otherwise
        """
        try:
            # Get or train model for device
            model, scaler = await self._get_model(device_id)
            
            if model is None:
                logger.debug(f"No model available for {device_id} yet")
                return None
            
            # Extract features from sensor data
            features = self._extract_features(sensor_data)
            if features is None:
                return None
            
            # Scale features
            features_scaled = scaler.transform([features])
            
            # Predict (-1 = anomaly, 1 = normal)
            prediction = model.predict(features_scaled)[0]
            
            # Get anomaly score (more negative = more anomalous)
            score = model.score_samples(features_scaled)[0]
            
            if prediction == -1:
                # Anomaly detected
                return {
                    "device_id": device_id,
                    "alert_type": "ml_anomaly",
                    "severity": "warning" if score > -0.5 else "critical",
                    "message": f"Unusual power pattern detected (anomaly score: {score:.3f})",
                    "threshold_value": 0.0,  # No fixed threshold
                    "actual_value": sensor_data.get("power_watts"),
                    "metadata": {
                        "anomaly_score": float(score),
                        "detection_method": "isolation_forest",
                        "features": {
                            "power": sensor_data.get("power_watts"),
                            "voltage": sensor_data.get("voltage"),
                            "current": sensor_data.get("current"),
                            "power_factor": sensor_data.get("power_factor")
                        }
                    }
                }
            
            return None
        
        except Exception as e:
            logger.error(f"Error detecting anomaly for {device_id}: {e}")
            return None
    
    async def _get_model(self, device_id: str) -> Tuple[Optional[IsolationForest], Optional[StandardScaler]]:
        """Get model for device, training if necessary"""
        
        # Check if we have a cached model
        if device_id in self.models:
            model, scaler, last_trained = self.models[device_id]
            
            # Check if model needs retraining
            age_hours = (datetime.utcnow() - last_trained).total_seconds() / 3600
            if age_hours < self.retrain_interval_hours:
                return model, scaler
            
            logger.info(f"Model for {device_id} is {age_hours:.1f} hours old, retraining...")
        
        # Try to load from disk
        model_path = self.model_dir / f"{device_id}_model.joblib"
        scaler_path = self.model_dir / f"{device_id}_scaler.joblib"
        
        if model_path.exists() and scaler_path.exists():
            try:
                model = joblib.load(model_path)
                scaler = joblib.load(scaler_path)
                self.models[device_id] = (model, scaler, datetime.utcnow())
                logger.info(f"Loaded model for {device_id} from disk")
                return model, scaler
            except Exception as e:
                logger.warning(f"Failed to load model from disk: {e}")
        
        # Train new model
        model, scaler = await self._train_model(device_id)
        
        if model is not None:
            # Save to disk and cache
            try:
                joblib.dump(model, model_path)
                joblib.dump(scaler, scaler_path)
                self.models[device_id] = (model, scaler, datetime.utcnow())
                logger.info(f"Trained and saved new model for {device_id}")
            except Exception as e:
                logger.error(f"Failed to save model: {e}")
        
        return model, scaler
    
    async def _train_model(self, device_id: str) -> Tuple[Optional[IsolationForest], Optional[StandardScaler]]:
        """Train Isolation Forest model on historical data"""
        try:
            # Get historical data (last 30 days)
            start_time = datetime.utcnow() - timedelta(days=30)
            
            async with self.db_manager.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT power_watts, voltage, current, power_factor
                    FROM sensor_data
                    WHERE device_id = $1
                      AND time >= $2
                      AND power_watts IS NOT NULL
                      AND voltage IS NOT NULL
                      AND current IS NOT NULL
                      AND power_factor IS NOT NULL
                    ORDER BY time DESC
                    LIMIT 10000
                    """,
                    device_id,
                    start_time
                )
            
            if len(rows) < self.min_samples_for_training:
                logger.warning(
                    f"Insufficient data for {device_id}: {len(rows)} samples "
                    f"(need {self.min_samples_for_training})"
                )
                return None, None
            
            # Extract features
            features = []
            for row in rows:
                feature_vec = [
                    row["power_watts"],
                    row["voltage"],
                    row["current"],
                    row["power_factor"]
                ]
                features.append(feature_vec)
            
            X = np.array(features)
            
            # Standardize features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train Isolation Forest
            model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=self.random_state,
                n_jobs=-1  # Use all CPU cores
            )
            model.fit(X_scaled)
            
            logger.info(f"Trained model for {device_id} on {len(rows)} samples")
            return model, scaler
        
        except Exception as e:
            logger.error(f"Error training model for {device_id}: {e}")
            return None, None
    
    def _extract_features(self, sensor_data: dict) -> Optional[list]:
        """Extract feature vector from sensor reading"""
        try:
            features = [
                sensor_data.get("power_watts"),
                sensor_data.get("voltage"),
                sensor_data.get("current"),
                sensor_data.get("power_factor")
            ]
            
            # Check all features are present
            if any(f is None for f in features):
                return None
            
            return features
        
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    async def train_all_models(self):
        """Train models for all devices (run periodically)"""
        try:
            # Get all device IDs
            async with self.db_manager.pool.acquire() as conn:
                rows = await conn.fetch("SELECT device_id FROM devices")
            
            device_ids = [row["device_id"] for row in rows]
            logger.info(f"Training models for {len(device_ids)} devices...")
            
            for device_id in device_ids:
                await self._train_model(device_id)
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(1)
            
            logger.info("Model training complete")
        
        except Exception as e:
            logger.error(f"Error in batch model training: {e}")
