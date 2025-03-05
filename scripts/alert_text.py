# File: alert_text.py
# Purpose: Handle SMS text message alerts for the owl monitoring system
#
# March 4, 2025 Update - Version 1.1.0
# - Added support for multiple owl detection scenarios
# - Updated to include image URLs in text messages
# - Enhanced alert messaging based on priority system

import os
import time
from dotenv import load_dotenv

# Try to import Twilio, but continue if not available
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("WARNING: Twilio package not installed. SMS alerts will be disabled.")


# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES

# Corrected import: from database_utils
from utilities.database_utils import get_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Validate Twilio credentials
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    error_msg = "Twilio credentials missing. Check environment variables."
    logger.error(error_msg)
    raise ValueError(error_msg)

# Initialize Twilio client if available
twilio_client = None
if TWILIO_AVAILABLE:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        TWILIO_AVAILABLE = False
else:
    logger.warning("Twilio package not installed. SMS alerts will be disabled.")

def send_text_alert(camera_name, alert_type, is_test=False, test_prefix="", image_url=None):
    """
    Send SMS alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
        image_url (str, optional): URL to the comparison image (added in v1.1.0)
    """
    try:
        # Check if text alerts are enabled
        if os.environ.get('OWL_TEXT_ALERTS', 'True').lower() != 'true':
            logger.info("Text alerts are disabled, skipping")
            return
            
        # Check if Twilio is available
        if not TWILIO_AVAILABLE or not twilio_client:
            logger.warning("Twilio not available. SMS alerts disabled.")
            return

        # Get priority level for better logging
        priority_level = ALERT_PRIORITIES.get(alert_type, 1)

        # Determine the message based on camera name and alert type
        # Enhanced in v1.1.0 to support multiple owl detection scenarios
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            message = (f"{test_prefix}Motion has been detected in the Upper Patio area. "
                       "Please check the camera feed at www.owly-fans.com")
        elif camera_name == "Bindy Patio Camera" and alert_type == "Owl On Box":
            message = (f"{test_prefix}Motion has been detected on the Owl Box. "
                       "Please check the camera feed at www.owly-fans.com")
        elif camera_name == "Wyze Internal Camera" and alert_type == "Owl In Box":
            message = (f"{test_prefix}Motion has been detected in the Owl Box. "
                       "Please check the camera feed at www.owly-fans.com")
        elif alert_type == "Two Owls":
            message = (f"{test_prefix}Two owls have been detected in the area! "
                      "Please check the camera feed at www.owly-fans.com")
        elif alert_type == "Two Owls In Box":
            message = (f"{test_prefix}Two owls have been detected in the box! "
                      "Please check the camera feed at www.owly-fans.com")
        elif alert_type == "Eggs Or Babies":
            message = (f"{test_prefix}Eggs or babies may have been detected in the box! "
                      "Please check the camera feed at www.owly-fans.com")
        else:
            message = f"{test_prefix}Motion has been detected by {camera_name}! Check www.owly-fans.com"

        # Add image URL if provided - New in v1.1.0
        if image_url:
            message += f"\nView image: {image_url}"

        # Get SMS subscribers
        subscribers = get_subscribers(notification_type="sms", owl_location=alert_type)

        logger.info(f"Sending {'test ' if is_test else ''}SMS alerts to {len(subscribers)} subscribers")
        logger.info(f"Alert type: {alert_type} (Priority: {priority_level})")

        # Send to each subscriber
        for subscriber in subscribers:
            try:
                # Format phone number for Twilio
                phone_number = subscriber['phone']
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                # Create and send the SMS message
                message_obj = twilio_client.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=phone_number
                )

                logger.info(f"{'Test ' if is_test else ''}Text alert sent to {subscriber['phone']}: {message_obj.sid}")

            except Exception as e:
                logger.error(f"Failed to send text alert to {subscriber['phone']}: {e}")

    except Exception as e:
        logger.error(f"Error sending SMS alerts: {e}")

def is_valid_phone_number(phone_number):
    """
    Check if a phone number is valid.
    
    Args:
        phone_number (str): Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Check length (10 digits for US numbers, 11 digits starting with 1)
    if len(phone_number) == 10:
        return True  # Assuming US numbers (10 digits)
    elif len(phone_number) == 11 and phone_number.startswith('1'):
        return True
    return False

def format_phone_number(phone_number):
    """
    Format phone number for consistent storage.
    
    Args:
        phone_number (str): Phone number to format
        
    Returns:
        str: Formatted phone number or None if invalid
    """
    try:
        # Remove any non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        if not is_valid_phone_number(cleaned):
            logger.warning(f"Invalid phone number format: {phone_number}")
            return None
            
        # Ensure number starts with country code
        if len(cleaned) == 10:
            cleaned = '1' + cleaned
            
        return f"+{cleaned}"
        
    except Exception as e:
        logger.error(f"Error formatting phone number {phone_number}: {e}")
        return None

if __name__ == "__main__":
    # Test SMS functionality
    try:
        logger.info("Testing SMS alert system...")
        
        # Test case 1: Regular alert with image URL
        test_image_url = "https://project-dev-123.supabase.co/storage/v1/object/public/owl_detections/owl_in_box/test_image.jpg"
        send_text_alert("Wyze Internal Camera", "Owl In Box", image_url=test_image_url)
        time.sleep(2)  # Wait between tests
        
        # Test case 2: Test alert with prefix
        send_text_alert("Upper Patio Camera", "Owl In Area", is_test=True, test_prefix="TEST: ")
        
        # Test case 3: Multiple owl alert
        send_text_alert("Wyze Internal Camera", "Two Owls In Box", is_test=True, test_prefix="TEST: ")
        
        logger.info("SMS test complete")
        
    except Exception as e:
        logger.error(f"SMS test failed: {e}")
        raise