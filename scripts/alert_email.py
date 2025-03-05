# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system
#
# March 5, 2025 Update - Version 1.2.0
# - Added alert ID to email subject and body for tracking
# - Streamlined error handling
# - Updated templates for improved readability

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES

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

def send_email_alert(camera_name, alert_type, is_test=False, test_prefix="", image_url=None, alert_id=None):
    """
    Send email alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
        image_url (str, optional): URL to the comparison image
        alert_id (str, optional): Unique ID for the alert for tracking
    """
    # Check if email alerts are enabled
    if os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() != 'true':
        logger.info("Email alerts are disabled, skipping")
        return
        
    # Determine the subject and body based on camera name and alert type
    # Add test prefix to subject if this is a test
    priority_level = ALERT_PRIORITIES.get(alert_type, 0)
    
    # Subjects by alert type
    subjects = {
        "Owl In Area": f"{test_prefix}ALERT: Owl In The Area",
        "Owl On Box": f"{test_prefix}ALERT: Owl On The Box",
        "Owl In Box": f"{test_prefix}ALERT: Owl In The Box",
        "Two Owls": f"{test_prefix}PRIORITY ALERT: Two Owls Detected",
        "Two Owls In Box": f"{test_prefix}PRIORITY ALERT: Two Owls In The Box",
        "Eggs Or Babies": f"{test_prefix}URGENT ALERT: Eggs or Babies Detected"
    }
    
    # Message bodies by alert type
    bodies = {
        "Owl In Area": f"{test_prefix}Motion has been detected in the Upper Patio area.",
        "Owl On Box": f"{test_prefix}Motion has been detected on the Owl Box.",
        "Owl In Box": f"{test_prefix}Motion has been detected in the Owl Box.",
        "Two Owls": f"{test_prefix}Two owls have been detected! This is a higher priority alert.",
        "Two Owls In Box": f"{test_prefix}Two owls have been detected in the box! This is a higher priority alert.",
        "Eggs Or Babies": f"{test_prefix}Eggs or babies may have been detected in the box! This is our highest priority alert."
    }
    
    # Get subject and body for this alert type
    subject = subjects.get(alert_type, f"{test_prefix}ALERT: Owl Motion Detected")
    body = bodies.get(alert_type, f"{test_prefix}Motion has been detected by {camera_name}!")
    
    # Add alert ID to subject if provided - NEW in v1.2.0
    if alert_id:
        subject = f"{subject} [ID: {alert_id}]"
    
    # Ensure URL is valid and complete
    if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
        image_url = f"https://{image_url}"

    # Get email subscribers
    subscribers = get_subscribers(notification_type="email", owl_location=alert_type)
    if not subscribers:
        logger.info(f"No subscribers found for {alert_type}")
        return
        
    logger.info(f"Sending {'test ' if is_test else ''}email alerts to {len(subscribers)} subscribers")
    
    try:
        # Send to each subscriber
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            for subscriber in subscribers:
                to_email = subscriber.get('email')
                if not to_email:
                    continue

                recipient_name = subscriber.get('name')

                # Create the email message
                msg = MIMEMultipart()
                msg["From"] = EMAIL_ADDRESS
                msg["To"] = to_email
                msg["Subject"] = subject

                # Personalize greeting if name is available
                greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"

                # HTML email body with personalized greeting, image, and alert ID
                html_content = f"""
                <html>
                    <body>
                        <p>{greeting}</p>
                        <p>{body}</p>
                        <p>Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.</p>
                """
                
                # Add image if URL provided
                if image_url:
                    html_content += f"""
                        <p><strong>Detection Image:</strong></p>
                        <p><a href='{image_url}'><img src='{image_url}' 
                            alt='Detection Image' style='max-width: 600px; max-height: 400px;' /></a></p>
                        <p><small>If the image doesn't display, <a href='{image_url}'>click here</a> to view it.</small></p>
                    """
                
                # Add priority level indicator
                if priority_level >= 4:  # Multiple owls or eggs/babies
                    html_content += f"""
                        <p style="color: red; font-weight: bold;">
                            This is a high priority alert! (Priority Level: {priority_level}/6)
                        </p>
                    """
                
                # Add alert ID to footer if provided - NEW in v1.2.0
                if alert_id:
                    html_content += f"""
                        <p style="color: #777; font-size: 0.8em;">Alert ID: {alert_id}</p>
                    """
                
                # Close the HTML
                html_content += """
                        <p>Best regards,<br>Owly Fans Monitoring System</p>
                    </body>
                </html>
                """
                
                msg.attach(MIMEText(html_content, "html"))

                # Send the email
                server.send_message(msg)
                logger.info(f"{'Test ' if is_test else ''}Email alert sent to {to_email}")
    except Exception as e:
        logger.error(f"Error sending email alerts: {e}")

def send_test_email(to_email, subject, body, alert_id=None):
    """
    Send a test email for debugging purposes.
    
    Args:
        to_email (str): Email address to send to
        subject (str): Email subject
        body (str): Email body content
        alert_id (str, optional): Add alert ID to email for testing tracking
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Add alert ID to subject if provided
        if alert_id:
            subject = f"{subject} [ID: {alert_id}]"
            
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # If alert ID provided, add it to the HTML body
            if alert_id:
                body += f"<p style='color: #777; font-size: 0.8em;'>Alert ID: {alert_id}</p>"
                
            msg.attach(MIMEText(body, "html"))
            
            server.send_message(msg)
            logger.info(f"Test email sent successfully to {to_email}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to send test email: {e}")
        return False

if __name__ == "__main__":
    # Test email functionality with alert IDs
    logger.info("Testing email alert system with alert IDs...")
    
    # Generate a test alert ID
    import random
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    random_suffix = ''.join(random.choices('0123456789ABCDEF', k=3))
    test_alert_id = f"OWL-{timestamp}-{random_suffix}"
    
    # Test with image URL and alert ID
    test_image_url = "https://project-dev-123.supabase.co/storage/v1/object/public/owl_detections/owl_in_box/test_image.jpg"
    
    # Test standard alert with ID
    send_email_alert(
        "Wyze Internal Camera", 
        "Owl In Box", 
        is_test=True, 
        test_prefix="TEST: ",
        image_url=test_image_url,
        alert_id=test_alert_id
    )
    
    # Test direct email with ID
    test_email = os.getenv("TEST_EMAIL", "maxferrigni@gmail.com")
    send_test_email(
        test_email,
        "Email Alert System Test with Alert ID",
        """
        <html>
            <body>
                <h2>Email Alerting System Test</h2>
                <p>This is a test of the email alert system for the Owl Monitoring App v1.2.0.</p>
                <p>This test includes a unique alert ID for tracking.</p>
                <p>If you're seeing this, the system is working properly.</p>
            </body>
        </html>
        """,
        alert_id=test_alert_id
    )
    
    logger.info(f"Email tests completed with alert ID: {test_alert_id}")