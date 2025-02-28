# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy, timing rules, and confidence-based decisions

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
from utilities.database_utils import get_subscribers, get_custom_thresholds

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
        
        # Default confidence thresholds - can be overridden by config or database
        self.default_confidence_thresholds = {
            "Wyze Internal Camera": 75.0,  # Inside Box: Higher certainty needed
            "Bindy Patio Camera": 65.0,    # On Box: Medium certainty
            "Upper Patio Camera": 55.0     # Area: Lower certainty acceptable
        }
        
        # Load any custom thresholds from database
        self.load_custom_thresholds()
        
        # Default consecutive frames threshold
        self.DEFAULT_CONSECUTIVE_FRAMES_THRESHOLD = 2

    def load_custom_thresholds(self):
        """Load any custom thresholds stored in the database"""
        try:
            # Get custom thresholds from database
            custom_thresholds = get_custom_thresholds()
            
            # If we got valid thresholds, update our defaults
            if custom_thresholds and isinstance(custom_thresholds, dict):
                for camera, threshold in custom_thresholds.items():
                    self.default_confidence_thresholds[camera] = threshold
                    logger.info(f"Loaded custom threshold for {camera}: {threshold}%")
                    
        except Exception as e:
            logger.error(f"Error loading custom thresholds: {e}")

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
                    logger.debug(f"Alert {alert_type} suppressed by higher priority {other_type}")
                    return True
        return False

    def _send_alert(self, camera_name, alert_type, activity_log_id=None, confidence_info=None):
        """
        Send alerts based on alert type and cooldown period.
        
        Args:
            camera_name (str): Name of the camera that triggered the alert
            alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
            activity_log_id (int, optional): ID of the corresponding activity log entry
            confidence_info (dict, optional): Confidence information for this alert

        Returns:
            bool: True if alert was sent, False otherwise
        """
        try:
            # Check alert eligibility based on cooldown period
            is_eligible, last_alert_data = check_alert_eligibility(
                alert_type, self.COOLDOWN_PERIODS[alert_type]
            )

            if is_eligible:
                # Create a new alert entry in the database with confidence information
                alert_entry = create_alert_entry(alert_type, activity_log_id)

                if alert_entry:
                    # Send email and SMS alerts
                    send_email_alert(camera_name, alert_type)
                    send_text_alert(camera_name, alert_type)

                    # Get subscriber counts for updating alert status
                    email_subscribers = get_subscribers(notification_type="email", owl_location=alert_type)
                    sms_subscribers = get_subscribers(notification_type="sms", owl_location=alert_type)
                    
                    email_count = len(email_subscribers) if email_subscribers else 0
                    sms_count = len(sms_subscribers) if sms_subscribers else 0
                    
                    # Additional info for alert status update
                    additional_info = {}
                    
                    # Add confidence data if available
                    if confidence_info:
                        additional_info["owl_confidence_score"] = confidence_info.get("owl_confidence", 0.0)
                        additional_info["consecutive_owl_frames"] = confidence_info.get("consecutive_owl_frames", 0)
                        
                        # Convert confidence factors to a string representation for logging
                        confidence_factors = confidence_info.get("confidence_factors", {})
                        if confidence_factors:
                            factor_str = ", ".join([f"{k}: {v:.1f}%" for k, v in confidence_factors.items()])
                            additional_info["confidence_breakdown"] = factor_str

                    # Update alert status with notification counts and confidence info
                    update_alert_status(
                        alert_id=alert_entry['id'],
                        email_count=email_count,
                        sms_count=sms_count,
                        **additional_info
                    )

                    # Update last alert time
                    self.last_alert_times[alert_type] = datetime.now(pytz.utc)
                    self.active_alerts[alert_type] = time.time()
                    
                    # Log with confidence information if available
                    if confidence_info:
                        logger.info(
                            f"Alert sent: {alert_type} from {camera_name} "
                            f"with {confidence_info.get('owl_confidence', 0.0):.1f}% confidence "
                            f"({confidence_info.get('consecutive_owl_frames', 0)} consecutive frames)"
                        )
                    else:
                        logger.info(f"Alert sent: {alert_type} from {camera_name}")

                    return True
                else:
                    logger.error(f"Failed to create alert entry for {alert_type}")
                    return False
            else:
                cooldown_mins = self.COOLDOWN_PERIODS[alert_type]
                logger.info(f"Alert for {alert_type} blocked by {cooldown_mins} minute cooldown")
                return False

        except Exception as e:
            logger.error(f"Error sending alert for {alert_type}: {e}")
            return False

    def _is_higher_alert_active(self, alert_type):
        """Check if any higher priority alerts are currently active."""
        priority = self.ALERT_HIERARCHY.get(alert_type, 0)
        current_time = time.time()
        
        for other_type, timestamp in self.active_alerts.items():
            if (self.ALERT_HIERARCHY.get(other_type, 0) > priority and 
                current_time - timestamp < 300):  # 5 minute window
                logger.debug(f"Alert {alert_type} suppressed by active {other_type} alert")
                return True
        return False

    def _check_confidence_requirements(self, detection_result, camera_name, config=None):
        """
        Check if detection meets confidence requirements for alert.
        
        Args:
            detection_result (dict): Detection results with confidence info
            camera_name (str): Camera name
            config (dict, optional): Camera configuration
            
        Returns:
            bool: True if confidence is sufficient, False otherwise
        """
        try:
            # Get confidence values from detection
            owl_confidence = detection_result.get("owl_confidence", 0.0)
            consecutive_frames = detection_result.get("consecutive_owl_frames", 0)
            
            # Get thresholds from config or use defaults
            confidence_threshold = self.default_confidence_thresholds.get(
                camera_name, 60.0
            )
            
            # Config can override the default if provided
            if config and "owl_confidence_threshold" in config:
                confidence_threshold = config.get("owl_confidence_threshold")
                
            frames_threshold = self.DEFAULT_CONSECUTIVE_FRAMES_THRESHOLD
            
            if config and "consecutive_frames_threshold" in config:
                frames_threshold = config.get("consecutive_frames_threshold", frames_threshold)
            
            # Check if confidence and frames meet requirements
            if owl_confidence < confidence_threshold:
                logger.debug(
                    f"Alert blocked - Confidence too low: {owl_confidence:.1f}% < {confidence_threshold}% "
                    f"for {camera_name}"
                )
                return False
                
            if consecutive_frames < frames_threshold:
                logger.debug(
                    f"Alert blocked - Too few consecutive frames: {consecutive_frames} < {frames_threshold} "
                    f"for {camera_name}"
                )
                return False
                
            logger.info(
                f"Alert confidence requirements met: {owl_confidence:.1f}% confidence, "
                f"{consecutive_frames} consecutive frames for {camera_name}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error checking confidence requirements: {e}")
            return False

    def process_detection(self, camera_name, detection_result, activity_log_id=None):
        """
        Process detection results and send alerts based on hierarchy, cooldown, and confidence.
        
        Args:
            camera_name (str): Name of the camera that triggered the detection
            detection_result (dict): Dictionary containing detection results
            activity_log_id (int, optional): ID of the corresponding owl_activity_log entry

        Returns:
            bool: True if an alert was sent, False otherwise
        """
        alert_sent = False
        alert_type = detection_result.get("status")

        # Check if the alert type is valid
        if alert_type not in self.ALERT_HIERARCHY:
            logger.warning(f"Invalid alert type: {alert_type}")
            return False

        # Check if owl is present (according to detection result)
        is_owl_present = detection_result.get("is_owl_present", False)
        
        if not is_owl_present:
            logger.debug(f"No owl detected for {alert_type}, skipping alert")
            return False
            
        # Extract confidence information
        confidence_info = {
            "owl_confidence": detection_result.get("owl_confidence", 0.0),
            "consecutive_owl_frames": detection_result.get("consecutive_owl_frames", 0),
            "confidence_factors": detection_result.get("confidence_factors", {})
        }
        
        # Check confidence requirements
        if not self._check_confidence_requirements(detection_result, camera_name):
            logger.info(f"Alert blocked - Confidence requirements not met for {camera_name}")
            return False

        # Check alert hierarchy
        priority = self.ALERT_HIERARCHY[alert_type]
        if self._check_alert_hierarchy(alert_type, priority):
            logger.info(f"Alert {alert_type} suppressed by higher priority alert")
            return False
            
        # Check cooldown period
        is_eligible, last_alert = check_alert_eligibility(
            alert_type, self.COOLDOWN_PERIODS[alert_type]
        )

        if not is_eligible:
            logger.debug(f"Alert {alert_type} blocked by cooldown period")
            return False

        # Determine which alert to send based on hierarchy
        if alert_type == "Owl In Box":
            # Always send owl in box alert if it passes confidence check
            alert_sent = self._send_alert(camera_name, "Owl In Box", activity_log_id, confidence_info)
            
        elif alert_type == "Owl On Box" and not self._is_higher_alert_active("Owl In Box"):
            # Send owl on box alert if no active owl in box alert
            alert_sent = self._send_alert(camera_name, "Owl On Box", activity_log_id, confidence_info)
            
        elif (alert_type == "Owl In Area" and 
                not self._is_higher_alert_active("Owl On Box") and 
                not self._is_higher_alert_active("Owl In Box")):
            # If owl is in area and not on/in box, send area alert
            alert_sent = self._send_alert(camera_name, "Owl In Area", activity_log_id, confidence_info)

        return alert_sent

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
            "alert_hierarchy": self.ALERT_HIERARCHY.copy(),
            "confidence_thresholds": self.default_confidence_thresholds.copy()
        }

    def get_confidence_threshold(self, camera_name):
        """Get the confidence threshold for a specific camera"""
        return self.default_confidence_thresholds.get(camera_name, 60.0)

    def set_confidence_threshold(self, camera_name, threshold):
        """Set a custom confidence threshold for a camera"""
        try:
            # Validate threshold
            threshold = float(threshold)
            if threshold < 0 or threshold > 100:
                logger.warning(f"Invalid threshold value: {threshold}. Must be between 0 and 100")
                return False
                
            # Update local threshold
            self.default_confidence_thresholds[camera_name] = threshold
            logger.info(f"Set confidence threshold for {camera_name} to {threshold}%")
            
            # Try to save to database if available
            try:
                from utilities.database_utils import save_custom_threshold
                save_custom_threshold(camera_name, threshold)
            except ImportError:
                logger.debug("Database save function not available, threshold only stored locally")
                
            return True
            
        except ValueError:
            logger.error(f"Invalid threshold value: {threshold}. Must be a number")
            return False


