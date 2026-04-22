#!/usr/bin/env python3
"""
Energy Monitor Health Check Script
Run this to verify all systems are operational
"""

import requests
import json
import sys
import os
from datetime import datetime, timedelta

class HealthChecker:
    def __init__(self):
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.grafana_url = "http://localhost:3000"
        self.prometheus_url = "http://localhost:9090"
        self.issues = []
        self.warnings = []
    
    def print_header(self, text):
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}")
    
    def check_backend_health(self):
        """Check backend API health"""
        self.print_header("Backend API Health")
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print(f"✅ Status: {health['status'].upper()}")
                print(f"✅ Database: {'Connected' if health['database'] else 'DISCONNECTED'}")
                print(f"✅ MQTT: {'Connected' if health['mqtt'] else 'DISCONNECTED'}")
                
                if not health['database']:
                    self.issues.append("Database not connected")
                if not health['mqtt']:
                    self.issues.append("MQTT broker not connected")
                
                return True
            else:
                print(f"❌ Backend returned status {response.status_code}")
                self.issues.append("Backend unhealthy")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to backend: {e}")
            self.issues.append(f"Backend unreachable: {e}")
            return False
    
    def check_devices(self):
        """Check registered devices"""
        self.print_header("Registered Devices")
        try:
            response = requests.get(f"{self.backend_url}/devices", timeout=5)
            if response.status_code == 200:
                devices = response.json()
                print(f"✅ Total devices: {len(devices)}")
                
                if len(devices) == 0:
                    self.warnings.append("No devices registered yet")
                else:
                    for device in devices[:5]:  # Show first 5
                        print(f"   - {device['device_id']}: {device['device_name']}")
                    if len(devices) > 5:
                        print(f"   ... and {len(devices) - 5} more")
                return True
            else:
                print(f"❌ Failed to fetch devices")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def check_recent_data(self):
        """Check if data is being received"""
        self.print_header("Recent Data")
        try:
            response = requests.get(f"{self.backend_url}/sensors/current", timeout=5)
            if response.status_code == 200:
                current = response.json()
                
                if len(current) == 0:
                    print("⚠️  No current readings - data may not be flowing")
                    self.warnings.append("No current sensor readings")
                    return False
                
                print(f"✅ Active readings: {len(current)}")
                for reading in current[:3]:  # Show first 3
                    print(f"   - {reading['device_id']}: {reading['power_watts']:.2f}W")
                    
                    # Check if data is recent (within 5 minutes)
                    data_time = datetime.fromisoformat(reading['time'].replace('Z', '+00:00'))
                    age = datetime.utcnow().replace(tzinfo=data_time.tzinfo) - data_time
                    
                    if age > timedelta(minutes=5):
                        self.warnings.append(f"Device {reading['device_id']} data is stale ({age})")
                
                return True
            else:
                print(f"❌ Failed to fetch current data")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def check_ml_models(self):
        """Check ML model status"""
        self.print_header("ML Anomaly Detection")
        try:
            # Check if models directory exists and has models
            models_exist = os.path.exists("/app/models") if os.path.exists("/app") else False
            
            # Try to get recent anomalies
            response = requests.get(
                f"{self.backend_url}/alerts?resolved=false&limit=10",
                timeout=5
            )
            
            if response.status_code == 200:
                alerts = response.json()
                ml_alerts = [a for a in alerts if a.get('alert_type') == 'ml_anomaly']
                
                if len(ml_alerts) > 0:
                    print(f"✅ ML detection active: {len(ml_alerts)} recent anomalies")
                else:
                    print("ℹ️  ML models running (no recent anomalies)")
                    self.warnings.append("ML models may need more training data (1000+ samples per device)")
                
                return True
            else:
                print("⚠️  Cannot check ML status")
                return False
        except Exception as e:
            print(f"⚠️  ML check failed: {e}")
            return False
    
    def check_prometheus(self):
        """Check Prometheus metrics"""
        self.print_header("Prometheus Metrics")
        try:
            # Check if Prometheus is up
            response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            
            if response.status_code == 200:
                print("✅ Prometheus is running")
                
                # Query some key metrics
                metrics_to_check = [
                    ("energy_monitor_mqtt_messages_received_total", "MQTT messages received"),
                    ("energy_monitor_database_inserts_total", "Database inserts"),
                    ("energy_monitor_active_devices", "Active devices")
                ]
                
                for metric, description in metrics_to_check:
                    query_response = requests.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params={"query": metric},
                        timeout=5
                    )
                    
                    if query_response.status_code == 200:
                        data = query_response.json()
                        if data['data']['result']:
                            value = data['data']['result'][0]['value'][1]
                            print(f"   ✓ {description}: {value}")
                    else:
                        print(f"   ⚠️  Could not query {metric}")
                
                return True
            else:
                print("❌ Prometheus not responding")
                self.issues.append("Prometheus unavailable")
                return False
        except Exception as e:
            print(f"❌ Prometheus unreachable: {e}")
            self.issues.append("Prometheus not accessible")
            return False
    
    def check_grafana(self):
        """Check Grafana availability"""
        self.print_header("Grafana Dashboards")
        try:
            response = requests.get(f"{self.grafana_url}/api/health", timeout=5)
            
            if response.status_code == 200:
                print("✅ Grafana is running")
                print(f"   Access at: {self.grafana_url}")
                return True
            else:
                print("❌ Grafana not responding")
                self.issues.append("Grafana unavailable")
                return False
        except Exception as e:
            print(f"❌ Grafana unreachable: {e}")
            self.issues.append("Grafana not accessible")
            return False
    
    def check_data_quality(self):
        """Check data quality and completeness"""
        self.print_header("Data Quality")
        try:
            # Get stats for last 24 hours
            response = requests.get(
                f"{self.backend_url}/analytics/total-consumption?hours=24",
                timeout=5
            )
            
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ 24h Energy: {stats['total_kwh']:.2f} kWh")
                print(f"   Avg Power: {stats['avg_power_watts']:.2f}W")
                print(f"   Peak Power: {stats['peak_power_watts']:.2f}W")
                
                if stats['total_kwh'] < 0.01:
                    self.warnings.append("Very low energy consumption - check if devices are publishing")
                
                return True
            else:
                print("⚠️  Cannot check data quality")
                return False
        except Exception as e:
            print(f"⚠️  Data quality check failed: {e}")
            return False
    
    def run_all_checks(self):
        """Run all health checks"""
        print("\n" + "="*60)
        print("  ENERGY MONITOR HEALTH CHECK")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        checks = [
            self.check_backend_health,
            self.check_devices,
            self.check_recent_data,
            self.check_data_quality,
            self.check_ml_models,
            self.check_prometheus,
            self.check_grafana
        ]
        
        passed = sum(1 for check in checks if check())
        total = len(checks)
        
        # Summary
        self.print_header("SUMMARY")
        print(f"Checks Passed: {passed}/{total}")
        
        if self.issues:
            print("\n❌ CRITICAL ISSUES:")
            for issue in self.issues:
                print(f"   - {issue}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if not self.issues and not self.warnings:
            print("\n✅ All systems operational!")
        
        print("\n" + "="*60)
        
        # Exit code
        return 0 if not self.issues else 1


if __name__ == "__main__":
    checker = HealthChecker()
    sys.exit(checker.run_all_checks())
