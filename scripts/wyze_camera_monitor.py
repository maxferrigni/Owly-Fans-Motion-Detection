# File: scripts/wyze_camera_monitor.py
# Purpose: Monitor Wyze camera feed and recover from failures
#
# March 5, 2025 - Version 1.2.0
# - Initial implementation for Wyze camera monitoring
# - Provides automatic recovery through mouse clicks
# - Sends admin alerts for persistent failures

import os
import time
import threading
import datetime
import pytz
import cv2
import numpy as np
import pyautogui
from PIL import Image
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

# Import utilities
from utilities.logging_utils import get_logger
from utilities.database_utils import get_admin_subscribers
from utilities.constants import CAMERA_MAPPINGS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger()

# Email credentials
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

class WyzeCameraMonitor:
    """Class to monitor and recover Wyze camera feed"""
    
    def __init__(self, config=None):
        """
        Initialize the Wyze camera monitor.
        
        Args:
            config (dict, optional): Configuration options
        """
        self.logger = logger
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            # Screen positions for Wyze camera window
            'camera_roi': self.config.get('camera_roi', [-1899, 698, -1255, 1039]),
            
            # Coordinates for refresh button click (x, y)
            'refresh_position': self.config.get('refresh_position', (-1577, 800)),
            
            # Recovery settings
            'max_retries': self.config.get('max_retries', 3),
            'retry_delay': self.config.get('retry_delay', 5),  # seconds
            
            # Monitoring settings
            'check_interval': self.config.get('check_interval', 300),  # seconds (5 minutes)
            
            # Detection thresholds
            'black_screen_threshold': self.config.get('black_screen_threshold', 20),  # average pixel value under this is considered black
            'frozen_frame_threshold': self.config.get('frozen_frame_threshold', 2.0),  # pixel change percentage below this is considered frozen
            
            # Admin notification settings
            'notification_cooldown': self.config.get('notification_cooldown', 3600)  # seconds (1 hour)
        }
        
        # Merge with provided config
        self.config = {**self.default_config, **(config or {})}
        
        # State tracking
        self.last_frame = None
        self.current_frame = None
        self.failure_count = 0
        self.recovery_attempts = 0
        self.is_recovering = False
        self.last_notification_time = None
        self.monitoring_thread = None
        self.stop_requested = False
        
        self.logger.info("Wyze camera monitor initialized")
        
    def check_camera_feed(self):
        """
        Check if the Wyze camera feed is working properly.
        
        Returns:
            tuple: (is_working, issue_type, frame)
                - is_working (bool): True if camera feed is okay
                - issue_type (str or None): 'black', 'frozen', or None if no issues
                - frame (PIL.Image): Current camera frame
        """
        try:
            # Capture the camera feed area
            x1, y1, x2, y2 = self.config['camera_roi']
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            # Take a screenshot of the camera area
            screenshot = pyautogui.screenshot(region=(x1, y1, width, height))
            
            # Convert to numpy array for analysis
            frame_np = np.array(screenshot)
            
            # Check for black screen (disconnected camera)
            avg_brightness = np.mean(frame_np)
            if avg_brightness < self.config['black_screen_threshold']:
                self.logger.warning(f"Black screen detected (brightness: {avg_brightness:.1f})")
                return False, "black", screenshot
            
            # Check for frozen frame (if we have a previous frame)
            if self.last_frame is not None:
                # Convert both frames to grayscale
                last_gray = cv2.cvtColor(np.array(self.last_frame), cv2.COLOR_RGB2GRAY)
                current_gray = cv2.cvtColor(frame_np, cv2.COLOR_RGB2GRAY)
                
                # Calculate absolute difference
                diff = cv2.absdiff(current_gray, last_gray)
                
                # Calculate percentage of changed pixels
                non_zero = np.count_nonzero(diff)
                total_pixels = diff.size
                change_percentage = (non_zero / total_pixels) * 100
                
                # Check if the frame is frozen
                if change_percentage < self.config['frozen_frame_threshold']:
                    self.logger.warning(f"Frozen frame detected (change: {change_percentage:.2f}%)")
                    return False, "frozen", screenshot
            
            # Update last_frame
            self.last_frame = screenshot
            self.current_frame = screenshot
            
            # Feed is working correctly
            return True, None, screenshot
            
        except Exception as e:
            self.logger.error(f"Error checking camera feed: {e}")
            return False, "error", None
    
    def attempt_recovery(self):
        """
        Attempt to recover the camera feed through mouse clicks.
        
        Returns:
            bool: True if recovery was successful
        """
        if self.is_recovering:
            self.logger.info("Recovery already in progress, skipping")
            return False
            
        self.is_recovering = True
        try:
            self.logger.info("Attempting Wyze camera recovery")
            
            # Get configured refresh button position
            refresh_x, refresh_y = self.config['refresh_position']
            
            # Track success
            success = False
            
            # Try recovery up to max_retries
            for attempt in range(1, self.config['max_retries'] + 1):
                self.logger.info(f"Recovery attempt {attempt}/{self.config['max_retries']}")
                
                # Click on the refresh button
                pyautogui.click(refresh_x, refresh_y)
                
                # Wait for the feed to refresh
                time.sleep(self.config['retry_delay'])
                
                # Check if recovery was successful
                is_working, issue, _ = self.check_camera_feed()
                if is_working:
                    self.logger.info(f"Camera feed recovered after {attempt} attempts")
                    self.failure_count = 0
                    self.recovery_attempts = 0
                    success = True
                    break
                
                # Increase jitter for subsequent clicks to account for possible misalignment
                refresh_x += random.randint(-5, 5)
                refresh_y += random.randint(-5, 5)
            
            # If all retries failed
            if not success:
                self.recovery_attempts += 1
                self.failure_count += 1
                self.logger.error(f"Failed to recover camera feed after {self.config['max_retries']} attempts")
                
                # Notify admin if this is a persistent issue
                if self.failure_count >= 3:
                    self.notify_admin_of_failure()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during recovery attempt: {e}")
            return False
        finally:
            self.is_recovering = False
    
    def notify_admin_of_failure(self):
        """Send an email notification to admin about persistent camera failure"""
        try:
            # Check if we should send a notification (respect cooldown)
            current_time = datetime.datetime.now()
            if (self.last_notification_time and 
                (current_time - self.last_notification_time).total_seconds() < self.config['notification_cooldown']):
                self.logger.info("Notification cooldown active, skipping admin alert")
                return
                
            # Get admin subscribers
            admin_subscribers = get_admin_subscribers()
            if not admin_subscribers:
                self.logger.warning("No admin subscribers found for notification")
                return
                
            # Prepare email
            subject = f"ALERT: Wyze Camera Feed Failure"
            
            # Create email with current frame if available
            for admin in admin_subscribers:
                to_email = admin.get('email')
                if not to_email:
                    continue
                    
                try:
                    # Create multipart message
                    msg = MIMEMultipart()
                    msg["From"] = EMAIL_ADDRESS
                    msg["To"] = to_email
                    msg["Subject"] = subject
                    
                    # Create message body
                    body = f"""
                    <html>
                    <body>
                        <h2>Wyze Camera Feed Failure</h2>
                        <p>The Wyze camera feed has failed and could not be automatically recovered.</p>
                        <p><strong>Failure details:</strong></p>
                        <ul>
                            <li>Failure count: {self.failure_count}</li>
                            <li>Recovery attempts: {self.recovery_attempts}</li>
                            <li>Time: {datetime.datetime.now(pytz.timezone('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S %Z')}</li>
                        </ul>
                        <p>Please check the camera feed manually.</p>
                    </body>
                    </html>
                    """
                    
                    msg.attach(MIMEText(body, "html"))
                    
                    # Attach the current frame if available
                    if self.current_frame:
                        # Convert PIL image to bytes
                        img_byte_arr = io.BytesIO()
                        self.current_frame.save(img_byte_arr, format='JPEG')
                        img_byte_arr = img_byte_arr.getvalue()
                        
                        # Create MIMEImage
                        image = MIMEImage(img_byte_arr)
                        image.add_header('Content-Disposition', 'attachment', filename='camera_state.jpg')
                        msg.attach(image)
                    
                    # Send email
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                        server.send_message(msg)
                        
                    self.logger.info(f"Admin notification sent to {to_email}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to send notification to {to_email}: {e}")
            
            # Update last notification time
            self.last_notification_time = current_time
            
        except Exception as e:
            self.logger.error(f"Error sending admin notification: {e}")
    
    def run_monitoring_loop(self):
        """Run the continuous monitoring loop in a separate thread"""
        self.stop_requested = False
        
        def monitoring_worker():
            self.logger.info("Wyze camera monitoring started")
            while not self.stop_requested:
                try:
                    # Check camera feed
                    is_working, issue_type, frame = self.check_camera_feed()
                    
                    # If not working, attempt recovery
                    if not is_working:
                        self.logger.warning(f"Camera feed issue detected: {issue_type}")
                        self.attempt_recovery()
                    else:
                        # Reset failure counter if working
                        if self.failure_count > 0:
                            self.logger.info("Camera feed is now working, resetting failure counters")
                            self.failure_count = 0
                            self.recovery_attempts = 0
                    
                    # Wait for next check interval
                    for _ in range(int(self.config['check_interval'])):
                        if self.stop_requested:
                            break
                        time.sleep(1)
                        
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    # Wait before retry
                    time.sleep(60)
            
            self.logger.info("Wyze camera monitoring stopped")
        
        # Start monitoring in a separate thread
        self.monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        self.monitoring_thread.start()
        
        return self.monitoring_thread
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.stop_requested = True
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=30)
            self.logger.info("Wyze camera monitoring stopped")

