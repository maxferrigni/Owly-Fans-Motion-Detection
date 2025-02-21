# File: alert_email_to_text.py
# Purpose: Handle SMS alerts via email-to-text gateways

import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from push_to_supabase import get_subscribers

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
    "sprint": "messaging.sprintpcs.com"
}

def send_text_via_email(phone_number, carrier, message, recipient_name=None):
    """
    Send SMS via email-to-text gateway.
    
    Args:
        phone_number (str): Recipient's phone number
        carrier (str): Carrier name (lowercase)
        message (str): Message content
        recipient_name (str, optional): Recipient's name for personalization
    """
    try:
        if carrier not in CARRIER_EMAIL_GATEWAYS:
            logger.error(f"Unsupported carrier: {carrier}")
            return False

        # Clean phone number (remove any non-digits)
        clean_number = ''.join(filter(str.isdigit, phone_number))
        if not clean_number:
            logger.error(f"Invalid phone number format: {phone_number}")
            return False

        # Construct email address for SMS gateway
        gateway = CARRIER_EMAIL_GATEWAYS[carrier]
        to_email = f"{clean_number}@{gateway}"

        # Set up the email server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        
        try:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = "Owl Alert"  # Keep subject short for SMS

            # Personalize message if name provided
            if recipient_name:
                message = f"Hi {recipient_name}, {message}"

            msg.attach(MIMEText(message, "plain"))

            # Send the message
            server.send_message(msg)
            logger.info(f"Text alert sent via email gateway to {phone_number} ({carrier})")
            return True

        except Exception as e:
            logger.error(f"Failed to send text via email to {phone_number}: {e}")
            return False
            
        finally:
            server.quit()

    except Exception as e:
        logger.error(f"Error in send_text_via_email: {e}")
        return False

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
        
        # Test subscribers from database
        subscribers = get_subscribers(notification_type="sms")
        if subscribers:
            test_sub = subscribers[0]
            send_text_via_email(
                test_sub['phone'],
                test_sub['carrier'].lower(),
                "This is a test alert from Owl Monitor system.",
                test_sub.get('name')
            )
            logger.info("Email-to-text test complete")
        else:
            logger.warning("No test subscribers found")
            
    except Exception as e:
        logger.error(f"Email-to-text test failed: {e}")
        raise