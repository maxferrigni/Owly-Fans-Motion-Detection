# File: system_monitoring.py
# Purpose: Monitor Wyze camera and OBS stream health for the Owl Monitoring system
#
# March 5, 2025 - Version 1.2.0
# - Check Wyze camera feed health
# - Monitor OBS streaming status
# - Send admin alerts for system issues

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
                'output_dir': os.path.expanduser("~/Videos"),  # Default OBS recording location
                'min_file_size_kb': 100,  # Minimum expected file size
                'max_file_age_minutes': 15  # Maximum age of the newest file
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
            'last_recording_file': None,
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
    
    def check_obs_stream(self):
        """
        Check if OBS is properly streaming and recording.
        
        Returns:
            tuple: (status_ok, details)
        """
        self.logger.info("Checking OBS stream status...")
        
        try:
            output_dir = self.config['obs_stream']['output_dir']
            
            # Check if output directory exists
            if not os.path.exists(output_dir):
                return False, f"OBS output directory not found: {output_dir}"
            
            # Look for recent recording files
            video_files = []
            for file in os.listdir(output_dir):
                if file.endswith(('.mp4', '.mkv', '.flv')):
                    file_path = os.path.join(output_dir, file)
                    stat = os.stat(file_path)
                    # Only check files created or modified in the last 24 hours
                    if (time.time() - stat.st_mtime) < 86400:  # 24 hours
                        video_files.append({
                            'path': file_path,
                            'size': stat.st_size / 1024,  # Size in KB
                            'mtime': stat.st_mtime,
                            'ctime': stat.st_ctime
                        })
            
            # No recent video files found
            if not video_files:
                return False, "No recent recording files found"
            
            # Sort by modification time (newest first)
            video_files.sort(key=lambda x: x['mtime'], reverse=True)
            newest_file = video_files[0]
            
            # Update last recording file
            self.obs_state['last_recording_file'] = newest_file
            
            # Check file size
            min_size = self.config['obs_stream']['min_file_size_kb']
            if newest_file['size'] < min_size:
                return False, f"Latest recording file too small: {newest_file['size']:.2f}KB < {min_size}KB"
            
            # Check file age
            max_age_minutes = self.config['obs_stream']['max_file_age_minutes']
            file_age_minutes = (time.time() - newest_file['mtime']) / 60
            
            if file_age_minutes > max_age_minutes:
                return False, f"Latest recording file too old: {file_age_minutes:.1f} min > {max_age_minutes} min"
            
            # Everything looks good
            self.obs_state['last_check_time'] = datetime.datetime.now()
            self.obs_state['error_count'] = 0  # Reset error count
            
            self.logger.info("OBS stream check: OK")
            return True, f"OBS recording active ({file_age_minutes:.1f} min old, {newest_file['size']:.2f}KB)"
            
        except Exception as e:
            self.logger.error(f"Error checking OBS stream: {e}")
            return False, f"Check error: {str(e)}"
    
    def check_obs_process(self):
        """
        Check if OBS process is running.
        
        Returns:
            bool: True if OBS is running, False otherwise
        """
        try:
            for proc in psutil.process_iter(['name']):
                if 'obs' in proc.info['name'].lower():
                    return True
            return False
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
        Send an alert email to admin users.
        
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
                # First check if OBS is running
                obs_running = self.check_obs_process()
                
                if not obs_running:
                    self.logger.warning("OBS process not found")
                    self.obs_state['error_count'] += 1
                    
                    # Alert after first check if OBS is not running at all
                    if self.obs_state['error_count'] == 1:
                        self.send_admin_alert(
                            issue="OBS Not Running",
                            details="The OBS process was not found running on the system."
                        )
                        self.obs_state['alerts_sent'] += 1
                else:
                    # OBS is running, check recording status
                    obs_ok, obs_details = self.check_obs_stream()
                    
                    if not obs_ok:
                        self.obs_state['error_count'] += 1
                        error_threshold = 2  # Alert after two consecutive errors
                        
                        if self.obs_state['error_count'] >= error_threshold:
                            self.send_admin_alert(
                                issue="OBS Recording Issue",
                                details=f"Issue: {obs_details}"
                            )
                            self.obs_state['alerts_sent'] += 1
                            # Reset error count to avoid repeated alerts
                            self.obs_state['error_count'] = 0
                    else:
                        # Reset error count if everything is ok
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
                'error_count': self.obs_state['error_count'],
                'alerts_sent': self.obs_state['alerts_sent'],
                'last_file': self.obs_state['last_recording_file']
            }
        }

# Manual test if run directly
if __name__ == "__main__":
    logger.info("Testing system monitoring functionality...")
    
    # Create monitor with default config
    monitor = OwlySystemMonitor()
    
    # Run a single cycle for testing
    monitor.run_monitoring_cycle()
    
    # Get status
    status = monitor.get_status()
    logger.info(f"System status: {status}")
    
    # Test background monitoring
    logger.info("Starting background monitoring for 30 seconds...")
    monitor.start_monitoring()
    
    # Wait for 30 seconds
    time.sleep(30)
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    logger.info("System monitoring test complete")