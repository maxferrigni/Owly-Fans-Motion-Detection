# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy and timing rules

from datetime import datetime, timedelta
import pytz
import time
from utilities.logging_utils import get_logger
from alert_email import send_email_alert
from alert_email_to_text import send_text_alert

# Import from push_to_supabase
from push_to_supabase import (
    check_alert_eligibility,
    create_alert_entry,
    update_alert_status
)

# Import from database_utils
from utilities.database_utils import get_subscribers

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

    def _check_alert_hierarchy(self, alert_type, current_priority):
        """
        Check if any higher priority alerts are active.
        
        Args:
            alert_type (str): Type of alert being checked
            current_priority (int): Priority of the current alert

        Returns:
            bool: True if a higher priority alert is active, False otherwise
        """
        current_time = time.time()
        for other_type, other_priority in self.ALERT_HIERARCHY.items():
            if other_priority > current_priority and other_type in self.active_alerts:
                last_alert_time = self.active_alerts[other_type]
                if current_time - last_alert_time < 300:  # 5 minute window
                    return True
        return False

    def _send_alert(self, camera_name, alert_type, activity_log_id=None):
        """
        Send alerts based on alert type and cooldown period.
        
        Args:
            camera_name (str): Name of the camera that triggered the alert
            alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
            activity_log_id (int, optional): ID of the corresponding activity log entry

        Returns:
            bool: True if alert was sent, False otherwise
        """
        try:
            # Check alert eligibility based on cooldown period
            is_eligible, last_alert_data = check_alert_eligibility(
                alert_type, self.COOLDOWN_PERIODS[alert_type]
            )

            if is_eligible:
                # Create a new alert entry in the database
                alert_entry = create_alert_entry(alert_type, camera_name, activity_log_id)

                if alert_entry:
                    # Send email and SMS alerts
                    send_email_alert(camera_name, alert_type)
                    send_text_alert(camera_name, alert_type)

                    # Update alert status with notification counts
                    update_alert_status(
                        alert_id=alert_entry['id'],
                        email_count=len(get_subscribers(notification_type="email", owl_location=alert_type)),
                        sms_count=len(get_subscribers(notification_type="sms", owl_location=alert_type))
                    )

                    # Update last alert time
                    self.last_alert_times[alert_type] = datetime.now(pytz.utc)
                    self.active_alerts[alert_type] = time.time()

                    return True
                else:
                    logger.error(f"Failed to create alert entry for {alert_type}")
                    return False
            else:
                logger.info(f"Alert for {alert_type} blocked by cooldown")
                return False

        except Exception as e:
            logger.error(f"Error sending alert for {alert_type}: {e}")
            return False

    def process_detection(self, camera_name, detection_result, activity_log_id=None):
        """
        Process detection results and send alerts based on hierarchy and cooldown.
        
        Args:
            camera_name (str): Name of the camera that triggered the detection
            detection_result (dict): Dictionary containing detection results
            activity_log_id (int, optional): ID of the corresponding owl_activity_log entry

        Returns:
            bool: True if an alert was sent, False otherwise
        """
        alert_sent = False
        alert_type = detection_result["status"]

        # Check if the alert type is valid
        if alert_type not in self.ALERT_HIERARCHY:
            logger.warning(f"Invalid alert type: {alert_type}")
            return False

        # Check if motion was detected
        if not detection_result.get("motion_detected", False):
            logger.debug(f"No motion detected for {alert_type}, skipping alert")
            return False

        # Check alert hierarchy
        priority = self.ALERT_HIERARCHY[alert_type]
        if not self._check_alert_hierarchy(alert_type, priority):
            # Check cooldown period
            is_eligible, last_alert = check_alert_eligibility(
                alert_type, self.COOLDOWN_PERIODS[alert_type]
            )

            if is_eligible:
                # Determine which alert to send based on hierarchy
                if alert_type == "Owl In Box":
                    # Always send owl in box alert
                    alert_sent = self._send_alert(camera_name, "Owl In Box", activity_log_id)
                elif alert_type == "Owl On Box" and not self._is_higher_alert_active("Owl In Box"):
                    # Send owl on box alert if no active owl in box alert
                    alert_sent = self._send_alert(camera_name, "Owl On Box", activity_log_id)
                elif (alert_type == "Owl In Area" and 
                      not self._is_higher_alert_active("Owl On Box") and 
                      not self._is_higher_alert_active("Owl In Box")):
                    # If owl is in area and not on/in box, send area alert
                    alert_sent = self._send_alert(camera_name, "Owl In Area", activity_log_id)

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
            "alert_delay": self.alert_delay,
            "alert_hierarchy": self.ALERT_HIERARCHY.copy()
        }


if __name__ == "__main__":
    # Test the alert manager
    try:
        logger.info("Testing alert manager...")
        alert_manager = AlertManager()

        # Test detection processing
        test_detection = {
            "status": "Owl In Box",
            "motion_detected": True,
            "pixel_change": 25.5,
            "luminance_change": 30.2
        }

        # Process test detection
        result = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection,
            activity_log_id=1  # Test ID
        )

        logger.info(f"Test detection processed: Alert sent = {result}")
        logger.info("Alert manager test complete")

    except Exception as e:
        logger.error(f"Alert manager test failed: {e}")
        raise