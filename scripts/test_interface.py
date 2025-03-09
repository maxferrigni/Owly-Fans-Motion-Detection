# File: test_interface.py
# Purpose: Email alert testing interface for the Owl Monitoring System
# Version: 1.5.4
#
# Major updates in v1.5.4:
# - Fixed non-functional alert test buttons
# - Added proper logging of test results
# - Enhanced visual feedback during and after tests
# - Fixed communication with alert_manager

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS

class TestInterface:
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        
        # Reference to log_message function, will be set by main app
        self.log_message_callback = None
        
        # Track alert test status
        self.test_in_progress = False
        
        # Create the test interface
        self.create_interface()
        
    def set_log_callback(self, callback_func):
        """Set the callback function for logging messages to the main UI"""
        self.log_message_callback = callback_func
        
    def log_message(self, message, level="INFO"):
        """Log a message to both the logger and UI if available"""
        # Log to file
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        
        # Log to UI if callback is available
        if self.log_message_callback:
            self.log_message_callback(message, level)
        
    def create_interface(self):
        """Create the alert testing interface"""
        # Main frame
        self.main_frame = ttk.Frame(self.parent_frame)
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Title and instructions
        title_label = ttk.Label(
            self.main_frame,
            text="Email Alert Testing",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        instructions = (
            "Use the buttons below to test email alerts for different owl activities. "
            "Each test will generate a real email alert with 'TEST:' in the subject. "
            "Test results will appear in the Owl Monitor Log."
        )
        
        instruction_label = ttk.Label(
            self.main_frame,
            text=instructions,
            wraplength=500,
            justify="center"
        )
        instruction_label.pack(pady=(0, 20))
        
        # Test alert buttons in a grid layout
        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.pack(pady=10)
        
        # Alert types to test
        alert_types = [
            "Owl In Box",
            "Owl On Box", 
            "Owl In Area",
            "Two Owls",
            "Two Owls In Box"
        ]
        
        # Create buttons in a grid - 3 columns
        self.alert_buttons = {}
        
        for i, alert_type in enumerate(alert_types):
            row, col = divmod(i, 3)
            button_frame = ttk.Frame(self.buttons_frame)
            button_frame.grid(row=row, column=col, padx=10, pady=10)
            
            # Button with test action
            button = ttk.Button(
                button_frame,
                text=f"Test {alert_type}",
                command=lambda t=alert_type: self.run_test_alert(t),
                width=15
            )
            button.pack()
            
            # Status label below button
            status_var = tk.StringVar(value="Ready")
            status_label = ttk.Label(
                button_frame,
                textvariable=status_var,
                font=("Arial", 8),
                foreground="gray"
            )
            status_label.pack(pady=(3, 0))
            
            # Store references to button and status
            self.alert_buttons[alert_type] = {
                "button": button,
                "status_var": status_var,
                "status_label": status_label
            }
        
        # Progress indicator
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill="x", pady=15)
        
        self.status_var = tk.StringVar(value="Ready to run tests")
        status_label = ttk.Label(
            self.progress_frame,
            textvariable=self.status_var,
            font=("Arial", 10, "italic")
        )
        status_label.pack(side=tk.LEFT)
        
        # Progress bar - hidden initially
        self.progress = ttk.Progressbar(
            self.progress_frame,
            mode="indeterminate",
            length=200
        )
        # Don't pack initially - will be shown during test
        
        # Information about email alerts
        info_frame = ttk.LabelFrame(self.main_frame, text="About Email Alerts")
        info_frame.pack(fill="x", pady=10, padx=20)
        
        info_text = (
            "Email alerts are sent to all subscribers who have selected to "
            "receive alerts for the specific owl location. Test alerts include "
            "'TEST:' in the subject line and will not trigger cooldown periods "
            "for real alerts."
        )
        
        info_label = ttk.Label(
            info_frame,
            text=info_text,
            wraplength=480,
            justify="left",
            padding=10
        )
        info_label.pack()

    def run_test_alert(self, alert_type):
        """Run a test alert for the specified alert type"""
        # Prevent running multiple tests simultaneously
        if self.test_in_progress:
            self.log_message("Test already in progress, please wait", "WARNING")
            return
            
        self.test_in_progress = True
        
        # Update UI to show test in progress
        self.status_var.set(f"Running test for {alert_type}...")
        
        # Update specific button status
        button_info = self.alert_buttons[alert_type]
        button_info["status_var"].set("Testing...")
        button_info["status_label"].config(foreground="blue")
        button_info["button"].config(state=tk.DISABLED)
        
        # Show progress bar
        self.progress.pack(side=tk.RIGHT, padx=10)
        self.progress.start(10)
        
        # Disable all buttons during test
        for info in self.alert_buttons.values():
            info["button"].config(state=tk.DISABLED)
        
        # Log the test start
        self.log_message(f"Starting test alert for {alert_type}", "INFO")
        
        # Run test in separate thread to avoid blocking UI
        threading.Thread(
            target=self._process_test_alert,
            args=(alert_type,),
            daemon=True
        ).start()
        
    def _process_test_alert(self, alert_type):
        """Process the test alert in a background thread"""
        try:
            # Get corresponding camera name for this alert type
            camera_name = self._get_camera_for_alert_type(alert_type)
            
            if not camera_name:
                self.log_message(f"No camera found for alert type: {alert_type}", "ERROR")
                self._update_test_status(alert_type, False, "No camera found")
                return
                
            # Create test detection result
            detection_result = self._create_test_detection(camera_name, alert_type)
            
            # Log the test details
            self.log_message(
                f"Sending test {alert_type} alert using camera {camera_name}",
                "INFO"
            )
            
            # Use alert_manager to process the test alert
            # Important: Set is_test=True to ensure it's processed as a test
            start_time = time.time()
            
            # Process detection with is_test=True flag
            result = self.alert_manager.process_detection(
                camera_name=camera_name,
                detection_result=detection_result,
                is_test=True
            )
            
            # Add short delay to allow alert processing to complete
            # and to give user visual feedback about processing
            elapsed = time.time() - start_time
            if elapsed < 2:  # Ensure at least 2 seconds of visual feedback
                time.sleep(2 - elapsed)
                
            # Check result and update status
            if result:
                self.log_message(f"Test alert for {alert_type} sent successfully", "INFO")
                self._update_test_status(alert_type, True)
            else:
                self.log_message(f"Failed to send test alert for {alert_type}", "WARNING")
                self._update_test_status(alert_type, False, "Failed to send")
                
        except Exception as e:
            error_msg = f"Error processing test alert for {alert_type}: {e}"
            self.log_message(error_msg, "ERROR")
            self._update_test_status(alert_type, False, "Error")
        finally:
            # Always clean up UI state
            self.parent_frame.after(0, self._reset_ui_state)
                
    def _update_test_status(self, alert_type, success, error_msg=None):
        """Update the UI with test results"""
        def update():
            button_info = self.alert_buttons[alert_type]
            
            if success:
                button_info["status_var"].set("Success!")
                button_info["status_label"].config(foreground="green")
            else:
                button_info["status_var"].set(error_msg or "Failed")
                button_info["status_label"].config(foreground="red")
                
            button_info["button"].config(state=tk.NORMAL)
            
        # Schedule update on main thread
        self.parent_frame.after(0, update)
    
    def _reset_ui_state(self):
        """Reset the UI state after test completes"""
        # Stop progress bar
        self.progress.stop()
        self.progress.pack_forget()
        
        # Enable all buttons
        for info in self.alert_buttons.values():
            info["button"].config(state=tk.NORMAL)
            
        # Update status
        self.status_var.set("Ready to run tests")
        
        # Reset test in progress flag
        self.test_in_progress = False
    
    def _get_camera_for_alert_type(self, alert_type):
        """Find a camera that corresponds to the given alert type"""
        for camera, camera_alert_type in CAMERA_MAPPINGS.items():
            if camera_alert_type == alert_type:
                return camera
                
        # Special case for alerts that don't have direct camera mappings
        if alert_type == "Two Owls":
            # Use Upper Patio Camera for general area owl detection
            return "Upper Patio Camera"
        elif alert_type == "Two Owls In Box":
            # Use Wyze camera for in-box detection
            return "Wyze Internal Camera"
                
        return None
    
    def _create_test_detection(self, camera_name, alert_type):
        """Create a test detection result for the specified camera and alert type"""
        # Create a detection result with high confidence to ensure it triggers an alert
        detection_result = {
            "camera": camera_name,
            "status": alert_type,
            "is_owl_present": True,
            "is_test": True,  # Explicitly mark as test
            "pixel_change": 50.0,
            "luminance_change": 45.0,
            "owl_confidence": 90.0,  # High confidence for test
            "consecutive_owl_frames": 3,
            "confidence_factors": {
                "shape_confidence": 35.0,
                "motion_confidence": 30.0, 
                "temporal_confidence": 15.0,
                "camera_confidence": 10.0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Add multiple owls flag for Two Owls alerts
        if alert_type in ["Two Owls", "Two Owls In Box"]:
            detection_result["multiple_owls"] = True
            detection_result["owl_count"] = 2
            
        return detection_result


# For testing the interface independently
if __name__ == "__main__":
    # Create test window
    root = tk.Tk()
    root.title("Test Interface")
    root.geometry("600x500")
    
    # Create frame for test interface
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    
    # Create logger
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    
    # Create a mock alert manager for testing
    class MockAlertManager:
        def process_detection(self, camera_name, detection_result, is_test=False):
            print(f"Mock alert sent: {detection_result['status']} from {camera_name}")
            print(f"Test mode: {is_test}")
            # Simulate processing time
            time.sleep(1)
            return True
    
    # Create the test interface
    test_interface = TestInterface(frame, logger, MockAlertManager())
    
    # Add a simple log display for testing
    log_frame = ttk.LabelFrame(root, text="Test Log")
    log_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    log_text = tk.Text(log_frame, height=10)
    log_text.pack(fill="both", expand=True)
    
    # Mock log_message function
    def log_message(message, level="INFO"):
        log_text.insert(tk.END, f"[{level}] {message}\n")
        log_text.see(tk.END)
    
    # Connect the log function
    test_interface.set_log_callback(log_message)
    
    # Start the main loop
    root.mainloop()