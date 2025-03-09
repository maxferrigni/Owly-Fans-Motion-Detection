# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy, timing rules, and confidence-based decisions
#
# March 2025 Update - Version 1.5.4
# - Fixed test alert functionality to properly work with TEST buttons
# - Improved error handling and logging
# - Enhanced alert ID generation and tracking
# - Fixed issue with alert processing logic not triggering for test alerts

from datetime import datetime, timedelta
import pytz
import time
import threading
import os
import traceback
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES, SUPABASE_STORAGE, get_detection_folder
from alert_email import send_email_alert

# Import from push_to_supabase
from push_to_supabase import (
    check_alert_eligibility,
    create_alert_entry,
    update_alert_status,
    generate_alert_id
)

# Import from database_utils
from utilities.database_utils import get_subscribers, get_custom_thresholds, check_column_exists

logger = get_logger()

class AlertManager:
    def __init__(self):
        # Use constants for alert hierarchy (highest to lowest priority)
        self.ALERT_HIERARCHY = ALERT_PRIORITIES

        # Cooldown periods for each alert type (in minutes)
        self.COOLDOWN_PERIODS = {
            "Owl In Box": 30,
            "Owl On Box": 30,
            "Owl In Area": 30,
            "Two Owls": 15,             # More frequent alerts for higher priority events
            "Two Owls In Box": 15,
            "Eggs Or Babies": 10        # Most frequent for highest priority
        }

        # Track last alert times locally
        self.last_alert_times = {alert_type: None for alert_type in self.ALERT_HIERARCHY}

        # Track current alert states
        self.current_states = {alert_type: False for alert_type in self.ALERT_HIERARCHY}

        # Track active alerts for suppression logic
        self.active_alerts = {}

        # Track alert durations for after action report
        self.alert_durations = {alert_type: timedelta(0) for alert_type in self.ALERT_HIERARCHY}
        
        # Track when alerts started for duration tracking
        self.alert_start_times = {alert_type: None for alert_type in self.ALERT_HIERARCHY}
        
        # Track alert counts for after action report
        self.alert_counts = {alert_type: 0 for alert_type in self.ALERT_HIERARCHY}

        # Track alert IDs
        self.alert_ids = {}

        # Default alert delay in minutes
        self.alert_delay = 30
        
        # Default confidence thresholds - can be overridden by config or database
        self.default_confidence_thresholds = {
            "Wyze Internal Camera": 75.0,  # Inside Box: Higher certainty needed
            "Bindy Patio Camera": 65.0,    # On Box: Medium certainty
            "Upper Patio Camera": 55.0     # Area: Lower certainty acceptable
        }

        # Cache database column existence to avoid repeated checks
        self.column_cache = {
            'alerts.confidence_breakdown': None
        }
        
        # Last after action report time
        self.last_after_action_report = None
        
        # Load any custom thresholds from database
        self.load_custom_thresholds()
        
        # Default consecutive frames threshold
        self.DEFAULT_CONSECUTIVE_FRAMES_THRESHOLD = 2
        
        # Read alert settings from environment variables - simplified for v1.3.0
        self.alerts_enabled = {
            'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true'
        }
        
        # Log initial alert settings
        logger.info(f"Alert settings initialized: Email={self.alerts_enabled['email']}")

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
            
            # Update cooldown periods based on the new delay
            # Keep the ratio consistent between different alert types
            self.COOLDOWN_PERIODS = {
                "Owl In Box": delay,
                "Owl On Box": delay,
                "Owl In Area": delay,
                "Two Owls": max(delay // 2, 5),  # Half the delay but minimum 5 minutes
                "Two Owls In Box": max(delay // 2, 5),
                "Eggs Or Babies": max(delay // 3, 3)  # 1/3 the delay but minimum 3 minutes
            }
            
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

    def _send_email_alert_async(self, camera_name, alert_type, alert_entry, alert_id, comparison_image_url=None, confidence_info=None, is_test=False):
        """
        Background thread function to send email alerts.
        
        Args:
            camera_name (str): Name of the camera
            alert_type (str): Type of alert
            alert_entry (dict): Alert entry from database
            alert_id (str): Unique identifier for this alert
            comparison_image_url (str, optional): URL to the comparison image
            confidence_info (dict, optional): Confidence information
            is_test (bool, optional): Whether this is a test alert
        """
        try:
            # Refresh alert settings from environment variables (in case they've changed)
            self.alerts_enabled = {
                'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true'
            }
            
            # Determine if this is a test message and prepare prefix
            test_prefix = "TEST: " if is_test else ""
            
            # Send email alerts if enabled
            email_count = 0
            if self.alerts_enabled['email']:
                try:
                    # Get email subscribers
                    email_subscribers = get_subscribers(notification_type="email", owl_location=alert_type)
                    email_count = len(email_subscribers) if email_subscribers else 0
                    logger.info(f"Sending {'test ' if is_test else ''}email alerts to {email_count} subscribers")
                    
                    # Send email alert with test prefix, image URL, and alert ID
                    send_email_alert(
                        camera_name, 
                        alert_type, 
                        is_test=is_test, 
                        test_prefix=test_prefix,
                        image_url=comparison_image_url,
                        alert_id=alert_id
                    )
                except Exception as e:
                    logger.error(f"Error sending email alerts: {e}")
                    logger.error(traceback.format_exc())
                    email_count = 0
            else:
                logger.info("Email alerts are disabled, skipping")
            
            # Additional info for alert status update
            additional_info = {
                'email_recipients_count': email_count
            }
            
            # Add comparison image URL if available
            if comparison_image_url and check_column_exists('alerts', 'comparison_image_url'):
                additional_info["comparison_image_url"] = comparison_image_url
            
            # Add confidence data if available and if column exists
            if confidence_info:
                # Add confidence score if column exists
                if check_column_exists('alerts', 'owl_confidence_score'):
                    additional_info["owl_confidence_score"] = confidence_info.get("owl_confidence", 0.0)
                
                # Add consecutive frames if column exists
                if check_column_exists('alerts', 'consecutive_owl_frames'):
                    additional_info["consecutive_owl_frames"] = confidence_info.get("consecutive_owl_frames", 0)
                
                # Convert confidence factors to a string representation for logging
                confidence_factors = confidence_info.get("confidence_factors", {})
                if confidence_factors and check_column_exists('alerts', 'confidence_breakdown'):
                    try:
                        factor_str = ", ".join([f"{k}: {v:.1f}%" for k, v in confidence_factors.items()])
                        additional_info["confidence_breakdown"] = factor_str
                    except Exception:
                        pass

            # Update alert status with notification counts and confidence info
            try:
                update_alert_status(
                    alert_id=alert_entry['id'],
                    **additional_info
                )
            except Exception as e:
                logger.error(f"Error updating alert status: {e}")
                logger.error(traceback.format_exc())
            
            # Log completion
            if confidence_info:
                logger.info(
                    f"{'Test ' if is_test else ''}Alert notifications completed for {alert_type} from {camera_name} "
                    f"with {confidence_info.get('owl_confidence', 0.0):.1f}% confidence "
                    f"(Alert ID: {alert_id})"
                )
            else:
                logger.info(f"{'Test ' if is_test else ''}Alert notifications completed for {alert_type} from {camera_name} (Alert ID: {alert_id})")
                
        except Exception as e:
            logger.error(f"Error in background alert processing: {e}")
            logger.error(traceback.format_exc())

    def _send_alert(self, camera_name, alert_type, activity_log_id=None, comparison_image_url=None, confidence_info=None, is_test=False, trigger_condition=None):
        """
        Send email alerts based on alert type and cooldown period.
        
        Args:
            camera_name (str): Name of the camera that triggered the alert
            alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
            activity_log_id (int, optional): ID of the corresponding activity log entry
            comparison_image_url (str, optional): URL to the comparison image
            confidence_info (dict, optional): Confidence information for this alert
            is_test (bool, optional): Whether this is a test alert
            trigger_condition (str, optional): What triggered this alert

        Returns:
            bool: True if alert was sent, False otherwise
        """
        # Check if email alerts are enabled
        if not self.alerts_enabled['email'] and not is_test:
            logger.info("Email alerts are disabled, no alerts will be sent")
            return False
            
        # Generate a unique alert ID
        alert_id = generate_alert_id()
        
        # Set default trigger condition if not provided
        if not trigger_condition:
            trigger_condition = f"Motion detection on {camera_name}: {alert_type}"
            # Add confidence if available
            if confidence_info:
                confidence = confidence_info.get("owl_confidence", 0.0)
                trigger_condition += f" ({confidence:.1f}% confidence)"
                
        # Check alert eligibility based on cooldown period - skip for test alerts
        if not is_test:
            cooldown_period = self.COOLDOWN_PERIODS.get(alert_type, 30)  # Default 30 minutes
            is_eligible, last_alert_data = check_alert_eligibility(
                alert_type, cooldown_period
            )
            if not is_eligible:
                logger.info(f"Alert for {alert_type} blocked by {cooldown_period} minute cooldown")
                return False
        else:
            # For test alerts, always eligible
            is_eligible = True
            logger.info(f"Test alert for {alert_type} - bypassing cooldown check")

        # Create a new alert entry in the database with the alert ID and trigger condition
        alert_entry = create_alert_entry(
            alert_type, 
            activity_log_id, 
            alert_id=alert_id,
            trigger_condition=trigger_condition
        )

        if alert_entry:
            # Store alert ID in our tracking dictionary
            self.alert_ids[alert_id] = {
                'alert_type': alert_type,
                'camera_name': camera_name,
                'timestamp': datetime.now(pytz.utc),
                'is_test': is_test,
                'activity_log_id': activity_log_id
            }
            
            # Start a background thread to send emails
            # This prevents the UI from freezing during network operations
            thread = threading.Thread(
                target=self._send_email_alert_async,
                args=(camera_name, alert_type, alert_entry, alert_id, comparison_image_url, confidence_info, is_test)
            )
            thread.daemon = True  # Make thread exit when main thread exits
            thread.start()

            # Update last alert time (even for test alerts to prevent spamming)
            self.last_alert_times[alert_type] = datetime.now(pytz.utc)
            self.active_alerts[alert_type] = time.time()
            
            # Start tracking duration if not already tracking
            now = datetime.now(pytz.utc)
            if not self.alert_start_times[alert_type] and not is_test:
                self.alert_start_times[alert_type] = now
            
            # Update alert counts for after action report (don't count test alerts)
            if not is_test:
                self.alert_counts[alert_type] += 1
            
            # Log alert creation with alert ID
            if confidence_info:
                logger.info(
                    f"{'Test ' if is_test else ''}Alert sent: {alert_type} from {camera_name} "
                    f"with {confidence_info.get('owl_confidence', 0.0):.1f}% confidence "
                    f"(Alert ID: {alert_id})"
                )
            else:
                logger.info(f"{'Test ' if is_test else ''}Alert sent: {alert_type} from {camera_name} (Alert ID: {alert_id})")

            return True
        else:
            logger.error(f"Failed to create alert entry for {alert_type}")
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

    def determine_alert_type(self, camera_name, detection_result):
        """
        Determine the most appropriate alert type based on detection results.
        
        Args:
            camera_name (str): Name of the camera 
            detection_result (dict): Detection results with all metrics
            
        Returns:
            str: The appropriate alert type
        """
        # Get base alert type from camera mapping
        base_alert_type = detection_result.get("status")
        
        # Check for multiple owls (if the field exists)
        multiple_owls = detection_result.get("multiple_owls", False)
        owl_count = detection_result.get("owl_count", 1)
        
        # Override with multiple owl alert types if applicable
        if multiple_owls or owl_count > 1:
            if base_alert_type == "Owl In Box":
                return "Two Owls In Box"
            return "Two Owls"
                
        # Check for eggs or babies (future enhancement)
        if detection_result.get("eggs_or_babies", False):
            return "Eggs Or Babies"
            
        # Default to the original alert type if no special conditions
        return base_alert_type

    def process_detection(self, camera_name, detection_result, activity_log_id=None, is_test=False):
        """
        Process detection results and send alerts based on hierarchy, cooldown, and confidence.
        Updated in v1.5.4 to handle test alerts properly.
        
        Args:
            camera_name (str): Name of the camera that triggered the detection
            detection_result (dict): Dictionary containing detection results
            activity_log_id (int, optional): ID of the corresponding owl_activity_log entry
            is_test (bool, optional): Whether this is a test alert that should bypass confidence checks

        Returns:
            bool: True if an alert was sent, False otherwise
        """
        try:
            # Refresh alert settings from environment variables
            self.alerts_enabled = {
                'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true'
            }
            
            # Log that we're processing a detection
            logger.info(f"Processing {'test ' if is_test else ''}detection from {camera_name}")
            
            # If email alerts are disabled and this is not a test, log and return early
            if not self.alerts_enabled['email'] and not is_test:
                logger.info("Email alerts are disabled, skipping alert processing")
                return False
            
            # Determine alert type 
            alert_type = self.determine_alert_type(camera_name, detection_result)

            # Check if the alert type is valid
            if alert_type not in self.ALERT_HIERARCHY:
                logger.warning(f"Invalid alert type: {alert_type}")
                return False

            # Check if owl is present (according to detection result)
            # For test alerts, we always consider owl as present
            is_owl_present = detection_result.get("is_owl_present", False) or is_test
            
            if not is_owl_present:
                logger.debug(f"No owl detected for {alert_type}, skipping alert")
                return False
                
            # Get image URL if available
            comparison_image_url = detection_result.get("comparison_image_url")
                
            # Extract confidence information
            confidence_info = {
                "owl_confidence": detection_result.get("owl_confidence", 0.0),
                "consecutive_owl_frames": detection_result.get("consecutive_owl_frames", 0),
                "confidence_factors": detection_result.get("confidence_factors", {})
            }
            
            # Get priority for hierarchy checks
            priority = self.ALERT_HIERARCHY.get(alert_type, 0)
            
            # Create trigger condition
            if detection_result.get("threshold_used"):
                trigger_condition = (f"{'TEST: ' if is_test else ''}Motion detection ({alert_type}): "
                                   f"{confidence_info['owl_confidence']:.1f}% confidence "
                                   f"(threshold: {detection_result['threshold_used']:.1f}%)")
            else:
                trigger_condition = f"{'TEST: ' if is_test else ''}Motion detection ({alert_type})"
            
            # For test alerts, always send regardless of confidence or hierarchy
            if is_test:
                logger.info(f"Processing test alert for {alert_type} from {camera_name}")
                return self._send_alert(
                    camera_name, 
                    alert_type, 
                    activity_log_id, 
                    comparison_image_url, 
                    confidence_info, 
                    is_test=True,
                    trigger_condition=trigger_condition
                )
            
            # Check confidence requirements for real alerts
            if not self._check_confidence_requirements(detection_result, camera_name):
                logger.info(f"Alert blocked - Confidence requirements not met for {camera_name}")
                return False

            # Check alert hierarchy
            if self._check_alert_hierarchy(alert_type, priority):
                logger.info(f"Alert {alert_type} suppressed by higher priority alert")
                return False

            # Determine which alert to send based on hierarchy
            if alert_type in ["Eggs Or Babies", "Two Owls In Box"]:
                # Highest priority alerts - always send
                return self._send_alert(
                    camera_name, 
                    alert_type, 
                    activity_log_id, 
                    comparison_image_url, 
                    confidence_info,
                    trigger_condition=trigger_condition
                )
            elif alert_type == "Two Owls":
                # Only suppressed by eggs/babies or owls in box
                if not self._is_higher_alert_active("Eggs Or Babies") and not self._is_higher_alert_active("Two Owls In Box"):
                    return self._send_alert(
                        camera_name, 
                        alert_type, 
                        activity_log_id, 
                        comparison_image_url, 
                        confidence_info,
                        trigger_condition=trigger_condition
                    )
            elif alert_type == "Owl In Box":
                # Suppressed by any multiple owl alert or eggs/babies
                if (not self._is_higher_alert_active("Eggs Or Babies") and 
                    not self._is_higher_alert_active("Two Owls In Box") and 
                    not self._is_higher_alert_active("Two Owls")):
                    return self._send_alert(
                        camera_name, 
                        alert_type, 
                        activity_log_id, 
                        comparison_image_url, 
                        confidence_info,
                        trigger_condition=trigger_condition
                    )
            elif alert_type == "Owl On Box":
                # Suppressed by box, multiple owls, or eggs/babies 
                if (not self._is_higher_alert_active("Eggs Or Babies") and 
                    not self._is_higher_alert_active("Two Owls In Box") and 
                    not self._is_higher_alert_active("Two Owls") and
                    not self._is_higher_alert_active("Owl In Box")):
                    return self._send_alert(
                        camera_name, 
                        alert_type, 
                        activity_log_id, 
                        comparison_image_url, 
                        confidence_info,
                        trigger_condition=trigger_condition
                    )
            elif alert_type == "Owl In Area":
                # Lowest priority - suppressed by all others
                if (not self._is_higher_alert_active("Eggs Or Babies") and 
                    not self._is_higher_alert_active("Two Owls In Box") and 
                    not self._is_higher_alert_active("Two Owls") and
                    not self._is_higher_alert_active("Owl In Box") and
                    not self._is_higher_alert_active("Owl On Box")):
                    return self._send_alert(
                        camera_name, 
                        alert_type, 
                        activity_log_id, 
                        comparison_image_url, 
                        confidence_info,
                        trigger_condition=trigger_condition
                    )

            return False
            
        except Exception as e:
            logger.error(f"Error processing detection: {e}")
            logger.error(traceback.format_exc())
            return False

    def update_alert_durations(self):
        """
        Update the duration tracking for active alerts.
        
        Should be called periodically to update durations.
        """
        now = datetime.now(pytz.utc)
        for alert_type, start_time in self.alert_start_times.items():
            if start_time:
                # Check if alert is still active (within last 5 minutes)
                if alert_type in self.active_alerts:
                    last_active = self.active_alerts[alert_type]
                    if time.time() - last_active > 300:  # 5 minutes of inactivity
                        # Alert is no longer active, finalize duration
                        duration = now - start_time
                        self.alert_durations[alert_type] += duration
                        self.alert_start_times[alert_type] = None
                # If no active alert record but we have a start time, keep tracking
                # This handles cases where the alert is ongoing but hasn't triggered recently

    def reset_alert_stats(self):
        """
        Reset all statistics for after action report.
        
        Called after generating an after action report or when starting a new session.
        """
        self.alert_counts = {alert_type: 0 for alert_type in self.ALERT_HIERARCHY}
        self.alert_durations = {alert_type: timedelta(0) for alert_type in self.ALERT_HIERARCHY}
        self.alert_start_times = {alert_type: None for alert_type in self.ALERT_HIERARCHY}
        self.last_after_action_report = datetime.now(pytz.utc)

    def get_alert_statistics(self):
        """
        Get all alert statistics.
        
        Returns:
            dict: Dictionary with all alert statistics
        """
        # Update durations before reporting
        self.update_alert_durations()
        
        # Format durations as minutes
        formatted_durations = {}
        for alert_type, duration in self.alert_durations.items():
            total_seconds = duration.total_seconds()
            formatted_durations[alert_type] = {
                'minutes': int(total_seconds // 60),
                'seconds': int(total_seconds % 60)
            }
        
        # Create report data
        report_data = {
            'alert_counts': self.alert_counts.copy(),
            'alert_durations': formatted_durations,
            'total_alerts': sum(self.alert_counts.values()),
            'session_start': self.last_after_action_report.isoformat() if self.last_after_action_report else None,
            'session_end': datetime.now(pytz.utc).isoformat()
        }
        
        return report_data

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
            "confidence_thresholds": self.default_confidence_thresholds.copy(),
            "alert_types_enabled": self.alerts_enabled.copy(),
            "alert_counts": self.alert_counts.copy(),
            "alert_ids_count": len(self.alert_ids)
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

    def get_alert_by_id(self, alert_id):
        """
        Get information about a specific alert by its ID.
        
        Args:
            alert_id (str): The unique alert ID
            
        Returns:
            dict: Alert information or None if not found
        """
        return self.alert_ids.get(alert_id)


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
            },
            "comparison_image_url": "https://example.com/image.jpg"
        }

        # Process test detection with alert ID tracking
        result = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection,
            activity_log_id=1,  # Test ID
            is_test=True  # Use test mode to bypass cooldown
        )

        logger.info(f"Test detection processed: Alert sent = {result}")
        
        # Wait a moment for the background thread to complete
        time.sleep(2)
        
        # Show alert IDs
        logger.info(f"Alert IDs tracked: {len(alert_manager.alert_ids)}")
        for alert_id, details in alert_manager.alert_ids.items():
            logger.info(f"Alert ID: {alert_id}, Type: {details['alert_type']}, Camera: {details['camera_name']}")
        
        logger.info("Alert manager test complete")
        
    except Exception as e:
        logger.error(f"Alert manager test failed: {e}")
        raise