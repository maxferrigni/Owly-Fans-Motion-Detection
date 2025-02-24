# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy and timing rules

from datetime import datetime, timedelta
import pytz
import time
from utilities.logging_utils import get_logger
from alert_email import send_email_alert
from alert_email_to_text import send_text_alert
from push_to_supabase import (
    check_alert_eligibility,
    create_alert_entry,
    update_alert_status,
    get_subscribers
)

logger = get_logger()

class AlertManager:
    def __init__(self):
        # Alert hierarchy (highest to lowest priority)
        self.ALERT_HIERARCHY = {
            "Owl In Box": 3,
            "Owl On Box": 2,
            "Owl In Area": 1
        }

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
            current_priority (int): Priority of current alert
            
        Returns:
            tuple: (bool, dict) - (should_suppress, suppression_info)
        """
        try:
            # Get recent alerts of higher priority
            for other_type, priority in self.ALERT_HIERARCHY.items():
                if priority > current_priority:
                    is_eligible, last_alert = check_alert_eligibility(other_type)
                    
                    if last_alert and not is_eligible:
                        return True, {
                            "suppressed_by_type": other_type,
                            "suppressed_by_id": last_alert['id'],
                            "reason": f"Suppressed by recent {other_type} alert"
                        }
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking alert hierarchy: {e}")
            return True, {
                "reason": f"Error checking hierarchy: {str(e)}"
            }

    def _send_notifications(self, camera_name, alert_type):
        """
        Send email and SMS notifications.
        
        Args:
            camera_name (str): Name of the camera
            alert_type (str): Type of alert
            
        Returns:
            tuple: (email_count, sms_count) - Number of notifications sent
        """
        try:
            # Get email subscribers
            email_subscribers = get_subscribers(notification_type="email")
            email_count = 0
            if email_subscribers:
                send_email_alert(camera_name, alert_type)
                email_count = len(email_subscribers)
                logger.info(f"Sent {email_count} email notifications")

            # Get SMS subscribers
            sms_subscribers = get_subscribers(
                notification_type="sms",
                owl_location=alert_type.lower().replace(" ", "_")
            )
            sms_count = 0
            if sms_subscribers:
                send_text_alert(camera_name, alert_type)
                sms_count = len(sms_subscribers)
                logger.info(f"Sent {sms_count} SMS notifications")

            return email_count, sms_count

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return 0, 0

    def process_detection(self, camera_name, detection_result, activity_log_id):
        """
        Process a new detection result and send alerts if appropriate.
        
        Args:
            camera_name (str): Name of the camera
            detection_result (dict): Detection result including status and metrics
            activity_log_id (int): ID of the owl_activity_log entry
            
        Returns:
            bool: Whether an alert was sent
        """
        try:
            alert_type = detection_result.get("status")
            if alert_type not in self.ALERT_HIERARCHY:
                return False

            # Check if detection is positive
            is_detected = detection_result.get("status") == alert_type
            if not is_detected:
                return False

            logger.info(f"{alert_type} detected by {camera_name}")
            logger.info(f"Pixel change: {detection_result.get('pixel_change', 0):.2f}%")
            logger.info(f"Luminance change: {detection_result.get('luminance_change', 0):.2f}")

            # Create alert entry
            alert_entry = create_alert_entry(
                owl_activity_log_id=activity_log_id,
                alert_type=alert_type,
                base_cooldown_minutes=self.alert_delay
            )

            if not alert_entry:
                logger.error("Failed to create alert entry")
                return False

            # Check basic eligibility
            is_eligible, last_alert = check_alert_eligibility(alert_type)
            
            # Check hierarchy suppression
            current_priority = self.ALERT_HIERARCHY[alert_type]
            should_suppress, suppression_info = self._check_alert_hierarchy(
                alert_type,
                current_priority
            )

            if should_suppress:
                # Update alert as suppressed
                update_alert_status(
                    alert_id=alert_entry['id'],
                    suppressed=True,
                    suppression_reason=suppression_info['reason'],
                    suppressed_by_id=suppression_info.get('suppressed_by_id'),
                    previous_alert_id=last_alert['id'] if last_alert else None
                )
                return False

            # Handle priority override
            priority_override = False
            if not is_eligible and last_alert:
                last_alert_type = last_alert['alert_type']
                last_priority = self.ALERT_HIERARCHY[last_alert_type]
                
                if current_priority > last_priority:
                    priority_override = True
                    logger.info(f"Priority override: {alert_type} overriding {last_alert_type}")
                else:
                    # Update alert as suppressed by cooldown
                    update_alert_status(
                        alert_id=alert_entry['id'],
                        suppressed=True,
                        suppression_reason="In cooldown period",
                        previous_alert_id=last_alert['id']
                    )
                    return False

            # Send notifications
            email_count, sms_count = self._send_notifications(camera_name, alert_type)

            # Update alert status
            update_alert_status(
                alert_id=alert_entry['id'],
                email_count=email_count,
                sms_count=sms_count,
                previous_alert_id=last_alert['id'] if last_alert else None,
                priority_override=priority_override
            )

            return True

        except Exception as e:
            logger.error(f"Error processing detection: {e}")
            return False

    def get_alert_status(self):
        """Get current alert status for logging/debugging"""
        return {
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
            "pixel_change": 25.5,
            "luminance_change": 30.2,
            "detection_info": {
                "confidence": 0.85,
                "is_test": True
            }
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