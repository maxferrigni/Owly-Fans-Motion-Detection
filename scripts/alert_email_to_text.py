# File: alert_email_to_text.py
# Purpose: Handle SMS alerts via email-to-text gateways
#
# March 4, 2025 Update - Version 1.1.0
# - Added support for multiple owl detection scenarios
# - Enhanced alert messaging based on priority system
# - Added comparison image URL support
# - Updated carrier gateways with latest domains

import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES

# Corrected import: from database_utils
from utilities.database_utils import get_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Email credentials from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Google App Password

if not EMAIL_PASSWORD:
    error_msg = "Email password not found in environment variables"
    logger.error(error_msg)
    raise ValueError(error_msg)

# Carrier gateway mappings
CARRIER_EMAIL_GATEWAYS = {
    "verizon": "vtext.com",
    "att": "txt.att.net",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "boost": "myboostmobile.com",
    "cricket": "sms.mycricket.com",
    "metro": "mymetropcs.com",
    "googlefi": "msg.fi.google.com",
    "spectrum": "messaging.spectrum.com",  # Updated domain
    "charter": "charter.net",              # Keep original as an option
    "xfinity": "xfinity.mobile.com"        # Added in v1.1.0
}

def send_text_via_email(phone_number, carrier, message, recipient_name=None):
    """
    Send SMS via email-to-text gateway.
    
    Args:
        phone_number (str): Phone number to send to
        carrier (str): Cell phone carrier (lowercase)
        message (str): Text message to send
        recipient_name (str, optional): Recipient's name for personalization
    """
    try:
        # Check if email-to-text alerts are enabled
        if os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() != 'true':
            logger.info("Email-to-text alerts are disabled, skipping")
            return

        # Check if carrier is supported
        if carrier not in CARRIER_EMAIL_GATEWAYS:
            logger.error(f"Unsupported carrier: {carrier}")
            return

        # Format phone number - remove any '+' or country code prefix for most carriers
        if phone_number.startswith('+'):
            # Remove '+' and country code (usually '1' for US numbers)
            if len(phone_number) > 10 and phone_number.startswith('+1'):
                phone_number = phone_number[2:]  # Remove '+1'
            else:
                phone_number = phone_number[1:]  # Just remove '+'

        # Ensure the number has exactly 10 digits for US carriers
        if len(phone_number) > 10:
            phone_number = phone_number[-10:]  # Take last 10 digits

        # Construct the email address for the gateway
        to_email = f"{phone_number}@{CARRIER_EMAIL_GATEWAYS[carrier]}"

        # Create and send the email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = ""  # No subject for SMS

            # Personalize message if name is available
            if recipient_name:
                message = f"Dear {recipient_name},\n\n{message}"

            msg.attach(MIMEText(message, "plain"))
            server.send_message(msg)

            logger.info(f"Text alert sent via email gateway to {to_email}")

    except Exception as e:
        logger.error(f"Error sending text alert to {phone_number} ({carrier}): {e}")

def send_text_alert(camera_name, alert_type, is_test=False, test_prefix="", image_url=None):
    """
    Send SMS alerts via email-to-text gateway based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
        image_url (str, optional): URL to the comparison image (added in v1.1.0)
    """
    try:
        # Check if email-to-text alerts are enabled
        if os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() != 'true':
            logger.info("Email-to-text alerts are disabled, skipping")
            return

        # Get priority level for logging
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
        subscribers = get_subscribers(notification_type="email_to_text", owl_location=alert_type)
        if not subscribers:
            # Fall back to standard SMS subscribers if no specific email-to-text ones
            subscribers = get_subscribers(notification_type="sms", owl_location=alert_type)

        logger.info(f"Sending {'test ' if is_test else ''}email-to-text alerts to {len(subscribers)} subscribers")
        logger.info(f"Alert type: {alert_type} (Priority: {priority_level})")
        
        # Send to each subscriber
        for subscriber in subscribers:
            if subscriber.get('phone') and subscriber.get('carrier'):
                send_text_via_email(
                    subscriber['phone'],
                    subscriber['carrier'].lower(),
                    message,
                    subscriber.get('name')
                )
            else:
                logger.warning(
                    f"Missing phone or carrier for subscriber: {subscriber.get('name', 'Unknown')}"
                )

    except Exception as e:
        logger.error(f"Error sending SMS alerts: {e}")

if __name__ == "__main__":
    # Test the functionality
    try:
        logger.info("Testing email-to-text alert system...")
        
        # Test regular alert with image URL
        test_image_url = "https://project-dev-123.supabase.co/storage/v1/object/public/owl_detections/owl_in_box/test_image.jpg"
        send_text_alert("Wyze Internal Camera", "Owl In Box", image_url=test_image_url)
        
        # Test with test prefix
        send_text_alert("Upper Patio Camera", "Owl In Area", is_test=True, test_prefix="TEST: ")
        
        # Test multiple owl alert
        send_text_alert("Wyze Internal Camera", "Two Owls In Box", is_test=True, test_prefix="TEST: ")
        
        logger.info("Email-to-text test complete")
        
    except Exception as e:
        logger.error(f"Email-to-text test failed: {e}")
        raise