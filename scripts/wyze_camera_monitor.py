# File: wyze_camera_monitor.py
# Purpose: Monitor Wyze camera feed and email admins if broken

import os
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
import pyautogui
from PIL import Image, ImageChops
import numpy as np
from utilities.logging_utils import get_logger
from utilities.database_utils import get_admin_subscribers
from utilities.constants import BROKEN_CAMERA_PATH

# Initialize logger
logger = get_logger()

class WyzeCameraMonitor:
    def __init__(self):
        # Configuration
        self.check_interval = 30 * 60  # 30 minutes
        self.camera_roi = (-1899, 698, -1255, 1039)  # Wyze camera region
        self.similarity_threshold = 0.9  # Threshold for comparison
        
        # Reference image path (using the constants path)
        self.reference_image_path = BROKEN_CAMERA_PATH
        
        # State tracking
        self.running = False
        self.reference_image = self._load_reference_image()
        self.last_email_time = None
        
        # Email settings
        self.email_address = os.environ.get('EMAIL_ADDRESS', 'owlyfans01@gmail.com')
        self.email_password = os.environ.get('EMAIL_PASSWORD')

    def _load_reference_image(self):
        """Load the broken camera reference image"""
        if os.path.exists(self.reference_image_path):
            logger.info(f"Loaded broken camera reference image")
            return Image.open(self.reference_image_path).convert('RGB')
        else:
            logger.warning(f"Reference image not found: {self.reference_image_path}")
            return None

    def _capture_camera_image(self):
        """Capture the current Wyze camera screen"""
        x, y, width, height = self.camera_roi
        width = abs(width - x)
        height = abs(height - y)
        return pyautogui.screenshot(region=(x, y, width, height)).convert('RGB')

    def _is_camera_broken(self, current_image):
        """Compare current image with reference broken image"""
        if self.reference_image is None:
            return False, 0
        
        try:
            # Ensure same size
            if self.reference_image.size != current_image.size:
                current_image = current_image.resize(self.reference_image.size)
            
            # Calculate difference
            diff = ImageChops.difference(self.reference_image, current_image)
            diff_array = np.array(diff)
            
            # Calculate similarity (0-1 where 1 is identical)
            diff_mean = np.mean(diff_array)
            similarity = 1 - (diff_mean / 255)
            
            return similarity >= self.similarity_threshold, similarity
        except Exception as e:
            logger.error(f"Error comparing images: {e}")
            return False, 0

    def _send_email_alert(self, current_image, similarity):
        """Send email alert to admins"""
        if not self.email_password:
            logger.error("Email password not configured")
            return False
            
        # Avoid sending too many emails
        if self.last_email_time and (datetime.now() - self.last_email_time < timedelta(hours=4)):
            logger.info("Skipping email - already sent recently")
            return False
            
        try:
            # Get admin subscribers
            admins = get_admin_subscribers()
            if not admins:
                logger.error("No admin subscribers found")
                return False
                
            # Create email
            for admin in admins:
                admin_email = admin.get('email')
                admin_name = admin.get('name', 'Admin')
                
                if not admin_email:
                    continue
                    
                # Create message
                msg = MIMEMultipart()
                msg['From'] = self.email_address
                msg['To'] = admin_email
                msg['Subject'] = "ALERT: Wyze Camera Feed is Broken"
                
                # Email body
                body = f"""
                <html>
                <body>
                    <h2>Wyze Camera Feed Alert</h2>
                    <p>Hello {admin_name},</p>
                    <p>The Wyze camera feed appears to be broken (similarity: {similarity:.2f}).</p>
                    <p>Please check the camera and restart it if necessary.</p>
                    <p>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </body>
                </html>
                """
                msg.attach(MIMEText(body, 'html'))
                
                # Attach current image
                img_bytes = current_image.tobytes()
                image = MIMEImage(img_bytes)
                image.add_header('Content-Disposition', 'attachment', filename='broken_camera.jpg')
                msg.attach(image)
                
                # Send email
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(self.email_address, self.email_password)
                    server.send_message(msg)
                    
                logger.info(f"Sent alert email to {admin_email}")
            
            self.last_email_time = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def check_camera(self):
        """Check if the camera is broken and send alert if needed"""
        try:
            # Skip if reference image not available
            if self.reference_image is None:
                logger.warning("No reference image available")
                return
                
            # Capture current image
            current_image = self._capture_camera_image()
            
            # Check if broken
            is_broken, similarity = self._is_camera_broken(current_image)
            
            if is_broken:
                logger.warning(f"Wyze camera appears broken (similarity: {similarity:.2f})")
                self._send_email_alert(current_image, similarity)
            else:
                logger.info(f"Wyze camera appears normal (similarity: {similarity:.2f})")
                
        except Exception as e:
            logger.error(f"Error checking camera: {e}")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        logger.info("Starting Wyze camera monitoring loop")
        
        while self.running:
            try:
                self.check_camera()
                
                # Sleep until next check
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        if self.running:
            return
            
        self.running = True
        threading.Thread(target=self._monitoring_loop, daemon=True).start()
        logger.info("Wyze camera monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring thread"""
        self.running = False
        logger.info("Wyze camera monitoring stopped")
        
    def save_reference_image(self):
        """Capture and save current camera state as reference image"""
        try:
            current_image = self._capture_camera_image()
            current_image.save(self.reference_image_path)
            self.reference_image = current_image
            logger.info(f"Saved reference image to {self.reference_image_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving reference image: {e}")
            return False

# Simple test if run directly
if __name__ == "__main__":
    import sys
    
    monitor = WyzeCameraMonitor()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "save":
            # Save current camera state as reference image
            monitor.save_reference_image()
        elif sys.argv[1] == "check":
            # Run a single check
            monitor.check_camera()
        elif sys.argv[1] == "monitor":
            # Start monitoring
            try:
                monitor.start_monitoring()
                print("Monitoring started. Press Ctrl+C to stop.")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                monitor.stop_monitoring()
        else:
            print("Usage: python wyze_camera_monitor.py [save|check|monitor]")
    else:
        print("Usage: python wyze_camera_monitor.py [save|check|monitor]")