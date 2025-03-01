# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger

# Import from database_utils
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

def send_email_alert(camera_name, alert_type, is_test=False, test_prefix=""):
    """
    Send email alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area")
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
    """
    try:
        # Check if email alerts are enabled
        if os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() != 'true':
            logger.info("Email alerts are disabled, skipping")
            return
            
        # Determine the subject and body based on camera name and alert type
        # Add test prefix to subject if this is a test
        if camera_name == "Upper Patio Camera" and alert_type == "Owl In Area":
            subject = f"{test_prefix}ALERT: Owl In The Area"
            body = (f"{test_prefix}Motion has been detected in the Upper Patio area. "
                   "Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.")
        elif camera_name == "Bindy Patio Camera" and alert_type == "Owl On Box":
            subject = f"{test_prefix}ALERT: Owl On The Box"
            body = (f"{test_prefix}Motion has been detected on the Owl Box. "
                   "Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.")
        elif camera_name == "Wyze Internal Camera" and alert_type == "Owl In Box":
            subject = f"{test_prefix}ALERT: Owl In The Box"
            body = (f"{test_prefix}Motion has been detected in the Owl Box. "
                   "Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.")
        else:
            subject = f"{test_prefix}ALERT: Owl Motion Detected"
            body = f"{test_prefix}Motion has been detected by {camera_name}! Check www.owly-fans.com"

        # Get email subscribers
        subscribers = get_subscribers(notification_type="email", owl_location=alert_type)

        logger.info(f"Sending {'test ' if is_test else ''}email alerts to {len(subscribers)} subscribers")
        
        # Send to each subscriber
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            for subscriber in subscribers:
                try:
                    to_email = subscriber.get('email')
                    if not to_email:
                        logger.warning(f"Missing email for subscriber: {subscriber.get('name', 'Unknown')}")
                        continue

                    recipient_name = subscriber.get('name')

                    # Create the email message
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
                    logger.info(f"{'Test ' if is_test else ''}Email alert sent successfully to {to_email}")

                except Exception as e:
                    logger.error(f"Failed to send email to {to_email}: {e}")
                    
            # Always close the connection
            server.quit()

    except smtplib.SMTPConnectError as e:
        logger.error(f"Connection error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")

if __name__ == "__main__":
    # Test email functionality
    try:
        logger.info("Testing email alert system...")
        # Test regular alert
        send_email_alert("Upper Patio Camera", "Owl In Area")
        logger.info("Regular email test complete")
        
        # Test with test prefix
        send_email_alert("Upper Patio Camera", "Owl In Area", is_test=True, test_prefix="TEST: ")
        logger.info("Test email alert complete")
    except Exception as e:
        logger.error(f"Email test failed: {e}")