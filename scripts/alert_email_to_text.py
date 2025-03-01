# File: alert_email_to_text.py
# Purpose: Handle SMS alerts via email-to-text gateways

import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger

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
    "spectrum": "messaging.spectrum.com",  # Updated to use spectrum.com domain
    "charter": "charter.net"               # Keep original as fallback
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
        # Check if email-to-text alerts are enabled
        if os.environ.get('OWL_EMAIL_TO_TEXT_ALERTS', 'True').lower() != 'true':
            logger.info("Email-to-text alerts are disabled, skipping")
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
        subscribers = get_subscribers(notification_type="email_to_text", owl_location=alert_type)

        logger.info(f"Sending{'test' if is_test else ''} email-to-text alerts to {len(subscribers)} subscribers")
        
        # Send to each subscriber
        for subscriber in subscribers:
            if subscriber.get('phone') and subscriber.get('carrier'):
                # Format phone number to remove "+" and country code for certain carriers
                phone = subscriber['phone']
                carrier = subscriber['carrier'].lower()
                
                # For Spectrum/Charter, use only the 10-digit number (no + or country code)
                if carrier in ["spectrum", "charter"]:
                    # Remove any non-digit characters and ensure it's 10 digits only
                    phone = ''.join(filter(str.isdigit, phone))
                    if len(phone) == 11 and phone.startswith('1'):
                        phone = phone[1:]  # Remove leading 1 if present
                
                send_text_via_email(
                    phone,
                    carrier,
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
        
        # Test subscribers from database
        subscribers = get_subscribers(notification_type="email_to_text")
        if subscribers:
            test_sub = subscribers[0]  # Use first subscriber for test
            
            # Test standard message
            send_text_via_email(
                test_sub['phone'],
                test_sub['carrier'].lower(),
                "This is a test alert from Owl Monitor system.",
                test_sub.get('name')
            )
            
            # Test with TEST prefix
            send_text_alert(
                "Wyze Internal Camera", 
                "Owl In Box",
                is_test=True,
                test_prefix="TEST: "
            )
            
            logger.info("Email-to-text test complete")
        else:
            logger.warning("No test subscribers found")
            
    except Exception as e:
        logger.error(f"Email-to-text test failed: {e}")
        raise