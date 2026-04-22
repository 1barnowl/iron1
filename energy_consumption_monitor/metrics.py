"""
Energy Monitor Backend - FastAPI Application
Handles MQTT data ingestion, REST API, and database operations
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import os

from database import DatabaseManager
from mqtt_handler import MQTTHandler
from ml_anomaly import AnomalyDetector
from models import (
    SensorDataResponse,
    DeviceResponse,
    AlertResponse,
    PowerStatsResponse,
    HealthResponse
)
from auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    require_scope,
    User,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_ENABLED
)
from metrics import (
    metrics_response,
    MetricsMiddleware,
    database_connected,
    mqtt_connected,
    active_devices
)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
db_manager: Optional[DatabaseManager] = None
mqtt_handler: Optional[MQTTHandler] = None
anomaly_detector: Optional[AnomalyDetector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global db_manager, mqtt_handler, anomaly_detector
    
    logger.info("Starting Energy Monitor Backend...")
    
    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.connect()
    database_connected.set(1)
    
    # Initialize ML anomaly detector
    anomaly_detector = AnomalyDetector(db_manager)
    logger.info("ML anomaly detector initialized")
    
    # Initialize and start MQTT handler (with ML integration)
    mqtt_handler = MQTTHandler(db_manager, anomaly_detector)
    mqtt_handler.start()
    mqtt_connected.set(1 if mqtt_handler.is_connected() else 0)
    
    # Start background task for periodic model retraining
    async def periodic_model_training():
        """Retrain ML models every 24 hours"""
        while True:
            try:
                await asyncio.sleep(86400)  # 24 hours
                logger.info("Starting periodic model retraining...")
                await anomaly_detector.train_all_models()
            except Exception as e:
                logger.error(f"Error in periodic model training: {e}")
    
    # Start background task for metrics updates
    async def periodic_metrics_update():
        """Update Prometheus metrics every 30 seconds"""
        while True:
            try:
                await asyncio.sleep(30)
                
                # Update device count
                devices = await db_manager.get_all_devices()
                active_devices.set(len(devices))
                
                # Update connection status
                database_connected.set(1 if await db_manager.check_health() else 0)
                mqtt_connected.set(1 if mqtt_handler.is_connected() else 0)
                
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
    
    # Start background tasks
    model_training_task = asyncio.create_task(periodic_model_training())
    metrics_task = asyncio.create_task(periodic_metrics_update())
    
    logger.info("Backend started successfully")
    logger.info(f"Authentication: {'ENABLED' if AUTH_ENABLED else 'DISABLED'}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down backend...")
    model_training_task.cancel()
    metrics_task.cancel()
    
    if mqtt_handler:
        mqtt_handler.stop()
        mqtt_connected.set(0)
    if db_manager:
        await db_manager.disconnect()
        database_connected.set(0)
    
    logger.info("Backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Energy Consumption Monitor API",
    description="Real-time energy monitoring and analytics platform",
    version="0.2.0",
    lifespan=lifespan
)

# Add metrics middleware FIRST (to capture all requests)
app.add_middleware(MetricsMiddleware)

# Configure CORS - restrict in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_healthy = db_manager and await db_manager.check_health()
    mqtt_healthy = mqtt_handler and mqtt_handler.is_connected()
    
    return HealthResponse(
        status="healthy" if db_healthy and mqtt_healthy else "unhealthy",
        database=db_healthy,
        mqtt=mqtt_healthy,
        timestamp=datetime.utcnow()
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return metrics_response()


@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint - returns JWT access token
    Use this token in Authorization header: Bearer <token>
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "scopes": user.scopes
    }


@app.get("/auth/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


@app.get("/devices", response_model=List[DeviceResponse])
async def get_devices():
    """Get all registered devices"""
    try:
        devices = await db_manager.get_all_devices()
        return devices
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    """Get specific device details"""
    try:
        device = await db_manager.get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sensors/current", response_model=List[SensorDataResponse])
async def get_current_power():
    """Get current power readings for all devices"""
    try:
        data = await db_manager.get_current_power()
        return data
    except Exception as e:
        logger.error(f"Error fetching current power: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sensors/{device_id}/history", response_model=List[SensorDataResponse])
async def get_device_history(
    device_id: str,
    hours: int = 24,
    limit: int = 1000
):
    """Get historical sensor data for a device"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        data = await db_manager.get_sensor_history(device_id, start_time, limit)
        return data
    except Exception as e:
        logger.error(f"Error fetching history for {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sensors/{device_id}/stats", response_model=PowerStatsResponse)
async def get_device_stats(device_id: str, hours: int = 24):
    """Get statistical summary for a device"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        stats = await db_manager.get_device_stats(device_id, start_time)
        if not stats:
            raise HTTPException(status_code=404, detail="No data found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating stats for {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(resolved: Optional[bool] = None, limit: int = 100):
    """Get system alerts"""
    try:
        alerts = await db_manager.get_alerts(resolved, limit)
        return alerts
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """Mark an alert as resolved"""
    try:
        success = await db_manager.resolve_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "resolved", "alert_id": alert_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/total-consumption")
async def get_total_consumption(hours: int = 24):
    """Get total energy consumption across all devices"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db_manager.get_total_consumption(start_time)
        return result
    except Exception as e:
        logger.error(f"Error calculating total consumption: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/cost-estimate")
async def estimate_cost(device_id: Optional[str] = None, hours: int = 24):
    """Estimate energy cost"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        end_time = datetime.utcnow()
        
        if device_id:
            cost = await db_manager.calculate_device_cost(device_id, start_time, end_time)
        else:
            cost = await db_manager.calculate_total_cost(start_time, end_time)
        
        return {
            "device_id": device_id or "all",
            "period_hours": hours,
            "estimated_cost_usd": round(cost, 2),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error estimating cost: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
