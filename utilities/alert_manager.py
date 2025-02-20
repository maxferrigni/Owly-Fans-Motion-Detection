# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy and timing rules

from datetime import datetime, timedelta
import pytz
import time
from utilities.logging_utils import get_logger
from alert_email import send_email_alert
from push_to_supabase import get_last_alert_time

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

        # Track last alert times locally
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

        # Default alert delay in minutes
        self.alert_delay = 30

    def set_alert_delay(self, minutes):
        """Set the minimum time between alerts in minutes"""
        try:
            delay = int(minutes)
            if delay < 1:
                logger.warning("Alert delay must be at least 1 minute, setting to 1")
                delay = 1
            self.alert_delay = delay
            logger.info(f"Alert delay set to {delay} minutes")
        except ValueError:
            logger.error(f"Invalid alert delay value: {minutes}")

    def _can_send_alert(self, alert_type):
        """
        Check if enough time has passed since the last alert, checking both
        local state and Supabase history.
        """
        now = datetime.now(pytz.timezone('America/Los_Angeles'))

        # Check local cooldown first
        if self.last_alert_times[alert_type] is not None:
            local_time_since = now - self.last_alert_times[alert_type]
            if local_time_since < timedelta(minutes=self.alert_delay):
                logger.info(f"Alert for {alert_type} blocked by local cooldown")
                return False

        # Check Supabase history
        last_alert = get_last_alert_time(alert_type)
        if last_alert is not None:
            # Convert UTC time from Supabase to local time for comparison
            last_alert_local = last_alert.astimezone(pytz.timezone('America/Los_Angeles'))
            time_since_last = now - last_alert_local
            if time_since_last < timedelta(minutes=self.alert_delay):
                logger.info(f"Alert for {alert_type} blocked by database cooldown")
                return False

        return True

    def _should_suppress_alert(self, alert_type):
        """
        Determines if an alert should be suppressed based on alert hierarchy.
        If a higher-priority alert has already been sent recently, suppress lower-priority alerts.
        """
        SUPPRESSION_WINDOW = 300  # 5 minutes
        priority = self.ALERT_HIERARCHY.get(alert_type, 0)
        current_time = time.time()

        # Check for any active higher-priority alerts
        for other_type, timestamp in self.active_alerts.items():
            if self.ALERT_HIERARCHY.get(other_type, 0) > priority:
                time_diff = current_time - timestamp
                if time_diff < SUPPRESSION_WINDOW:
                    logger.info(f"Suppressing {alert_type} alert due to recent {other_type} alert")
                    return True

        return False

    def _send_alert(self, camera_name, alert_type):
        """
        Send alert if cooldown period has passed.
        Returns whether alert was actually sent.
        """
        if self._can_send_alert(alert_type):
            logger.info(f"Sending alert for {alert_type}")
            
            # Send email notification
            send_email_alert(camera_name, alert_type)
            
            # Update tracking
            self.last_alert_times[alert_type] = datetime.now(pytz.timezone('America/Los_Angeles'))
            self.active_alerts[alert_type] = time.time()
            
            return True
            
        return False

    def process_detection(self, camera_name, detection_result):
        """
        Process a new detection result and send alerts if appropriate.
        Returns whether an alert was sent.
        
        Args:
            camera_name (str): Name of the camera
            detection_result (dict): Detection result including status and metrics
            
        Returns:
            bool: Whether an alert was sent
        """
        alert_type = detection_result.get("status")
        is_test = detection_result.get("detection_info", {}).get("is_test", False)
        alert_sent = False
        
        if alert_type not in self.ALERT_HIERARCHY:
            return alert_sent

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
                alert_sent = True
            return alert_sent

        # For real alerts, enforce hierarchy
        if not old_state and is_detected:  # New detection
            if not self._should_suppress_alert(alert_type):
                if alert_type == "Owl In Box":
                    # If owl is in box, only send that alert
                    alert_sent = self._send_alert(camera_name, "Owl In Box")
                elif alert_type == "Owl On Box" and not self._is_higher_alert_active("Owl In Box"):
                    # If owl is on box and not in box, only send on box alert
                    alert_sent = self._send_alert(camera_name, "Owl On Box")
                elif (alert_type == "Owl In Area" and 
                      not self._is_higher_alert_active("Owl On Box") and 
                      not self._is_higher_alert_active("Owl In Box")):
                    # If owl is in area and not on/in box, send area alert
                    alert_sent = self._send_alert(camera_name, "Owl In Area")

        return alert_sent

    def _is_higher_alert_active(self, alert_type):
        """Check if any higher priority alerts are currently active."""
        priority = self.ALERT_HIERARCHY.get(alert_type, 0)
        current_time = time.time()
        
        for other_type, timestamp in self.active_alerts.items():
            if (self.ALERT_HIERARCHY.get(other_type, 0) > priority and 
                current_time - timestamp < 300):  # 5 minute window
                return True
        return False

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
            },
            "alert_delay": self.alert_delay
        }