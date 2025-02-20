# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy and timing rules

from datetime import datetime, timedelta
import pytz
import time
from utilities.logging_utils import get_logger
from alert_email import send_email_alert
from alert_text import send_text_alert
from alert_email_to_text import send_email_to_text

logger = get_logger()

class AlertManager:
    def __init__(self):
        # Alert hierarchy (highest to lowest priority)
        self.ALERT_HIERARCHY = {
            "Owl In Box": 3,
            "Owl On Box": 2,
            "Owl In Area": 1
        }

        # Cooldown periods for each alert type (in minutes)
        self.COOLDOWN_PERIODS = {
            "Owl In Box": 30,    # 30 minutes between box alerts
            "Owl On Box": 45,    # 45 minutes between on-box alerts
            "Owl In Area": 60    # 60 minutes between area alerts
        }

        # Track last alert times
        self.last_alert_times = {
            "Owl In Box": None,
            "Owl On Box": None,
            "Owl In Area": None
        }

        # Track current alert states
        self.current_states = {
            "Owl In Box": False,
            "Owl On Box": False,
            "Owl In Area": False
        }

        # Track active alerts for suppression logic
        self.active_alerts = {}

    def _can_send_alert(self, alert_type):
        """Check if enough time has passed since the last alert"""
        if self.last_alert_times[alert_type] is None:
            return True

        now = datetime.now(pytz.timezone('America/Los_Angeles'))
        cooldown = timedelta(minutes=self.COOLDOWN_PERIODS[alert_type])
        time_since_last = now - self.last_alert_times[alert_type]

        return time_since_last > cooldown

    def _is_higher_alert_active(self, alert_type):
        """Check if any higher priority alerts are currently active."""
        priority = self.ALERT_HIERARCHY.get(alert_type, 0)
        current_time = time.time()
        
        for other_type, timestamp in self.active_alerts.items():
            if (self.ALERT_HIERARCHY.get(other_type, 0) > priority and 
                current_time - timestamp < 300):  # 5 minute window
                return True
        return False

    def _send_alert(self, camera_name, alert_type):
        """Send alert if cooldown period has passed."""
        if self._can_send_alert(alert_type):
            logger.info(f"Sending alert for {alert_type}")
            
            # Send primary notifications
            send_email_alert(camera_name, alert_type)
            send_text_alert(camera_name, alert_type)
            
            # Update tracking
            self.last_alert_times[alert_type] = datetime.now(pytz.timezone('America/Los_Angeles'))
            self.active_alerts[alert_type] = time.time()
            
            # Try backup notification if needed
            try:
                send_email_to_text(camera_name, alert_type)
            except Exception as e:
                logger.error(f"Backup notification failed: {e}")

    def process_detection(self, camera_name, detection_result):
        """
        Process a new detection result and send alerts if appropriate.
        
        Args:
            camera_name (str): Name of the camera
            detection_result (dict): Detection result including status and metrics
        """
        alert_type = detection_result.get("status")
        is_test = detection_result.get("detection_info", {}).get("is_test", False)
        
        if alert_type not in self.ALERT_HIERARCHY:
            return

        # Update current state
        is_detected = detection_result.get("status") == alert_type
        old_state = self.current_states[alert_type]
        self.current_states[alert_type] = is_detected

        if is_detected:
            logger.info(f"{alert_type} detected by {camera_name}")
            logger.info(f"Pixel change: {detection_result.get('pixel_change', 0):.2f}%")
            logger.info(f"Luminance change: {detection_result.get('luminance_change', 0):.2f}")

        # Handle test mode differently
        if is_test:
            if self._can_send_alert(alert_type):
                logger.info(f"Sending test alert for {alert_type}")
                send_email_alert(camera_name, alert_type)
                self.last_alert_times[alert_type] = datetime.now(pytz.timezone('America/Los_Angeles'))
            return

        # For real alerts, enforce hierarchy
        if not old_state and is_detected:  # New detection
            if alert_type == "Owl In Box":
                # If owl is in box, only send that alert
                self._send_alert(camera_name, "Owl In Box")
            elif alert_type == "Owl On Box" and not self._is_higher_alert_active("Owl In Box"):
                # If owl is on box and not in box, only send on box alert
                self._send_alert(camera_name, "Owl On Box")
            elif (alert_type == "Owl In Area" and 
                  not self._is_higher_alert_active("Owl On Box") and 
                  not self._is_higher_alert_active("Owl In Box")):
                # If owl is in area and not on/in box, send area alert
                self._send_alert(camera_name, "Owl In Area")

    def get_alert_status(self):
        """Get current alert status for logging/debugging"""
        return {
            "current_states": self.current_states.copy(),
            "last_alert_times": {
                k: v.isoformat() if v else None 
                for k, v in self.last_alert_times.items()
            },
            "active_alerts": {
                k: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(v))
                for k, v in self.active_alerts.items()
            }
        }