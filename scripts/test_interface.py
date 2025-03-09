# File: test_interface.py
# Purpose: Simplified test interface for email alerts only
# Version: 1.5.3 - Removed image testing functionality

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS

class TestInterface:
    """
    Simplified test interface focused solely on email alert testing.
    Image testing functionality has been removed for stability in v1.5.3.
    """
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        
        # Create the simplified test interface
        self.create_interface()
        
    def create_interface(self):
        """Create email testing interface"""
        # Create title frame with information
        title_frame = ttk.LabelFrame(self.parent_frame, text="Email Alert Testing")
        title_frame.pack(pady=10, padx=10, fill="x")
        
        info_text = (
            "This panel allows you to test the email alert functionality.\n"
            "Select an alert type and click 'Send Test Alert' to verify that emails are working correctly.\n"
            "NOTE: In v1.5.3, image testing functionality has been removed for stability."
        )
        
        info_label = ttk.Label(
            title_frame,
            text=info_text,
            wraplength=600,
            justify="left",
            padding=(10, 10)
        )
        info_label.pack(fill="x")
        
        # Alert selection frame
        selection_frame = ttk.LabelFrame(self.parent_frame, text="Select Alert Type")
        selection_frame.pack(pady=10, padx=10, fill="x")
        
        # Use radio buttons for alert type selection
        self.alert_type_var = tk.StringVar(value="Owl In Box")
        
        for alert_type in ["Owl In Box", "Owl On Box", "Owl In Area", "Two Owls", "Two Owls In Box"]:
            ttk.Radiobutton(
                selection_frame,
                text=alert_type,
                value=alert_type,
                variable=self.alert_type_var
            ).pack(anchor="w", padx=20, pady=5)
        
        # Email test controls
        control_frame = ttk.Frame(self.parent_frame)
        control_frame.pack(pady=20, padx=10, fill="x")
        
        # Send test button
        self.test_button = ttk.Button(
            control_frame,
            text="Send Test Alert",
            command=self.send_test_alert,
            width=20
        )
        self.test_button.pack(side=tk.LEFT, padx=10)
        
        # Status indicator
        self.status_var = tk.StringVar(value="Ready to test")
        self.status_label = ttk.Label(
            control_frame,
            textvariable=self.status_var,
            font=("Arial", 10, "italic")
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Results frame
        self.results_frame = ttk.LabelFrame(self.parent_frame, text="Test Results")
        self.results_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Result log with scrollbar
        self.result_text = tk.Text(
            self.results_frame,
            height=10,
            width=80,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        scrollbar = ttk.Scrollbar(self.results_frame, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add initial message
        self.log_result("Email test system ready. Select an alert type and click 'Send Test Alert'.")
    
    def send_test_alert(self):
        """Send a test alert email"""
        # Disable the button during processing
        self.test_button.config(state=tk.DISABLED)
        self.status_var.set("Sending test alert...")
        
        # Get selected alert type
        alert_type = self.alert_type_var.get()
        
        # Log the action
        self.log_result(f"Starting test for alert type: {alert_type}")
        
        # Process in a background thread to keep UI responsive
        threading.Thread(target=self._process_test_alert, args=(alert_type,), daemon=True).start()
    
    def _process_test_alert(self, alert_type):
        """Process the test alert in a background thread"""
        try:
            # Get camera name for this alert type
            camera_name = next(
                (name for name, type_ in CAMERA_MAPPINGS.items() 
                if type_ == alert_type),
                "Test Camera"
            )
            
            # Create simulated detection result
            detection_result = {
                "camera": camera_name,
                "status": alert_type,
                "is_owl_present": True,
                "motion_detected": True,
                "pixel_change": 50.0,
                "luminance_change": 40.0,
                "snapshot_path": "",
                "timestamp": "2025-03-08T12:00:00-08:00",
                "owl_confidence": 75.0,
                "consecutive_owl_frames": 3,
                "threshold_used": 60.0,
                "confidence_factors": {}
            }
            
            # Send test alert - is_test=True to bypass confidence checks and cooldowns
            alert_sent = self.alert_manager.process_detection(
                camera_name,
                detection_result,
                is_test=True
            )
            
            # Log result on the UI thread
            self.parent_frame.after(100, self._update_ui, alert_sent, alert_type)
            
        except Exception as e:
            self.logger.error(f"Error sending test alert: {e}")
            # Update UI on the main thread
            self.parent_frame.after(100, self._update_ui_error, str(e))
    
    def _update_ui(self, alert_sent, alert_type):
        """Update UI after test alert processing (called on UI thread)"""
        if alert_sent:
            self.status_var.set("Test alert sent successfully")
            self.log_result(f"SUCCESS: Test alert for {alert_type} sent!")
            self.log_result("Check your email for the test alert message.")
        else:
            self.status_var.set("Test alert failed")
            self.log_result(f"ERROR: Failed to send test alert for {alert_type}.")
            self.log_result("Check logs for more information.")
        
        # Re-enable the button
        self.test_button.config(state=tk.NORMAL)
    
    def _update_ui_error(self, error_message):
        """Update UI after an error (called on UI thread)"""
        self.status_var.set("Error sending test alert")
        self.log_result(f"ERROR: {error_message}")
        
        # Re-enable the button
        self.test_button.config(state=tk.NORMAL)
    
    def log_result(self, message):
        """Add a message to the result log"""
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
        self.logger.info(message)


if __name__ == "__main__":
    # Test code
    root = tk.Tk()
    root.title("Test Interface")
    
    # Create a mock alert manager for testing
    class MockAlertManager:
        def process_detection(self, camera_name, detection_result, is_test=False):
            print(f"Mock alert for {camera_name}: {detection_result['status']}")
            return True
    
    # Create logger
    logger = get_logger()
    
    # Create test interface
    interface = TestInterface(root, logger, MockAlertManager())
    
    root.mainloop()