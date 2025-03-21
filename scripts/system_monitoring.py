# File: system_monitoring.py
# Purpose: Monitor Wyze camera and OBS stream health for the Owl Monitoring system
#
# March 20, 2025 - Version 1.4.7.1
# - Added OBS streaming status monitoring
# - Improved admin alerts with rate limiting (30-min cooldown)
# - Enhanced Wyze camera monitoring reliability
# - Added status display information for UI integration

import os
import time
import datetime
import threading
import pyautogui
import cv2
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv
import psutil

# Import utilities
from utilities.logging_utils import get_logger
from utilities.database_utils import get_subscribers

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger()

# Email credentials from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "owlyfans01@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Google App Password

class OwlySystemMonitor:
    """
    Monitors the health of critical Owly system components:
    - Wyze Camera Feed
    - OBS Stream Status
    
    Sends alerts to admin users when issues are detected.
    """
    
    def __init__(self, config=None, logger=None):
        self.logger = logger or get_logger()
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            # Wyze camera monitoring
            'wyze_camera': {
                'enabled': True,
                'check_interval_seconds': 300,  # Check every 5 minutes
                'max_retries': 3,
                'recovery_click_coords': (960, 540),  # Default to center of screen
                'roi': (400, 300, 1000, 800),  # Region to check for camera feed
                'error_patterns': {
                    'black_screen_threshold': 30,  # Avg pixel value below this indicates black screen
                    'frozen_frames_threshold': 0.98  # Similar frames above this % indicates frozen camera
                }
            },
            # OBS monitoring
            'obs_stream': {
                'enabled': True,
                'check_interval_seconds': 300,  # Check every 5 minutes
                'alert_cooldown_seconds': 1800  # 30 minutes between alerts
            }
        }
        
        # Merge provided config with defaults
        self.merge_config()
        
        # Initialize monitoring state
        self.wyze_state = {
            'last_check_time': None,
            'error_count': 0,
            'last_frame': None,
            'recovery_attempted': False,
            'alerts_sent': 0
        }
        
        self.obs_state = {
            'last_check_time': None,
            'error_count': 0,
            'is_running': False,
            'last_alert_time': 0,  # Time when last alert was sent (unix timestamp)
            'alerts_sent': 0
        }
        
        # Background monitoring thread
        self.monitoring_thread = None
        self.running = False
        
        self.logger.info("OwlySystemMonitor initialized")
    
    def merge_config(self):
        """Merge provided config with defaults"""
        if not self.config:
            self.config = self.default_config
            return
            
        # Handle Wyze camera config
        if 'wyze_camera' not in self.config:
            self.config['wyze_camera'] = self.default_config['wyze_camera']
        else:
            for key, value in self.default_config['wyze_camera'].items():
                if key not in self.config['wyze_camera']:
                    self.config['wyze_camera'][key] = value
                    
        # Handle OBS config
        if 'obs_stream' not in self.config:
            self.config['obs_stream'] = self.default_config['obs_stream']
        else:
            for key, value in self.default_config['obs_stream'].items():
                if key not in self.config['obs_stream']:
                    self.config['obs_stream'][key] = value
    
    def check_wyze_camera_feed(self):
        """
        Check if the Wyze camera feed is functioning properly.
        
        Returns:
            tuple: (status_ok, details, screenshot)
        """
        self.logger.info("Checking Wyze camera feed...")
        
        try:
            # Take screenshot of the region containing the camera feed
            roi = self.config['wyze_camera']['roi']
            screenshot = pyautogui.screenshot(region=roi)
            
            # Convert to numpy array for analysis
            img_array = np.array(screenshot)
            
            # Check for black screen (camera disconnected)
            avg_pixel_value = np.mean(img_array)
            black_threshold = self.config['wyze_camera']['error_patterns']['black_screen_threshold']
            
            if avg_pixel_value < black_threshold:
                self.logger.warning(f"Wyze camera appears to be black (avg pixel: {avg_pixel_value:.2f})")
                return False, "Black screen detected", screenshot
            
            # Check for frozen feed by comparing with previous frame
            if self.wyze_state['last_frame'] is not None:
                # Convert current and previous frames to grayscale
                current_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                prev_gray = cv2.cvtColor(np.array(self.wyze_state['last_frame']), cv2.COLOR_RGB2GRAY)
                
                # Calculate frame similarity
                similarity = np.sum(current_gray == prev_gray) / current_gray.size
                frozen_threshold = self.config['wyze_camera']['error_patterns']['frozen_frames_threshold']
                
                if similarity > frozen_threshold:
                    self.logger.warning(f"Wyze camera appears to be frozen (similarity: {similarity:.2f})")
                    return False, "Frozen feed detected", screenshot
            
            # Save current frame for future comparison
            self.wyze_state['last_frame'] = screenshot
            self.wyze_state['last_check_time'] = datetime.datetime.now()
            self.wyze_state['error_count'] = 0  # Reset error count
            
            self.logger.info("Wyze camera feed check: OK")
            return True, "Camera feed operational", screenshot
            
        except Exception as e:
            self.logger.error(f"Error checking Wyze camera feed: {e}")
            return False, f"Check error: {str(e)}", None
    
    def attempt_wyze_recovery(self):
        """
        Attempt to recover Wyze camera feed by simulating mouse clicks.
        
        Returns:
            bool: True if recovery was attempted, False otherwise
        """
        if self.wyze_state['recovery_attempted']:
            self.logger.info("Recovery already attempted, skipping")
            return False
            
        try:
            self.logger.info("Attempting Wyze camera recovery...")
            
            # Get coordinates for mouse click (center of camera area by default)
            coords = self.config['wyze_camera']['recovery_click_coords']
            
            # Perform click
            pyautogui.click(coords[0], coords[1])
            time.sleep(2)  # Wait for response
            
            # Try clicking again at slightly offset positions if needed
            for offset in [(20, 0), (-20, 0), (0, 20), (0, -20)]:
                pyautogui.click(coords[0] + offset[0], coords[1] + offset[1])
                time.sleep(1)
            
            self.wyze_state['recovery_attempted'] = True
            self.logger.info("Recovery attempt completed")
            
            # Wait a bit longer for camera to initialize
            time.sleep(5)
            
            # Check if recovery worked
            status, details, _ = self.check_wyze_camera_feed()
            if status:
                self.logger.info("Recovery successful")
            else:
                self.logger.warning(f"Recovery attempt failed: {details}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error during recovery attempt: {e}")
            return False
    
    def check_obs_process(self):
        """
        Check if OBS is properly running.
        
        Returns:
            bool: True if OBS is running, False otherwise
        """
        try:
            # First check if OBS process is running using psutil
            obs_running = False
            for proc in psutil.process_iter(['name']):
                if 'obs' in proc.info['name'].lower():
                    obs_running = True
                    break
            
            # Update state
            self.obs_state['is_running'] = obs_running
            self.obs_state['last_check_time'] = datetime.datetime.now()
            
            # Log result
            if obs_running:
                self.logger.info("OBS is running")
            else:
                self.logger.warning("OBS is not running")
            
            return obs_running
            
        except Exception as e:
            self.logger.error(f"Error checking OBS process: {e}")
            return False
    
    def get_admin_subscribers(self):
        """
        Get subscribers marked as Owly Admins.
        
        Returns:
            list: List of admin subscriber records
        """
        try:
            # Get admin subscribers
            admins = get_subscribers(admin_only=True)
            
            # If no admins found, default to first regular subscriber as fallback
            if not admins:
                self.logger.warning("No admin subscribers found, using regular subscribers as fallback")
                admins = get_subscribers(notification_type="email")
                
            return admins
        except Exception as e:
            self.logger.error(f"Error getting admin subscribers: {e}")
            return []
    
    def send_admin_alert(self, issue, details, screenshot=None):
        """
        Send an alert email to admin users with 30-minute cooldown.
        
        Args:
            issue (str): Short description of the issue
            details (str): Detailed explanation
            screenshot (PIL.Image, optional): Screenshot showing the issue
            
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        try:
            # Get admin subscribers
            admins = self.get_admin_subscribers()
            
            if not admins:
                self.logger.error("Cannot send admin alert: No admin users found")
                return False
            
            # Check if we're within the cooldown period
            current_time = time.time()
            cooldown_seconds = self.config['obs_stream']['alert_cooldown_seconds']
            
            if (current_time - self.obs_state['last_alert_time']) < cooldown_seconds:
                self.logger.info(f"Admin alert cooldown active: {int((cooldown_seconds - (current_time - self.obs_state['last_alert_time'])) / 60)} minutes remaining")
                return False
                
            # Create email content
            subject = f"OWLY SYSTEM ALERT: {issue}"
            
            # Create email for each admin
            for admin in admins:
                admin_email = admin.get('email')
                admin_name = admin.get('name', 'Admin')
                
                if not admin_email:
                    continue
                    
                try:
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
                            <p>Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
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
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                        server.send_message(msg)
                        
                    self.logger.info(f"Admin alert sent to {admin_email}: {issue}")
                    
                except Exception as email_err:
                    self.logger.error(f"Error sending admin alert to {admin_email}: {email_err}")
            
            # Update last alert time to respect cooldown
            self.obs_state['last_alert_time'] = current_time
            self.obs_state['alerts_sent'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending admin alert: {e}")
            return False
    
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle checking all components"""
        try:
            self.logger.info("Starting monitoring cycle...")
            
            # Check Wyze camera if enabled
            if self.config['wyze_camera']['enabled']:
                wyze_ok, wyze_details, screenshot = self.check_wyze_camera_feed()
                
                if not wyze_ok:
                    self.wyze_state['error_count'] += 1
                    error_threshold = self.config['wyze_camera']['max_retries']
                    
                    # If we've seen multiple errors, attempt recovery
                    if self.wyze_state['error_count'] >= error_threshold:
                        self.logger.warning(f"Wyze camera error threshold reached ({error_threshold})")
                        
                        # Attempt recovery
                        recovery_attempted = self.attempt_wyze_recovery()
                        
                        # If recovery didn't work or wasn't attempted, notify admin
                        if recovery_attempted:
                            # Check again after recovery attempt
                            wyze_ok, wyze_details, screenshot = self.check_wyze_camera_feed()
                        
                        # If still failing after recovery, send alert
                        if not wyze_ok:
                            self.send_admin_alert(
                                issue="Wyze Camera Feed Problem",
                                details=f"Issue: {wyze_details}\nRecovery attempted: {recovery_attempted}",
                                screenshot=screenshot
                            )
                            self.wyze_state['alerts_sent'] += 1
                            
                            # Reset error count to avoid repeated alerts
                            self.wyze_state['error_count'] = 0
                else:
                    # If everything is fine now, reset recovery flag
                    self.wyze_state['recovery_attempted'] = False
            
            # Check OBS if enabled
            if self.config['obs_stream']['enabled']:
                # Check if OBS is running
                obs_running = self.check_obs_process()
                
                if not obs_running:
                    self.logger.warning("OBS process not found")
                    self.obs_state['error_count'] += 1
                    
                    # Send alert with proper cooldown
                    alert_sent = self.send_admin_alert(
                        issue="OBS Not Running",
                        details=(
                            "The OBS process was not found running on the system.\n\n"
                            "Please start OBS to ensure the stream continues."
                        )
                    )
                    
                    if alert_sent:
                        self.logger.info("OBS alert sent to administrators")
                    else:
                        self.logger.debug("OBS alert was not sent (cooldown or no admins)")
                else:
                    # OBS is running, reset error count
                    self.obs_state['error_count'] = 0
            
            self.logger.info("Monitoring cycle completed")
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                self.run_monitoring_cycle()
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                
            # Wait for next check interval
            # Use shorter interval for Wyze camera by default
            check_interval = min(
                self.config['wyze_camera']['check_interval_seconds'],
                self.config['obs_stream']['check_interval_seconds']
            )
            
            # Sleep in small increments to allow for clean shutdown
            for _ in range(check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def start_monitoring(self):
        """Start monitoring in a background thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.logger.warning("Monitoring already running")
            return
            
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        self.logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
            
        self.logger.info("Monitoring stopped")
    
    def get_status(self):
        """
        Get the current status of all monitored components.
        
        Returns:
            dict: Status of all monitored components
        """
        return {
            'wyze_camera': {
                'enabled': self.config['wyze_camera']['enabled'],
                'last_check': self.wyze_state['last_check_time'],
                'error_count': self.wyze_state['error_count'],
                'alerts_sent': self.wyze_state['alerts_sent'],
                'recovery_attempted': self.wyze_state['recovery_attempted']
            },
            'obs_stream': {
                'enabled': self.config['obs_stream']['enabled'],
                'last_check': self.obs_state['last_check_time'],
                'is_running': self.obs_state['is_running'],
                'error_count': self.obs_state['error_count'],
                'alerts_sent': self.obs_state['alerts_sent'],
                'cooldown_active': (time.time() - self.obs_state['last_alert_time']) < self.config['obs_stream']['alert_cooldown_seconds'],
                'cooldown_remaining_seconds': max(0, self.config['obs_stream']['alert_cooldown_seconds'] - (time.time() - self.obs_state['last_alert_time']))
            }
        }

def start_wyze_monitoring(config=None):
    """
    Utility function to start Wyze camera monitoring.
    
    Args:
        config (dict, optional): Configuration options
        
    Returns:
        OwlySystemMonitor: The monitoring instance
    """
    monitor = OwlySystemMonitor(config)
    monitor.start_monitoring()
    return monitor

if __name__ == "__main__":
    import random  # For the recovery jitter
    
    # Test the camera monitor
    logger.info("Testing system monitoring functionality...")
    
    # Create the monitor with default settings
    monitor = OwlySystemMonitor()
    
    # Test OBS status check
    logger.info("Testing OBS process check...")
    obs_running = monitor.check_obs_process()
    logger.info(f"OBS running: {obs_running}")
    
    # Test Wyze camera check
    is_working, issue, frame = monitor.check_wyze_camera_feed()
    logger.info(f"Camera feed working: {is_working}, issue: {issue}")
    
    if not is_working:
        # Test recovery
        recovery_success = monitor.attempt_wyze_recovery()
        logger.info(f"Recovery attempt {'successful' if recovery_success else 'failed'}")
    
    # Manual test of admin notification
    test_notification = input("Send test admin notification? (y/n): ")
    if test_notification.lower() == 'y':
        monitor.send_admin_alert(
            issue="Test System Alert",
            details="This is a test of the admin notification system."
        )
    
    # Start continuous monitoring if requested
    start_monitoring = input("Start continuous monitoring? (y/n): ")
    if start_monitoring.lower() == 'y':
        monitor.start_monitoring()
        logger.info("Monitoring started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping monitoring...")
            monitor.stop_monitoring()