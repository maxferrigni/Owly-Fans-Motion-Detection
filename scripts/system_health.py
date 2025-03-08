"""
System Health Monitor for Owl Monitoring System.

Checks various system components and reports their status.

Current health checks:
1. Wyze Camera - Checks if camera feed is black/frozen
2. OBS Process - Checks if OBS is running

Future potential checks:
- Disk space monitoring
- CPU usage monitoring
- Network connectivity
- Base image freshness
- Database connectivity
"""

import os
import time
import threading
import psutil
import pyautogui
import numpy as np
from datetime import datetime, timedelta
from utilities.logging_utils import get_logger

logger = get_logger()

class SystemHealthMonitor:
    """Central system health monitoring framework"""
    
    def __init__(self):
        # Health check interval (30 minutes)
        self.check_interval = 30 * 60
        
        # Initialize health checks
        self.health_checks = []
        self.setup_health_checks()
        
        # State tracking
        self.running = False
        self.monitoring_thread = None
        self.status_callbacks = []
        
        # Last overall health status
        self.overall_status = "Unknown"
        
    def setup_health_checks(self):
        """Setup all health check components"""
        # Add Wyze camera check
        self.health_checks.append(WyzeCameraCheck())
        
        # Add OBS process check
        self.health_checks.append(ObsProcessCheck())
        
    def add_status_callback(self, callback):
        """Add a callback function to receive status updates"""
        self.status_callbacks.append(callback)
        
    def notify_status_update(self):
        """Notify all callbacks of status updates"""
        status = self.get_status()
        for callback in self.status_callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
                
    def get_status(self):
        """Get the overall system health status"""
        # Collect individual statuses
        check_statuses = [check.get_status() for check in self.health_checks]
        
        # Determine overall health (healthy only if all checks are healthy)
        overall_healthy = all(status["healthy"] for status in check_statuses)
        
        # Create the overall status
        return {
            "healthy": overall_healthy,
            "status": "Healthy" if overall_healthy else "Issues Detected",
            "checks": check_statuses,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    def run_health_checks(self):
        """Run all health checks once"""
        logger.info("Running system health checks...")
        
        for check in self.health_checks:
            try:
                # Run the individual check
                check.check()
                logger.info(f"Health check '{check.name}': {check.status}")
            except Exception as e:
                logger.error(f"Error running health check '{check.name}': {e}")
                check.status = f"Error: {str(e)[:50]}"
                check.healthy = False
                
        # Update overall status and notify callbacks
        self.overall_status = "Healthy" if all(check.healthy for check in self.health_checks) else "Issues Detected"
        self.notify_status_update()
        
    def monitoring_loop(self):
        """Background monitoring thread"""
        while self.running:
            # Run all health checks
            self.run_health_checks()
            
            # Sleep until next check
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
                
    def start_monitoring(self):
        """Start the health monitoring thread"""
        if self.running:
            logger.warning("System health monitoring already running")
            return False
            
        self.running = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info("System health monitoring started")
        return True
        
    def stop_monitoring(self):
        """Stop the health monitoring thread"""
        if not self.running:
            return
            
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
            
        logger.info("System health monitoring stopped")

class SystemHealthCheck:
    """Base class for system health checks"""
    
    def __init__(self, name):
        self.name = name
        self.status = "Unknown"
        self.last_check_time = None
        self.healthy = False
        
    def check(self):
        """Perform the health check - override in subclasses"""
        raise NotImplementedError
        
    def get_status(self):
        """Get the current status"""
        return {
            "name": self.name,
            "status": self.status,
            "healthy": self.healthy,
            "last_check": self.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time else None
        }

class WyzeCameraCheck(SystemHealthCheck):
    """Check if Wyze camera feed is working"""
    
    def __init__(self):
        super().__init__("Wyze Camera")
        
        # Default ROI for Wyze camera
        self.camera_roi = (-1899, 698, -1255, 1039)
        self.black_threshold = 20  # Average pixel value below this is considered black
        
    def check(self):
        """Check if camera feed is black/frozen"""
        try:
            # Capture screenshot of camera area
            x, y, width, height = self.camera_roi
            width = abs(width - x)
            height = abs(height - y)
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            # Convert to numpy array for analysis
            img_array = np.array(screenshot)
            
            # Calculate average brightness
            avg_brightness = np.mean(img_array)
            
            # Update status based on brightness
            if avg_brightness < self.black_threshold:
                self.status = "Black Screen"
                self.healthy = False
                logger.warning(f"Wyze camera appears black (brightness: {avg_brightness:.2f})")
            else:
                self.status = "Normal"
                self.healthy = True
                logger.info(f"Wyze camera appears normal (brightness: {avg_brightness:.2f})")
                
            self.last_check_time = datetime.now()
            return self.healthy
            
        except Exception as e:
            self.status = f"Error: {str(e)[:50]}"
            self.healthy = False
            self.last_check_time = datetime.now()
            logger.error(f"Error checking Wyze camera: {e}")
            return False

class ObsProcessCheck(SystemHealthCheck):
    """Check if OBS is running"""
    
    def __init__(self):
        super().__init__("OBS Process")
        
    def check(self):
        """Check if OBS process is running"""
        try:
            obs_running = False
            
            # Look for OBS process
            for proc in psutil.process_iter(['name']):
                if 'obs' in proc.info['name'].lower():
                    obs_running = True
                    break
                    
            if obs_running:
                self.status = "Running"
                self.healthy = True
                logger.info("OBS process is running")
            else:
                self.status = "Not Running"
                self.healthy = False
                logger.warning("OBS process is not running")
                
            self.last_check_time = datetime.now()
            return self.healthy
            
        except Exception as e:
            self.status = f"Error: {str(e)[:50]}"
            self.healthy = False
            self.last_check_time = datetime.now()
            logger.error(f"Error checking OBS process: {e}")
            return False

# Future health checks can be added as new classes that inherit from SystemHealthCheck
# Example:
#
# class DiskSpaceCheck(SystemHealthCheck):
#     def __init__(self, path="/", threshold_gb=5):
#         super().__init__("Disk Space")
#         self.path = path
#         self.threshold_bytes = threshold_gb * 1024 * 1024 * 1024
#
#     def check(self):
#         ...

# Test code that runs only when this file is executed directly
if __name__ == "__main__":
    # Set up basic logging to console for testing
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testing System Health Monitor...")
    
    # Create the monitor
    monitor = SystemHealthMonitor()
    
    # Add a test callback
    def test_callback(status):
        print("\nHealth Status Update:")
        print(f"Overall: {status['status']}")
        for check in status['checks']:
            print(f"  {check['name']}: {check['status']} (Healthy: {check['healthy']})")
    
    monitor.add_status_callback(test_callback)
    
    # Run health checks once
    print("\nRunning health checks once...")
    monitor.run_health_checks()
    
    # Ask if user wants to start monitoring
    response = input("\nStart continuous monitoring? (y/n): ")
    if response.lower() == 'y':
        monitor.start_monitoring()
        
        try:
            print("Monitoring started. Press Ctrl+C to stop.")
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
            monitor.stop_monitoring()
    
    print("System Health Monitor test complete.")