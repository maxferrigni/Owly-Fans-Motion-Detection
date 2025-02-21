# File: alert_text.py
# Purpose: Handle SMS text message alerts for the owl monitoring system

import os
from twilio.rest import Client
from dotenv import load_dotenv
import time

# Import utilities
from utilities.logging_utils import get_logger
from push_to_supabase import get_subscribers

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

def send_text_alert(camera_name, alert_type):
    """
    Send SMS alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
    """
    try:
        # Get subscribers who want SMS notifications for this alert type
        subscribers = get_subscribers(
            notification_type="sms",
            owl_location=alert_type.lower().replace(" ", "_")
        )

        if not subscribers:
            logger.warning("No SMS subscribers found for this alert type")
            return

        # Create message based on alert type
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            message = "ALERT: Owl detected in the Upper Patio area! Check www.owly-fans.com"
        else:
            message = f"ALERT: {alert_type} detected at {camera_name}! Check www.owly-fans.com"

        logger.info(f"Sending SMS alerts to {len(subscribers)} subscribers")
        
        # Send to each subscriber with rate limiting
        for subscriber in subscribers:
            if subscriber.get('phone'):
                send_single_text(message, subscriber['phone'], subscriber['name'])
                time.sleep(1)  # Rate limiting between messages
            else:
                logger.warning(f"No phone number for subscriber: {subscriber.get('name', 'Unknown')}")

    except Exception as e:
        logger.error(f"Error sending SMS alerts: {e}")

def send_single_text(message, phone_number, recipient_name=None):
    """
    Send a single SMS message to a recipient.
    
    Args:
        message (str): Message content
        phone_number (str): Recipient's phone number
        recipient_name (str, optional): Recipient's name for personalization
    """
    try:
        # Validate phone number format
        if not is_valid_phone_number(phone_number):
            logger.error(f"Invalid phone number format: {phone_number}")
            return

        # Format phone number consistently
        formatted_phone = format_phone_number(phone_number)
        if not formatted_phone:
            logger.error(f"Could not format phone number: {phone_number}")
            return

        # Personalize message if name is available
        if recipient_name:
            message = f"Hi {recipient_name}, {message}"

        # Send message via Twilio
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=formatted_phone
        )
        logger.info(f"SMS sent successfully to {formatted_phone}")

    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {e}")

def is_valid_phone_number(phone_number):
    """
    Validate phone number format.
    
    Args:
        phone_number (str): Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Remove any non-numeric characters
    cleaned = ''.join(filter(str.isdigit, phone_number))
    
    # Check if it's a valid US number (10 digits)
    if len(cleaned) == 10:
        return True
    # Check if it's a valid US number with country code (11 digits starting with 1)
    elif len(cleaned) == 11 and cleaned.startswith('1'):
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
        
        # Test case 1: Owl In Box alert
        send_text_alert("Wyze Internal Camera", "Owl In Box")
        time.sleep(2)  # Wait between tests
        
        # Test case 2: Owl In Area alert
        send_text_alert("Upper Patio Camera", "Owl In Area")
        
        logger.info("SMS tests complete")
    except Exception as e:
        logger.error(f"SMS test failed: {e}")
        raise