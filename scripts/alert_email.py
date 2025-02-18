# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
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

def send_email_alert(camera_name, alert_type):
    """
    Send email alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
    """
    try:
        # Determine the subject and body based on camera name and alert type
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            subject = "ALERT: Owl In The Area"
            body = ("Motion has been detected in the Upper Patio area. "
                   "Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.")
        else:
            subject = f"ALERT: {alert_type}"
            body = (f"Motion has been detected at {camera_name}. "
                   f"Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.")

        # Get subscribers who want email notifications for this alert type
        subscribers = get_subscribers()

        if subscribers:
            logger.info(f"Sending email alerts to {len(subscribers)} subscribers")
            for subscriber in subscribers:
                send_single_email(subject, body, subscriber['email'], subscriber['name'])
        else:
            logger.warning("No email subscribers found for this alert type")

    except Exception as e:
        logger.error(f"Error sending email alerts: {e}")

def send_single_email(subject, body, to_email, recipient_name=None):
    """
    Send a single email to a recipient.
    
    Args:
        subject (str): Email subject
        body (str): Email body (HTML)
        to_email (str): Recipient's email address
        recipient_name (str, optional): Recipient's name for personalization
    """
    try:
        # Set up the email server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        
        try:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        except smtplib.SMTPAuthenticationError as auth_error:
            logger.error(f"Email authentication failed: {auth_error}")
            return
            
        try:
            # Create the email
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = subject

            # Personalize greeting if name is available
            greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"

            # HTML email body with personalized greeting
            html_body = f"""
            <html>
                <body>
                    <p>{greeting}</p>
                    <p>{body}</p>
                    <p>Best regards,<br>Owly Fans Monitoring System</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(html_body, "html"))

            # Send the email
            server.send_message(msg)
            logger.info(f"Email alert sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            
        finally:
            # Always close the connection
            server.quit()

    except smtplib.SMTPConnectError as e:
        logger.error(f"Connection error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}")

if __name__ == "__main__":
    # Test email functionality
    try:
        logger.info("Testing email alert system...")
        send_email_alert("Upper Patio Camera", "Owl In Area")
        logger.info("Email test complete")
    except Exception as e:
        logger.error(f"Email test failed: {e}")