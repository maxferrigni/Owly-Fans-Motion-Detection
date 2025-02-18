# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy and timing rules

from datetime import datetime, timedelta
import pytz
from utilities.logging_utils import get_logger
from alert_email import send_email_alert

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

    def _can_send_alert(self, alert_type):
        """Check if enough time has passed since last alert"""
        if self.last_alert_times[alert_type] is None:
            return True
            
        now = datetime.now(pytz.timezone('America/Los_Angeles'))
        cooldown = timedelta(minutes=self.COOLDOWN_PERIODS[alert_type])
        time_since_last = now - self.last_alert_times[alert_type]
        
        return time_since_last > cooldown

    def _should_suppress_alert(self, alert_type):
        """Check if alert should be suppressed due to higher priority alert"""
        alert_priority = self.ALERT_HIERARCHY[alert_type]
        
        # Check if any higher priority alerts are active
        for other_type, other_priority in self.ALERT_HIERARCHY.items():
            if other_priority > alert_priority and self.current_states[other_type]:
                logger.info(f"Suppressing {alert_type} alert due to active {other_type}")
                return True
        
        return False

    def process_detection(self, camera_name, detection_result):
        """
        Process a new detection result and send alerts if appropriate.
        
        Args:
            camera_name (str): Name of the camera
            detection_result (dict): Detection result including status and metrics
        """
        alert_type = detection_result.get("status")
        if alert_type not in self.ALERT_HIERARCHY:
            return
            
        # Update current state
        is_detected = detection_result.get("status") == alert_type
        old_state = self.current_states[alert_type]
        self.current_states[alert_type] = is_detected
        
        # Log the detection regardless of alert status
        if is_detected:
            logger.info(f"{alert_type} detected by {camera_name}")
            logger.info(f"Pixel change: {detection_result.get('pixel_change', 0):.2f}%")
            logger.info(f"Luminance change: {detection_result.get('luminance_change', 0):.2f}")
        
        # Check if we should send an alert
        if is_detected and not old_state:  # New detection
            if not self._should_suppress_alert(alert_type):
                if self._can_send_alert(alert_type):
                    logger.info(f"Sending alert for {alert_type}")
                    send_email_alert(camera_name, alert_type)
                    self.last_alert_times[alert_type] = datetime.now(pytz.timezone('America/Los_Angeles'))
                else:
                    logger.info(f"Alert for {alert_type} in cooldown period")
            
    def get_alert_status(self):
        """Get current alert status for logging/debugging"""
        return {
            "current_states": self.current_states.copy(),
            "last_alert_times": {k: v.isoformat() if v else None 
                               for k, v in self.last_alert_times.items()}
        }