# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system
#
# March 8, 2025 Update - Version 1.5.4
# - Fixed test email functionality
# - Enhanced error handling and debugging
# - Improved test mode detection and processing
# - Added comprehensive logging throughout the process

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os
import io
import traceback
import time
from datetime import datetime
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
        
    Returns:
        dict: Results of the email sending process including success status and recipient count
    """
    start_time = time.time()
    logger.info(f"Starting email alert process for {alert_type} (Test: {is_test})")
    
    # Track results
    results = {
        "success": False,
        "email_count": 0,
        "errors": []
    }
    
    try:
        # Check if email alerts are enabled
        email_enabled = os.environ.get('OWL_EMAIL_ALERTS', 'True').lower() == 'true'
        if not email_enabled and not is_test:  # Always allow test emails even if alerts disabled
            logger.info("Email alerts are disabled, skipping")
            return results
            
        # Determine the subject and body based on camera name and alert type
        # Add test prefix to subject if this is a test
        priority_level = ALERT_PRIORITIES.get(alert_type, 0)
        
        # Force test_prefix for test alerts
        if is_test and not test_prefix:
            test_prefix = "TEST: "
        
        # Log test status
        if is_test:
            logger.info(f"Processing TEST alert for {alert_type}")
        
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
        
        # Add alert ID to subject if provided
        if alert_id:
            subject = f"{subject} [ID: {alert_id}]"
        
        # Ensure URL is valid and complete
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
            image_url = f"https://{image_url}"

        # Get email subscribers
        subscribers = get_subscribers(notification_type="email", owl_location=alert_type)
        if not subscribers:
            logger.warning(f"No subscribers found for {alert_type}")
            results["errors"].append("No subscribers found")
            return results
            
        # Log the number of subscribers
        subscriber_count = len(subscribers)
        logger.info(f"Found {subscriber_count} subscribers for {alert_type}")
        
        # Track successful email count
        email_count = 0
        
        try:
            # Connect to SMTP server with error handling and retries
            smtp_connected = False
            retry_count = 0
            max_retries = 3
            
            # Try to connect to SMTP with retries
            while not smtp_connected and retry_count < max_retries:
                try:
                    logger.debug(f"Connecting to SMTP server (attempt {retry_count+1})")
                    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
                    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                    smtp_connected = True
                    logger.debug("SMTP connection successful")
                except Exception as e:
                    retry_count += 1
                    error = f"SMTP connection error (attempt {retry_count}): {str(e)}"
                    logger.warning(error)
                    results["errors"].append(error)
                    
                    if retry_count < max_retries:
                        # Wait before retrying (exponential backoff)
                        wait_time = 2 ** retry_count
                        logger.debug(f"Waiting {wait_time} seconds before retry")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"Failed to connect to SMTP server after {max_retries} attempts")

            # If we're connected, send emails to each subscriber
            if smtp_connected:
                for subscriber in subscribers:
                    to_email = subscriber.get('email')
                    if not to_email:
                        continue
                        
                    try:
                        recipient_name = subscriber.get('name', '')
                        
                        # Create personalized message
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
                        
                        # Add alert ID to footer if provided
                        if alert_id:
                            html_content += f"""
                                <p style="color: #777; font-size: 0.8em;">Alert ID: {alert_id}</p>
                            """
                        
                        # Add test indicator for test emails
                        if is_test:
                            html_content += f"""
                                <p style="color: #FF6600; font-size: 0.9em; font-weight: bold;">
                                    This is a TEST alert and can be safely ignored.
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
                        email_count += 1
                        logger.debug(f"Email sent to {to_email}")
                        
                    except Exception as e:
                        error = f"Error sending email to {to_email}: {str(e)}"
                        logger.error(error)
                        results["errors"].append(error)
                
                # Close the server connection
                try:
                    server.quit()
                except Exception as e:
                    logger.warning(f"Error closing SMTP connection: {str(e)}")
                
        except Exception as e:
            error = f"Error in email process: {str(e)}"
            logger.error(error)
            logger.error(traceback.format_exc())
            results["errors"].append(error)
            
        # Update results
        results["email_count"] = email_count
        results["success"] = email_count > 0
        
        # Log completion
        elapsed_time = time.time() - start_time
        logger.info(
            f"{'Test ' if is_test else ''}Email alert process completed in {elapsed_time:.2f}s. "
            f"Sent {email_count}/{subscriber_count} emails for {alert_type}."
        )
        
        return results
            
    except Exception as e:
        # Catch any unexpected errors
        error = f"Unexpected error in email alert process: {str(e)}"
        logger.error(error)
        logger.error(traceback.format_exc())
        results["errors"].append(error)
        return results

