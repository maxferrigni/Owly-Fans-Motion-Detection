# File: alert_email.py
# Purpose: Handle email alerts for the motion detection system
#
# April 7, 2025 Update - Version 2.1.0
# - Enhanced image URL validation to use correct Supabase domain
# - Added helper function to validate and correct image URLs
# - Improved alert frequency with proper URL handling
# - Fixed URL validation for base, current, and comparison images
# - Streamlined image rendering in HTML emails
# - Added fallback text for missing images
# - Improved logging of image URLs

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os
import time
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Import utilities
from utilities.logging_utils import get_logger
from utilities.constants import ALERT_PRIORITIES, SUPABASE_PUBLIC_URL, SUPABASE_STORAGE_URL

# Import from database_utils
from utilities.database_utils import get_subscribers, get_admin_subscribers

# Initialize logger
logger = get_logger()

# Load environment variables
load_dotenv()

# Email credentials from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Google App Password

# Track last admin alert time for rate limiting
last_admin_alert_time = 0

if not EMAIL_PASSWORD:
    error_msg = "Email password not found in environment variables"
    logger.error(error_msg)
    raise ValueError(error_msg)

def validate_image_url(url):
    """
    Validate an image URL to ensure it uses the correct Supabase domain.
    
    Args:
        url (str): Image URL to validate
        
    Returns:
        str: Corrected URL or None if invalid
    """
    if not url:
        return None
        
    try:
        # Check if using wrong domain and fix it
        wrong_domain = "project-dev-123.supabase.co"
        if wrong_domain in url:
            url = url.replace(wrong_domain, 
                             SUPABASE_PUBLIC_URL.replace("https://", ""))
            logger.info(f"Fixed incorrect domain in URL: {url}")
        
        # Make sure URL starts with proper protocol
        if not url.startswith("http"):
            url = f"https://{url}"
        
        # Simple check if URL seems valid
        if "supabase" not in url or ".co" not in url:
            logger.warning(f"URL doesn't look like a valid Supabase URL: {url}")
            return None
            
        return url
        
    except Exception as e:
        logger.error(f"Error validating URL: {e}")
        return None

def get_image_html(url, image_type):
    """
    Generate HTML for an image with fallback for missing images.
    
    Args:
        url (str): URL of the image
        image_type (str): Type of image (Base, Current, Comparison)
        
    Returns:
        str: HTML string for the image section
    """
    if url:
        return f"""
            <div style="flex: 1; min-width: 300px;">
                <p><strong>{image_type} Image:</strong></p>
                <a href="{url}" target="_blank">
                    <img src="{url}" alt="{image_type} Image" style="max-width: 100%; max-height: 300px;" />
                </a>
                <p><small><a href="{url}" target="_blank">Open {image_type} Image</a></small></p>
            </div>
        """
    else:
        return f"""
            <div style="flex: 1; min-width: 300px;">
                <p><strong>{image_type} Image:</strong></p>
                <p style="color: #777;">{image_type} image not available</p>
            </div>
        """