if __name__ == "__main__":
    # Test the alert manager
    try:
        logger.info("Testing alert manager...")
        alert_manager = AlertManager()

        # Test detection processing with confidence
        test_detection = {
            "status": "Owl In Box",
            "motion_detected": True,
            "is_owl_present": True,
            "pixel_change": 25.5,
            "luminance_change": 30.2,
            "owl_confidence": 85.5,  # High confidence
            "consecutive_owl_frames": 3,  # Multiple consecutive frames
            "confidence_factors": {
                "shape_confidence": 35.0,
                "motion_confidence": 30.5,
                "temporal_confidence": 15.0,
                "camera_confidence": 5.0
            }
        }

        # Process test detection
        result = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection,
            activity_log_id=1  # Test ID
        )

        logger.info(f"Test detection processed: Alert sent = {result}")
        
        # Test with low confidence
        test_detection_low_conf = {
            "status": "Owl In Box",
            "motion_detected": True,
            "is_owl_present": True,
            "pixel_change": 25.5,
            "luminance_change": 30.2,
            "owl_confidence": 45.5,  # Below threshold
            "consecutive_owl_frames": 1,  # Too few frames
            "confidence_factors": {
                "shape_confidence": 15.0,
                "motion_confidence": 20.5,
                "temporal_confidence": 5.0,
                "camera_confidence": 5.0
            }
        }
        
        result_low_conf = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection_low_conf,
            activity_log_id=2  # Test ID
        )
        
        logger.info(f"Low confidence test: Alert sent = {result_low_conf}")
        logger.info("Alert manager test complete")

    except Exception as e:
        logger.error(f"Alert manager test failed: {e}")
        raise