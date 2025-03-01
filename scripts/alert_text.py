# File: alert_text.py
# Purpose: Handle SMS text message alerts for the owl monitoring system

import os
from twilio.rest import Client
from dotenv import load_dotenv
import time

# Import utilities
from utilities.logging_utils import get_logger

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

# Initialize Twilio client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Twilio client: {e}")
    raise

def send_text_alert(camera_name, alert_type, is_test=False, test_prefix=""):
    """
    Send SMS alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test messages (default "TEST: ")
    """
    try:
        # Check if text alerts are enabled
        if os.environ.get('OWL_TEXT_ALERTS', 'True').lower() != 'true':
            logger.info("Text alerts are disabled, skipping")
            return

        # If no test_prefix was provided but is_test is True, use default
        if is_test and not test_prefix:
            test_prefix = "TEST: "

        # Determine the message based on camera name and alert type
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            message = (f"{test_prefix}Motion has been detected in the Upper Patio area. "
                       "Please check the camera feed at www.owly-fans.com")
        elif camera_name == "Bindy Patio Camera" and alert_type == "Owl On Box":
            message = (f"{test_prefix}Motion has been detected on the Owl Box. "
                       "Please check the camera feed at www.owly-fans.com")
        elif camera_name == "Wyze Internal Camera" and alert_type == "Owl In Box":
            message = (f"{test_prefix}Motion has been detected in the Owl Box. "
                       "Please check the camera feed at www.owly-fans.com")
        else:
            message = f"{test_prefix}Motion has been detected by {camera_name}! Check www.owly-fans.com"

        # Get SMS subscribers
        subscribers = get_subscribers(notification_type="sms", owl_location=alert_type)

        logger.info(f"Sending{'test' if is_test else ''} SMS alerts to {len(subscribers)} subscribers")

        # Send to each subscriber
        for subscriber in subscribers:
            try:
                # Create and send the SMS message
                message_obj = twilio_client.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=subscriber['phone']
                )

                logger.info(f"{'Test' if is_test else ''} Text alert sent to {subscriber['phone']}: {message_obj.sid}")

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
        return True  # Assuming US numbers (10 digits starting with 1)
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
        
        # Test case 1: Standard Owl In Box alert
        send_text_alert("Wyze Internal Camera", "Owl In Box")
        time.sleep(2)  # Wait between tests
        
        # Test case 2: Test Owl In Area alert
        send_text_alert("Upper Patio Camera", "Owl In Area", is_test=True)
        
        logger.info("SMS test complete")
        
    except Exception as e:
        logger.error(f"SMS test failed: {e}")
        raise