def send_email_alert(camera_name, alert_type, is_test=False, test_prefix="", 
                     image_url=None, alert_id=None, base_image_url=None, 
                     current_image_url=None, confidence_info=None):
    """
    Send email alerts based on camera name and alert type.
    
    Args:
        camera_name (str): Name of the camera that detected motion
        alert_type (str): Type of alert ("Owl In Box", "Owl On Box", "Owl In Area", etc.)
        is_test (bool, optional): Whether this is a test alert
        test_prefix (str, optional): Prefix to add for test alerts (e.g., "TEST: ")
        image_url (str, optional): URL to the comparison image
        alert_id (str, optional): Unique ID for the alert for tracking
        base_image_url (str, optional): URL to the base image
        current_image_url (str, optional): URL to the current image
        confidence_info (dict, optional): Information about detection confidence and criteria
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
    
    # Add alert ID to subject if provided
    if alert_id:
        subject = f"{subject} [ID: {alert_id}]"
    
    # Validate all image URLs to ensure they use the correct domain
    image_url = validate_image_url(image_url)
    base_image_url = validate_image_url(base_image_url)
    current_image_url = validate_image_url(current_image_url)

    # Log the URLs being used
    logger.info(f"Using validated URLs in email - Base: {base_image_url}, Current: {current_image_url}, Comparison: {image_url}")

    # Log available images for debugging
    available_images = []
    if base_image_url:
        available_images.append("base")
    if current_image_url:
        available_images.append("current")
    if image_url:
        available_images.append("comparison")
    
    logger.info(f"Images available for alert: {', '.join(available_images) if available_images else 'None'}")

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

                # HTML email body with personalized greeting, images, and detailed metrics
                html_content = f"""
                <html>
                    <body>
                        <p>{greeting}</p>
                        <p>{body}</p>
                        <p>Please check the camera feed at <a href='http://www.owly-fans.com'>Owly-Fans.com</a>.</p>
                """
                
                # Format confidence metrics if available
                if confidence_info:
                    html_content += f"""
                        <h3>Detection Details:</h3>
                        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                            <tr style="background-color: #f2f2f2;">
                                <th>Metric</th>
                                <th>Value</th>
                                <th>Threshold</th>
                                <th>Result</th>
                            </tr>
                    """
                    
                    owl_confidence = confidence_info.get("owl_confidence", 0.0)
                    threshold = confidence_info.get("threshold_used", 60.0)
                    confidence_factors = confidence_info.get("confidence_factors", {})
                    
                    # Overall confidence row
                    html_content += f"""
                        <tr>
                            <td><strong>Overall Confidence</strong></td>
                            <td>{owl_confidence:.1f}%</td>
                            <td>{threshold:.1f}%</td>
                            <td style="color: {'green' if owl_confidence >= threshold else 'red'}">
                                {'✓ Pass' if owl_confidence >= threshold else '✗ Fail'}
                            </td>
                        </tr>
                    """
                    
                    # Add rows for confidence factors
                    for factor, value in confidence_factors.items():
                        factor_name = factor.replace('_', ' ').title()
                        html_content += f"""
                            <tr>
                                <td>{factor_name}</td>
                                <td>{value:.1f}%</td>
                                <td>-</td>
                                <td>Component</td>
                            </tr>
                        """
                    
                    # Consecutive frames
                    consecutive_frames = confidence_info.get("consecutive_owl_frames", 0)
                    frames_required = confidence_info.get("consecutive_frames_required", 2)
                    html_content += f"""
                        <tr>
                            <td><strong>Consecutive Frames</strong></td>
                            <td>{consecutive_frames}</td>
                            <td>{frames_required}</td>
                            <td style="color: {'green' if consecutive_frames >= frames_required else 'red'}">
                                {'✓ Pass' if consecutive_frames >= frames_required else '✗ Fail'}
                            </td>
                        </tr>
                    """
                    
                    # Other metrics if available
                    if "pixel_change" in confidence_info:
                        html_content += f"""
                            <tr>
                                <td>Pixel Change</td>
                                <td>{confidence_info['pixel_change']:.2f}%</td>
                                <td>-</td>
                                <td>Informational</td>
                            </tr>
                        """
                        
                    if "luminance_change" in confidence_info:
                        html_content += f"""
                            <tr>
                                <td>Luminance Change</td>
                                <td>{confidence_info['luminance_change']:.2f}</td>
                                <td>-</td>
                                <td>Informational</td>
                            </tr>
                        """
                    
                    html_content += "</table>"
                
                # Add priority level indicator
                if priority_level >= 4:  # Multiple owls or eggs/babies
                    html_content += f"""
                        <p style="color: red; font-weight: bold;">
                            This is a high priority alert! (Priority Level: {priority_level}/6)
                        </p>
                    """
                
                # Add image sections with all available images
                if base_image_url or current_image_url or image_url:
                    html_content += "<h3>Detection Images:</h3>"
                    html_content += '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
                    
                    # Use the image HTML generator function for each image type
                    if base_image_url:
                        html_content += get_image_html(base_image_url, "Base")
                    
                    if current_image_url:
                        html_content += get_image_html(current_image_url, "Current")
                    
                    if image_url:
                        html_content += get_image_html(image_url, "Comparison")
                    
                    html_content += '</div>'
                else:
                    # No images available
                    html_content += """
                        <p style="color: #777;">No detection images are available for this alert.</p>
                    """
                
                # Add alert ID to footer if provided
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

def send_admin_alert(issue, details, screenshot=None):
    """
    Send an alert email to admin users with 30-minute cooldown.
    Added in v1.4.7.1 for administrator-only system alerts.
    
    Args:
        issue (str): Short description of the issue
        details (str): Detailed explanation
        screenshot (PIL.Image, optional): Screenshot showing the issue
        
    Returns:
        bool: True if alert was sent successfully, False otherwise
    """
    global last_admin_alert_time
    
    try:
        # Check if within cooldown period (30 minutes = 1800 seconds)
        current_time = time.time()
        cooldown_seconds = 1800  # 30 minutes
        
        if (current_time - last_admin_alert_time) < cooldown_seconds:
            remaining_minutes = int((cooldown_seconds - (current_time - last_admin_alert_time)) / 60)
            logger.info(f"Admin alert cooldown active: {remaining_minutes} minutes remaining")
            return False
            
        # Get admin subscribers
        admins = get_admin_subscribers()
        
        if not admins:
            logger.error("Cannot send admin alert: No admin users found")
            return False
            
        # Create email content with ADMIN prefix
        subject = f"OWLY SYSTEM ALERT: {issue}"
        
        # Create timestamp
        timestamp = datetime.now(pytz.timezone('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Send email to each admin
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            for admin in admins:
                admin_email = admin.get('email')
                admin_name = admin.get('name', 'Admin')
                
                if not admin_email:
                    continue
                    
                # Create multipart message
                msg = MIMEMultipart()
                msg['From'] = EMAIL_ADDRESS
                msg['To'] = admin_email
                msg['Subject'] = subject
                
                # Create HTML body
                html_content = f"""
                <html>
                    <body>
                        <h2>Owly System Alert</h2>
                        <p>Hello {admin_name},</p>
                        <p>An issue has been detected with the Owly monitoring system:</p>
                        <p><strong>{issue}</strong></p>
                        <p>{details}</p>
                        <p>Timestamp: {timestamp}</p>
                        <hr>
                        <p>This is an automated message from the Owly System Monitor.</p>
                        <p><small>You are receiving this message because you are registered as an administrator.</small></p>
                    </body>
                </html>
                """
                
                # Attach HTML content
                msg.attach(MIMEText(html_content, 'html'))
                
                # Attach screenshot if provided
                if screenshot:
                    # Convert PIL image to bytes
                    import io
                    img_bytes = io.BytesIO()
                    screenshot.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                    # Create image attachment
                    image = MIMEImage(img_bytes.read())
                    image.add_header('Content-Disposition', 'attachment', filename='screenshot.png')
                    msg.attach(image)
                
                # Send email
                server.send_message(msg)
                logger.info(f"Admin alert sent to {admin_email}: {issue}")
        
        # Update last alert time to enforce cooldown
        last_admin_alert_time = current_time
        logger.info(f"Admin alert sent: {issue}")
        return True
            
    except Exception as e:
        logger.error(f"Error sending admin alert: {e}")
        return False

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
    # Test email functionality
    logger.info("Testing email alert system...")
    
    # Generate a test alert ID
    import random
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    random_suffix = ''.join(random.choices('0123456789ABCDEF', k=3))
    test_alert_id = f"OWL-{timestamp}-{random_suffix}"
    
    # Test with image URLs - updated to use correct domain
    test_image_url = f"{SUPABASE_STORAGE_URL}/owl_detections/owl_in_box/test_image.jpg"
    test_base_url = f"{SUPABASE_STORAGE_URL}/base_images/test_base.jpg"
    test_current_url = f"{SUPABASE_STORAGE_URL}/owl_detections/owl_in_box/test_current.jpg"
    
    # Example confidence information
    test_confidence_info = {
        "owl_confidence": 75.5,
        "threshold_used": 60.0,
        "consecutive_owl_frames": 3,
        "consecutive_frames_required": 2,
        "confidence_factors": {
            "shape_confidence": 30.0,
            "motion_confidence": 25.5,
            "temporal_confidence": 15.0,
            "camera_confidence": 5.0
        },
        "pixel_change": 15.2,
        "luminance_change": 35.7
    }
    
    # Test standard alert with ID and all images
    send_email_alert(
        "Wyze Internal Camera", 
        "Owl In Box", 
        is_test=True, 
        test_prefix="TEST: ",
        image_url=test_image_url,
        base_image_url=test_base_url,
        current_image_url=test_current_url,
        alert_id=test_alert_id,
        confidence_info=test_confidence_info
    )
    
    # Test without current image URL
    send_email_alert(
        "Wyze External Camera", 
        "Owl On Box", 
        is_test=True, 
        test_prefix="TEST: ",
        image_url=test_image_url,
        base_image_url=test_base_url,
        alert_id=f"{test_alert_id}-2",
        confidence_info=test_confidence_info
    )
    
    # Test with no images
    send_email_alert(
        "Wyze Doorbell Camera", 
        "Owl In Area", 
        is_test=True, 
        test_prefix="TEST: ",
        alert_id=f"{test_alert_id}-3",
        confidence_info=test_confidence_info
    )
    
    # Test admin alert functionality with cooldown
    logger.info("Testing admin alert with cooldown...")
    
    # Test admin alert
    admin_result = send_admin_alert(
        issue="Test System Alert",
        details="This is a test of the admin alert system with 30-minute cooldown.",
    )
    
    if admin_result:
        logger.info("Admin alert test succeeded")
        
        # Test cooldown by trying to send again immediately
        second_result = send_admin_alert(
            issue="Second Test Alert",
            details="This should be blocked by the cooldown."
        )
        
        if not second_result:
            logger.info("Cooldown test worked - second alert was blocked")
        else:
            logger.error("Cooldown test failed - second alert was sent")
    else:
        logger.error("Admin alert test failed")
    
    # Test direct email
    test_email = os.getenv("TEST_EMAIL", "maxferrigni@gmail.com")
    send_test_email(
        test_email,
        "Email Alert System Test v2.1.0",
        """
        <html>
            <body>
                <h2>Email Alerting System Test</h2>
                <p>This is a test of the email alert system for the Owl Monitoring App v2.1.0.</p>
                <p>This version includes improved URL validation and handling, with fallbacks for missing images.</p>
                <p>If you're seeing this, the system is working properly.</p>
            </body>
        </html>
        """,
        alert_id=test_alert_id
    )
    
    logger.info(f"Email tests completed with alert ID: {test_alert_id}")