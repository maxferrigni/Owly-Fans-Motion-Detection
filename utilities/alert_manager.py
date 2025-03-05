# File: utilities/alert_manager.py
# Purpose: Manage owl detection alerts with hierarchy, timing rules, and confidence-based decisions
#
# March 4, 2025 Update - Version 1.1.0
# - Updated alert priority system with enhanced hierarchy
# - Added support for multiple owl detection scenarios
# - Include image links in all alert types
# - Prepared framework for after action reporting

from datetime import datetime, timedelta
import pytz
import time
import threading
import os
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES, SUPABASE_STORAGE, get_detection_folder
from alert_email import send_email_alert
from alert_text import send_text_alert
from alert_email_to_text import send_text_via_email

# Import from push_to_supabase
from push_to_supabase import (
    check_alert_eligibility,
    create_alert_entry,
    update_alert_status
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
        self.last_alert_times = {
            "Owl In Box": None,
            "Owl On Box": None,
            "Owl In Area": None,
            "Two Owls": None,
            "Two Owls In Box": None,
            "Eggs Or Babies": None
        }

        # Track current alert states
        self.current_states = {
            "Owl In Box": False,
            "Owl On Box": False,
            "Owl In Area": False,
            "Two Owls": False,
            "Two Owls In Box": False,
            "Eggs Or Babies": False
        }

        # Track active alerts for suppression logic
        self.active_alerts = {}

        # Track alert durations for after action report
        self.alert_durations = {
            "Owl In Box": timedelta(0),
            "Owl On Box": timedelta(0),
            "Owl In Area": timedelta(0),
            "Two Owls": timedelta(0),
            "Two Owls In Box": timedelta(0),
            "Eggs Or Babies": timedelta(0)
        }
        
        # Track when alerts started for duration tracking
        self.alert_start_times = {
            "Owl In Box": None,
            "Owl On Box": None,
            "Owl In Area": None,
            "Two Owls": None,
            "Two Owls In Box": None,
            "Eggs Or Babies": None
        }
        
        # Track alert counts for after action report
        self.alert_counts = {
            "Owl In Box": 0,
            "Owl On Box": 0,
            "Owl In Area": 0,
            "Two Owls": 0,
            "Two Owls In Box": 0,
            "Eggs Or Babies": 0
        }

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
        
        # Read alert settings from environment variables
        self.alerts_enabled = {
            'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true',
            'text': os.environ.get('OWL_TEXT_ALERTS', 'True').lower() == 'true',
            'email_to_text': os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() == 'true'
        }
        
        # Log initial alert settings
        logger.info(f"Alert settings initialized: Email={self.alerts_enabled['email']}, " +
                   f"Text={self.alerts_enabled['text']}, " +
                   f"Email-to-Text={self.alerts_enabled['email_to_text']}")

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

    def _send_email_and_sms_async(self, camera_name, alert_type, alert_entry, comparison_image_url=None, confidence_info=None, is_test=False):
        """
        Background thread function to send email and SMS alerts.
        
        Args:
            camera_name (str): Name of the camera
            alert_type (str): Type of alert
            alert_entry (dict): Alert entry from database
            comparison_image_url (str, optional): URL to the comparison image
            confidence_info (dict, optional): Confidence information
            is_test (bool, optional): Whether this is a test alert
        """
        try:
            # Refresh alert settings from environment variables (in case they've changed)
            self.alerts_enabled = {
                'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true',
                'text': os.environ.get('OWL_TEXT_ALERTS', 'True').lower() == 'true',
                'email_to_text': os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() == 'true'
            }
            
            # Determine if this is a test message and prepare prefix
            test_prefix = "TEST: " if is_test else ""
            
            # Send email alerts in a try block to continue if it fails
            email_count = 0
            if self.alerts_enabled['email']:
                try:
                    # Get email subscribers
                    email_subscribers = get_subscribers(notification_type="email", owl_location=alert_type)
                    email_count = len(email_subscribers) if email_subscribers else 0
                    logger.info(f"Sending email alerts to {email_count} subscribers")
                    
                    # Send email alert with test prefix if needed and include image URL
                    send_email_alert(
                        camera_name, 
                        alert_type, 
                        is_test=is_test, 
                        test_prefix=test_prefix,
                        image_url=comparison_image_url  # New in v1.1.0 - Include image URL
                    )
                except Exception as e:
                    logger.error(f"Error sending email alerts: {e}")
                    email_count = 0
            else:
                logger.info("Email alerts are disabled, skipping")
            
            # Send SMS alerts in a separate try block
            sms_count = 0
            if self.alerts_enabled['text']:
                try:
                    # Get SMS subscribers
                    sms_subscribers = get_subscribers(notification_type="sms", owl_location=alert_type)
                    sms_count = len(sms_subscribers) if sms_subscribers else 0
                    logger.info(f"Sending SMS alerts to {sms_count} subscribers")
                    
                    # Send SMS alert with test prefix if needed and include image URL
                    send_text_alert(
                        camera_name, 
                        alert_type, 
                        is_test=is_test, 
                        test_prefix=test_prefix,
                        image_url=comparison_image_url  # New in v1.1.0 - Include image URL
                    )
                except Exception as e:
                    logger.error(f"Error sending SMS alerts: {e}")
                    sms_count = 0
            else:
                logger.info("Text alerts are disabled, skipping")
            
            # Handle email-to-text alerts separately
            email_to_text_count = 0
            if self.alerts_enabled['email_to_text']:
                try:
                    # This would typically be inside send_text_alert, but we're keeping it separate
                    # for clarity in this example
                    
                    # Get email-to-text subscribers
                    subscribers = get_subscribers(notification_type="email_to_text", owl_location=alert_type)
                    email_to_text_count = len(subscribers) if subscribers else 0
                    logger.info(f"Sending email-to-text alerts to {email_to_text_count} subscribers")
                    
                    if subscribers:
                        for subscriber in subscribers:
                            if subscriber.get('phone') and subscriber.get('carrier'):
                                # Create message with test prefix if needed and image URL
                                message = self._get_alert_message(
                                    camera_name, 
                                    alert_type, 
                                    is_test, 
                                    image_url=comparison_image_url  # New in v1.1.0
                                )
                                send_text_via_email(
                                    subscriber['phone'],
                                    subscriber['carrier'].lower(),
                                    message,
                                    subscriber.get('name')
                                )
                except Exception as e:
                    logger.error(f"Error sending email-to-text alerts: {e}")
                    email_to_text_count = 0
            else:
                logger.info("Email-to-text alerts are disabled, skipping")
            
            # Additional info for alert status update
            additional_info = {
                'email_recipients_count': email_count,
                'sms_recipients_count': sms_count + email_to_text_count  # Combine both SMS types
            }
            
            # Add comparison image URL if available
            if comparison_image_url and check_column_exists('alerts', 'comparison_image_url'):
                additional_info["comparison_image_url"] = comparison_image_url
            
            # Add confidence data if available and if column exists
            if confidence_info:
                # Check if owl_confidence_score column exists
                if check_column_exists('alerts', 'owl_confidence_score'):
                    additional_info["owl_confidence_score"] = confidence_info.get("owl_confidence", 0.0)
                
                # Check if consecutive_owl_frames column exists
                if check_column_exists('alerts', 'consecutive_owl_frames'):
                    additional_info["consecutive_owl_frames"] = confidence_info.get("consecutive_owl_frames", 0)
                
                # Convert confidence factors to a string representation for logging
                confidence_factors = confidence_info.get("confidence_factors", {})
                if confidence_factors:
                    # Check if confidence_breakdown column exists
                    if check_column_exists('alerts', 'confidence_breakdown'):
                        try:
                            factor_str = ", ".join([f"{k}: {v:.1f}%" for k, v in confidence_factors.items()])
                            additional_info["confidence_breakdown"] = factor_str
                        except Exception:
                            logger.debug("Error formatting confidence_breakdown")

            # Update alert status with notification counts and confidence info
            try:
                update_alert_status(
                    alert_id=alert_entry['id'],
                    **additional_info
                )
            except Exception as e:
                logger.error(f"Error updating alert status: {e}")
            
            # Log completion
            if confidence_info:
                logger.info(
                    f"Alert notifications completed for {alert_type} from {camera_name} "
                    f"with {confidence_info.get('owl_confidence', 0.0):.1f}% confidence"
                )
            else:
                logger.info(f"Alert notifications completed for {alert_type} from {camera_name}")
                
        except Exception as e:
            logger.error(f"Error in background alert processing: {e}")

    def _get_alert_message(self, camera_name, alert_type, is_test=False, image_url=None):
        """
        Generate alert message text with optional TEST prefix and image URL.
        
        Args:
            camera_name (str): Name of the camera
            alert_type (str): Type of alert
            is_test (bool): Whether this is a test message
            image_url (str, optional): URL to the image for this alert
            
        Returns:
            str: Formatted message text
        """
        # Add TEST prefix if this is a test message
        test_prefix = "TEST: " if is_test else ""
        
        # Base message components
        message_parts = {
            "Owl In Area": f"Motion has been detected in the Upper Patio area.",
            "Owl On Box": f"Motion has been detected on the Owl Box.",
            "Owl In Box": f"Motion has been detected in the Owl Box.",
            "Two Owls": f"Two owls have been detected!",
            "Two Owls In Box": f"Two owls have been detected in the box!",
            "Eggs Or Babies": f"Eggs or babies may have been detected in the box!"
        }
        
        # Get appropriate message part based on alert type
        message_part = message_parts.get(
            alert_type, 
            f"Motion has been detected by {camera_name}!"
        )
        
        # Construct full message
        message = f"{test_prefix}{message_part} Please check the camera feed at www.owly-fans.com"
        
        # Add image URL if provided - New in v1.1.0
        if image_url:
            message += f"\nView image: {image_url}"
            
        return message

    def _send_alert(self, camera_name, alert_type, activity_log_id=None, comparison_image_url=None, confidence_info=None, is_test=False):
        """
        Send alerts based on alert type and cooldown period.
        
        Args:
            camera_name (str): Name of the camera that triggered the alert
            alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
            activity_log_id (int, optional): ID of the corresponding activity log entry
            comparison_image_url (str, optional): URL to the comparison image
            confidence_info (dict, optional): Confidence information for this alert
            is_test (bool, optional): Whether this is a test alert

        Returns:
            bool: True if alert was sent, False otherwise
        """
        try:
            # Check if any alert types are enabled
            if not any(self.alerts_enabled.values()):
                logger.info("All alert types are disabled, no alerts will be sent")
                return False
                
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

            # Create a new alert entry in the database with confidence information
            alert_entry = create_alert_entry(alert_type, activity_log_id)

            if alert_entry:
                # Start a background thread to send emails and SMS
                # This prevents the UI from freezing during network operations
                thread = threading.Thread(
                    target=self._send_email_and_sms_async,
                    args=(camera_name, alert_type, alert_entry, comparison_image_url, confidence_info, is_test)
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
                
                # Log alert creation
                if confidence_info:
                    logger.info(
                        f"{'Test ' if is_test else ''}Alert sent: {alert_type} from {camera_name} "
                        f"with {confidence_info.get('owl_confidence', 0.0):.1f}% confidence "
                        f"({confidence_info.get('consecutive_owl_frames', 0)} consecutive frames)"
                    )
                else:
                    logger.info(f"{'Test ' if is_test else ''}Alert sent: {alert_type} from {camera_name}")

                return True
            else:
                logger.error(f"Failed to create alert entry for {alert_type}")
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

    def determine_alert_type(self, camera_name, detection_result):
        """
        Determine the most appropriate alert type based on detection results.
        New in v1.1.0 to handle multiple owls and other complex scenarios.
        
        Args:
            camera_name (str): Name of the camera 
            detection_result (dict): Detection results with all metrics
            
        Returns:
            str: The appropriate alert type
        """
        try:
            # Get base alert type from camera mapping
            base_alert_type = detection_result.get("status")
            
            # Check for multiple owls (if the field exists)
            multiple_owls = detection_result.get("multiple_owls", False)
            owl_count = detection_result.get("owl_count", 1)
            
            # Override with multiple owl alert types if applicable
            if multiple_owls or owl_count > 1:
                if base_alert_type == "Owl In Box":
                    return "Two Owls In Box"
                else:
                    return "Two Owls"
                    
            # Check for eggs or babies (future enhancement)
            if detection_result.get("eggs_or_babies", False):
                return "Eggs Or Babies"
                
            # Default to the original alert type if no special conditions
            return base_alert_type
            
        except Exception as e:
            logger.error(f"Error determining alert type: {e}")
            # Fall back to standard alert type
            return detection_result.get("status", "Unknown")

    def process_detection(self, camera_name, detection_result, activity_log_id=None, is_test=False):
        """
        Process detection results and send alerts based on hierarchy, cooldown, and confidence.
        
        Args:
            camera_name (str): Name of the camera that triggered the detection
            detection_result (dict): Dictionary containing detection results
            activity_log_id (int, optional): ID of the corresponding owl_activity_log entry
            is_test (bool, optional): Whether this is a test alert that should bypass confidence checks

        Returns:
            bool: True if an alert was sent, False otherwise
        """
        # Refresh alert settings from environment variables
        self.alerts_enabled = {
            'email': os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true',
            'text': os.environ.get('OWL_TEXT_ALERTS', 'True').lower() == 'true',
            'email_to_text': os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() == 'true'
        }
        
        # If all alert types are disabled, log and return early
        if not any(self.alerts_enabled.values()):
            logger.info("All alert types are disabled, skipping alert processing")
            return False
        
        alert_sent = False
        
        # Determine alert type - New in v1.1.0 to check for multiple owls
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
            
        # Get image URL if available - New in v1.1.0
        comparison_image_url = detection_result.get("comparison_image_url")
            
        # Extract confidence information
        confidence_info = {
            "owl_confidence": detection_result.get("owl_confidence", 0.0),
            "consecutive_owl_frames": detection_result.get("consecutive_owl_frames", 0),
            "confidence_factors": detection_result.get("confidence_factors", {})
        }
        
        # Get priority for hierarchy checks
        priority = self.ALERT_HIERARCHY.get(alert_type, 0)
        
        # Check confidence requirements - bypass for test alerts
        if not is_test and not self._check_confidence_requirements(detection_result, camera_name):
            logger.info(f"Alert blocked - Confidence requirements not met for {camera_name}")
            return False

        # Check alert hierarchy - bypass for test alerts
        if not is_test and self._check_alert_hierarchy(alert_type, priority):
            logger.info(f"Alert {alert_type} suppressed by higher priority alert")
            return False

        # Determine which alert to send based on hierarchy or if it's a test
        if is_test:
            # For tests, just send the alert directly
            alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                         comparison_image_url, confidence_info, is_test=True)
        elif alert_type in ["Eggs Or Babies", "Two Owls In Box"]:
            # Highest priority alerts - always send
            alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                         comparison_image_url, confidence_info)
        elif alert_type == "Two Owls":
            # Only suppressed by eggs/babies or owls in box
            if not self._is_higher_alert_active("Eggs Or Babies") and not self._is_higher_alert_active("Two Owls In Box"):
                alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                             comparison_image_url, confidence_info)
        elif alert_type == "Owl In Box":
            # Suppressed by any multiple owl alert or eggs/babies
            if (not self._is_higher_alert_active("Eggs Or Babies") and 
                not self._is_higher_alert_active("Two Owls In Box") and 
                not self._is_higher_alert_active("Two Owls")):
                alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                             comparison_image_url, confidence_info)
        elif alert_type == "Owl On Box":
            # Suppressed by box, multiple owls, or eggs/babies 
            if (not self._is_higher_alert_active("Eggs Or Babies") and 
                not self._is_higher_alert_active("Two Owls In Box") and 
                not self._is_higher_alert_active("Two Owls") and
                not self._is_higher_alert_active("Owl In Box")):
                alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                             comparison_image_url, confidence_info)
        elif alert_type == "Owl In Area":
            # Lowest priority - suppressed by all others
            if (not self._is_higher_alert_active("Eggs Or Babies") and 
                not self._is_higher_alert_active("Two Owls In Box") and 
                not self._is_higher_alert_active("Two Owls") and
                not self._is_higher_alert_active("Owl In Box") and
                not self._is_higher_alert_active("Owl On Box")):
                alert_sent = self._send_alert(camera_name, alert_type, activity_log_id, 
                                             comparison_image_url, confidence_info)

        return alert_sent

    def update_alert_durations(self):
        """
        Update the duration tracking for active alerts.
        New in v1.1.0 to support after action reports.
        
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
        New in v1.1.0 to support after action reports.
        
        Called after generating an after action report or when starting a new session.
        """
        self.alert_counts = {alert_type: 0 for alert_type in self.ALERT_HIERARCHY}
        self.alert_durations = {alert_type: timedelta(0) for alert_type in self.ALERT_HIERARCHY}
        self.alert_start_times = {alert_type: None for alert_type in self.ALERT_HIERARCHY}
        self.last_after_action_report = datetime.now(pytz.utc)

    def get_alert_statistics(self):
        """
        Get all alert statistics for after action report.
        New in v1.1.0 to support after action reports.
        
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
            "alert_counts": self.alert_counts.copy()
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
            },
            "comparison_image_url": "https://example.com/image.jpg"  # Test URL
        }

        # Process test detection
        result = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection,
            activity_log_id=1  # Test ID
        )

        logger.info(f"Test detection processed: Alert sent = {result}")
        
        # Test with multiple owls
        test_detection_multiple = {
            "status": "Owl In Box",
            "motion_detected": True,
            "is_owl_present": True,
            "multiple_owls": True,  # Two owls detected!
            "owl_confidence": 90.5,
            "consecutive_owl_frames": 4,
            "confidence_factors": {
                "shape_confidence": 40.0,
                "motion_confidence": 35.5,
                "temporal_confidence": 15.0,
                "camera_confidence": 5.0
            }
        }
        
        result_multiple = alert_manager.process_detection(
            camera_name="Test Camera",
            detection_result=test_detection_multiple,
            activity_log_id=2
        )
        
        logger.info(f"Multiple owl test: Alert sent = {result_multiple}")
        logger.info("Alert manager test complete")

    except Exception as e:
        logger.error(f"Alert manager test failed: {e}")
        raise