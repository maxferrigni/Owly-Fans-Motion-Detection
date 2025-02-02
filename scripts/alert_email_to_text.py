# File: alert_email_to_text.py
# Purpose: Convert email alerts to SMS via email-to-SMS gateways as backup notification method

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import time

# Import utilities
from utilities.logging_utils import get_logger
from push_to_supabase import get_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Email credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Carrier gateway mappings
SMS_GATEWAYS = {
    'verizon': 'vtext.com',
    'att': 'txt.att.net',
    'sprint': 'messaging.sprintpcs.com',
    'tmobile': 'tmomail.net'
}

def send_email_to_text(camera_name, alert_type, retry_primary=True):
    """
    Send text messages via email-to-SMS gateway as backup method.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
        retry_primary (bool): Whether to retry primary SMS method first
    """
    try:
        # Format the message
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            message = "Owl Alert: Motion detected in Upper Patio"
        else:
            message = f"Owl Alert: {alert_type} at {camera_name}"

        # Get SMS subscribers
        subscribers = get_subscribers(
            notification_type="sms",
            owl_location=alert_type.lower().replace(" ", "_")
        )

        if not subscribers:
            logger.warning("No SMS subscribers found for backup notifications")
            return

        logger.info(f"Sending backup SMS alerts to {len(subscribers)} subscribers")

        for subscriber in subscribers:
            phone = subscriber.get('phone')
            carrier = subscriber.get('preferences', {}).get('carrier', '').lower()
            
            if not phone or not carrier:
                logger.warning(f"Missing phone or carrier for subscriber: {subscriber.get('name', 'Unknown')}")
                continue

            if carrier not in SMS_GATEWAYS:
                logger.warning(f"Unsupported carrier '{carrier}' for subscriber: {subscriber.get('name', 'Unknown')}")
                continue

            send_single_email_to_text(message, phone, carrier, subscriber.get('name'))
            time.sleep(1)  # Rate limiting

    except Exception as e:
        logger.error(f"Error sending backup SMS alerts: {e}")

def send_single_email_to_text(message, phone_number, carrier, recipient_name=None):
    """
    Send a single text message via email-to-SMS gateway.
    
    Args:
        message (str): Message content
        phone_number (str): Recipient's phone number
        carrier (str): Recipient's cellular carrier
        recipient_name (str, optional): Recipient's name for personalization
    """
    try:
        if not EMAIL_PASSWORD:
            logger.error("Email password not found in environment variables")
            return

        # Clean phone number
        phone_clean = ''.join(filter(str.isdigit, phone_number))
        if len(phone_clean) != 10:
            logger.error(f"Invalid phone number format: {phone_number}")
            return

        # Get carrier gateway
        if carrier not in SMS_GATEWAYS:
            logger.error(f"Unsupported carrier: {carrier}")
            return
        
        gateway = SMS_GATEWAYS[carrier]

        # Create email address for SMS gateway
        to_email = f"{phone_clean}@{gateway}"

        # Personalize message if name available
        if recipient_name:
            message = f"Hi {recipient_name}, {message}"

        # Truncate message if too long
        if len(message) > 160:
            message = message[:157] + "..."

        # Set up email server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()

        try:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            # Create message
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = "Owl Alert"
            msg.attach(MIMEText(message, "plain"))

            # Send message
            server.send_message(msg)
            logger.info(f"Backup SMS sent successfully via {carrier} to {phone_number}")

        except Exception as e:
            logger.error(f"Failed to send backup SMS via {carrier} to {phone_number}: {e}")

        finally:
            server.quit()

    except Exception as e:
        logger.error(f"Error in backup SMS process: {e}")

if __name__ == "__main__":
    # Test backup SMS functionality
    try:
        logger.info("Testing backup SMS system...")
        send_email_to_text("Upper Patio Camera", "Owl In Area", retry_primary=False)
        logger.info("Backup SMS test complete")
    except Exception as e:
        logger.error(f"Backup SMS test failed: {e}")