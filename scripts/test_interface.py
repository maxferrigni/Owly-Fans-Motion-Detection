# File: test_interface.py
# Purpose: Simplified email testing interface for the Owl Monitoring System
# Version: 1.5.3

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS

class TestInterface:
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        
        # Create the simplified test interface
        self.create_interface()
        
    def create_interface(self):
        """Create simplified email testing interface"""
        # Email testing section
        self.email_frame = ttk.LabelFrame(self.parent_frame, text="Email Alert Testing")
        self.email_frame.pack(pady=10, fill="x", padx=10)
        
        # Create simple instruction text
        instruction_label = ttk.Label(
            self.email_frame,
            text="Use the buttons below to test email alerts. Results will appear in the Owl Monitor Log.",
            wraplength=500
        )
        instruction_label.pack(pady=10, padx=10)
        
        # Create button grid for different alert types
        button_frame = ttk.Frame(self.email_frame)
        button_frame.pack(pady=10, padx=10)
        
        # Create buttons for each alert type
        self.alert_buttons = {}
        alert_types = [
            "Owl In Box",
            "Owl On Box", 
            "Owl In Area",
            "Two Owls",
            "Two Owls In Box"
        ]
        
        # Create a grid of buttons - 3 buttons per row
        for i, alert_type in enumerate(alert_types):
            row, col = divmod(i, 3)
            
            self.alert_buttons[alert_type] = ttk.Button(
                button_frame,
                text=f"Test {alert_type}",
                command=lambda t=alert_type: self.trigger_test_alert(t),
                width=15
            )
            self.alert_buttons[alert_type].grid(
                row=row, 
                column=col, 
                padx=5, 
                pady=5, 
                sticky="w"
            )
        
        # Add a status label
        self.status_var = tk.StringVar(value="Ready to send test alerts")
        status_label = ttk.Label(
            self.email_frame,
            textvariable=self.status_var,
            font=("Arial", 10, "italic")
        )
        status_label.pack(pady=10, padx=10)

    def trigger_test_alert(self, alert_type):
        """Trigger a test email alert"""
        try:
            # Disable buttons during processing to prevent double clicks
            for btn in self.alert_buttons.values():
                btn.config(state=tk.DISABLED)
                
            # Update status
            self.status_var.set(f"Sending {alert_type} test alert...")
            
            # Update UI immediately
            self.parent_frame.update_idletasks()
            
            self.logger.info(f"Sending test email alert: {alert_type}")
            
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
                "owl_confidence": 75.0,
                "consecutive_owl_frames": 3
            }
            
            # Process test alert - set is_test=True to bypass confidence checks
            alert_sent = self.alert_manager.process_detection(
                camera_name,
                detection_result,
                is_test=True
            )
            
            # Log the result to the main log
            if alert_sent:
                self.logger.info(f"Test alert for {alert_type} sent successfully")
                self.status_var.set(f"Test alert for {alert_type} sent successfully")
            else:
                self.logger.warning(f"Test alert for {alert_type} was not sent (blocked by rules)")
                self.status_var.set(f"Test alert for {alert_type} was not sent")
                
        except Exception as e:
            error_msg = f"Error sending test alert for {alert_type}: {e}"
            self.logger.error(error_msg)
            self.status_var.set(f"Error: {str(e)[:50]}...")
        finally:
            # Re-enable buttons after short delay
            threading.Timer(2.0, self.enable_buttons).start()
    
    def enable_buttons(self):
        """Re-enable all buttons after alert processing"""
        for btn in self.alert_buttons.values():
            btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    # Create a test window
    root = tk.Tk()
    root.title("Test Interface")
    root.geometry("600x400")
    
    # Create a frame to hold the test interface
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    
    # Create a mock logger
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    
    # Create a mock alert manager
    class MockAlertManager:
        def process_detection(self, camera_name, detection_result, is_test=False):
            print(f"Mock alert sent: {detection_result['status']}")
            return True
    
    # Create the test interface
    test_interface = TestInterface(frame, logger, MockAlertManager())
    
    # Start the main loop
    root.mainloop()