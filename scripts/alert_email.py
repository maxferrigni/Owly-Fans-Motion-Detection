# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system
#
# March 4, 2025 Update - Version 1.1.0
# - Added image URLs to email alerts
# - Enhanced email templates for different alert types
# - Updated to support multiple owl detection scenarios

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

def send_email_alert(camera_name, alert_type, is_test=False, test_prefix="", image_url=None):
    """
    Send email alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
        image_url (str, optional): URL to the comparison image (added in v1.1.0)
    """
    try:
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
        
        # Ensure URL is valid and complete
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
            image_url = f"https://{image_url}"

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

                    # HTML email body with personalized greeting and image
                    html_content = f"""
                    <html>
                        <body>
                            <p>{greeting}</p>
                            <p>{body}</p>
                            <p>Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.</p>
                    """
                    
                    # Add image if URL provided (new in v1.1.0)
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
                    
                    # Close the HTML
                    html_content += """
                            <p>Best regards,<br>Owly Fans Monitoring System</p>
                        </body>
                    </html>
                    """
                    
                    msg.attach(MIMEText(html_content, "html"))

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

def send_test_email(to_email, subject, body):
    """
    Send a test email for debugging purposes.
    
    Args:
        to_email (str): Email address to send to
        subject (str): Email subject
        body (str): Email body
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            msg = MIMEMultipart()
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = to_email
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body, "html"))
            
            server.send_message(msg)
            logger.info(f"Test email sent successfully to {to_email}")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to send test email: {e}")
        return False

def test():
    """Test email functionality with test recipients"""
    print("Testing email alert system...")
    try:
        test_email = os.getenv("TEST_EMAIL", "maxferrigni@gmail.com")
        
        # Test with image URL
        test_image_url = "https://project-dev-123.supabase.co/storage/v1/object/public/owl_detections/owl_in_box/test_image.jpg"
        
        # Test basic alert
        send_email_alert(
            "Wyze Internal Camera", 
            "Owl In Box", 
            is_test=True, 
            test_prefix="TEST: ",
            image_url=test_image_url
        )
        
        # Test multiple owl alert
        send_email_alert(
            "Wyze Internal Camera", 
            "Two Owls In Box", 
            is_test=True, 
            test_prefix="TEST: ",
            image_url=test_image_url
        )
        
        # Test direct email
        send_test_email(
            test_email,
            "Email Alert System Test",
            """
            <html>
                <body>
                    <h2>Email Alerting System Test</h2>
                    <p>This is a test of the email alert system for the Owl Monitoring App v1.1.0.</p>
                    <p>If you're seeing this, the system is working properly.</p>
                </body>
            </html>
            """
        )
        
        print("Email test completed successfully")
        return True
    except Exception as e:
        print(f"Email test failed: {e}")
        return False

if __name__ == "__main__":
    # Test email functionality
    try:
        logger.info("Testing email alert system...")
        # Test regular alert
        send_email_alert("Upper Patio Camera", "Owl In Area", image_url="https://example.com/test.jpg")
        logger.info("Regular email test complete")
        
        # Test with test prefix
        send_email_alert("Upper Patio Camera", "Owl In Area", is_test=True, test_prefix="TEST: ")
        logger.info("Test email alert complete")
        
        # Test new multi-owl alerts
        send_email_alert("Wyze Internal Camera", "Two Owls In Box", is_test=True, test_prefix="TEST: ")
        logger.info("Multiple owl test complete")
    except Exception as e:
        logger.error(f"Email test failed: {e}")