def send_test_email(to_email, subject, body, alert_id=None, include_image=False):
    """
    Send a test email for debugging purposes.
    
    Args:
        to_email (str): Email address to send to
        subject (str): Email subject
        body (str): Email body content
        alert_id (str, optional): Add alert ID to email for testing tracking
        include_image (bool, optional): Whether to include a test image
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Sending direct test email to {to_email}")
    
    try:
        # Add alert ID to subject if provided
        if alert_id:
            subject = f"{subject} [ID: {alert_id}]"
            
        # Create message
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject
        
        # Add test header to body
        test_body = f"""
        <html>
            <body>
                <h2 style="color: #FF6600;">TEST EMAIL</h2>
                {body}
        """
        
        # If alert ID provided, add it to the HTML body
        if alert_id:
            test_body += f"<p style='color: #777; font-size: 0.8em;'>Alert ID: {alert_id}</p>"
            
        # Include a test placeholder image if requested
        if include_image:
            test_body += """
                <p><strong>Test Image:</strong></p>
                <p style="background-color: #f0f0f0; padding: 15px; border: 1px solid #ddd; text-align: center;">
                    [This is where a detection image would appear]
                </p>
            """
        
        # Close HTML
        test_body += """
                <p style="color: #FF6600; font-weight: bold;">
                    This is a TEST email and can be safely ignored.
                </p>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(test_body, "html"))
        
        # Connect and send
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            logger.debug("Connecting to SMTP server for direct test")
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            logger.debug(f"Sending test email to {to_email}")
            server.send_message(msg)
            
            logger.info(f"Test email sent successfully to {to_email}")
            
        return True
            
    except Exception as e:
        logger.error(f"Failed to send test email: {e}")
        logger.error(traceback.format_exc())
        return False

def verify_email_setup():
    """
    Verify that email functionality is properly configured.
    
    Returns:
        dict: Status of email setup including any errors
    """
    status = {
        "configured": False,
        "connection_test": False,
        "errors": []
    }
    
    logger.info("Verifying email setup...")
    
    # Check for required environment variables
    if not EMAIL_ADDRESS:
        status["errors"].append("Email address not configured")
        
    if not EMAIL_PASSWORD:
        status["errors"].append("Email password not configured")
        
    if len(status["errors"]) > 0:
        logger.warning("Email setup verification failed: missing credentials")
        return status
        
    # Mark as configured if we have the basic requirements
    status["configured"] = True
    
    # Test SMTP connection
    try:
        logger.debug("Testing SMTP connection")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.quit()
        
        status["connection_test"] = True
        logger.info("Email setup verification successful")
        
    except Exception as e:
        error = f"SMTP connection test failed: {str(e)}"
        logger.error(error)
        status["errors"].append(error)
        
    return status

# Test the functionality if run directly
if __name__ == "__main__":
    # Test email alert system
    logger.info("Testing email alert system...")
    
    # Generate a test alert ID
    import random
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    random_suffix = ''.join(random.choices('0123456789ABCDEF', k=3))
    test_alert_id = f"OWL-{timestamp}-{random_suffix}"
    
    # Test email setup verification
    setup_status = verify_email_setup()
    if not setup_status["configured"]:
        logger.error("Email setup not properly configured. Please check your settings.")
        for error in setup_status["errors"]:
            logger.error(f"  - {error}")
        exit(1)
    
    # Test sending to all subscribers
    logger.info("Testing alert email to subscribers...")
    results = send_email_alert(
        "Wyze Internal Camera", 
        "Owl In Box", 
        is_test=True, 
        test_prefix="TEST: ",
        alert_id=test_alert_id
    )
    
    if results["success"]:
        logger.info(f"Successfully sent test emails to {results['email_count']} subscribers")
    else:
        logger.warning("Failed to send test emails to subscribers")
        for error in results["errors"]:
            logger.warning(f"  - {error}")
    
    # Test direct email
    logger.info("Testing direct email to admin...")
    test_email = os.getenv("TEST_EMAIL", "maxferrigni@gmail.com")
    success = send_test_email(
        test_email,
        "Email Alert System Test",
        """
        <p>This is a test of the email alert system for the Owl Monitoring App v1.5.4.</p>
        <p>If you're seeing this, the email system is working properly.</p>
        """,
        alert_id=test_alert_id,
        include_image=True
    )
    
    if success:
        logger.info(f"Successfully sent direct test email to {test_email}")
    else:
        logger.warning(f"Failed to send direct test email to {test_email}")
    
    logger.info("Email tests completed")