def start_wyze_monitoring(config=None):
    """
    Utility function to start Wyze camera monitoring.
    
    Args:
        config (dict, optional): Configuration options
        
    Returns:
        WyzeCameraMonitor: The monitoring instance
    """
    monitor = WyzeCameraMonitor(config)
    monitor.run_monitoring_loop()
    return monitor

if __name__ == "__main__":
    import random  # For the recovery jitter
    
    # Test the camera monitor
    logger.info("Testing Wyze camera monitoring...")
    
    # Create the monitor with default settings
    monitor = WyzeCameraMonitor()
    
    # Test single camera check
    is_working, issue, frame = monitor.check_camera_feed()
    logger.info(f"Camera feed working: {is_working}, issue: {issue}")
    
    if not is_working:
        # Test recovery
        recovery_success = monitor.attempt_recovery()
        logger.info(f"Recovery attempt {'successful' if recovery_success else 'failed'}")
    
    # Manual test of admin notification
    test_notification = input("Send test admin notification? (y/n): ")
    if test_notification.lower() == 'y':
        monitor.failure_count = 3
        monitor.recovery_attempts = 3
        monitor.notify_admin_of_failure()
    
    # Start continuous monitoring if requested
    start_monitoring = input("Start continuous monitoring? (y/n): ")
    if start_monitoring.lower() == 'y':
        monitor.run_monitoring_loop()
        logger.info("Monitoring started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping monitoring...")
            monitor.stop_monitoring()