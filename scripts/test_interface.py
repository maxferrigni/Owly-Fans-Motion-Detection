# File: test_interface.py
# Purpose: Handle test mode functionality for the Owl Monitoring System

import tkinter as tk
from utilities.logging_utils import get_logger
from utilities.constants import CAMERA_MAPPINGS

class TestInterface:
    def __init__(self, parent_frame, logger, alert_manager):
        self.parent_frame = parent_frame
        self.logger = logger or get_logger()
        self.alert_manager = alert_manager
        self.test_mode = False
        self.active_test_button = None

        # Create frames
        self.test_mode_frame = tk.Frame(self.parent_frame)
        self.test_mode_frame.pack(pady=5)
        
        self.test_buttons_frame = tk.Frame(self.test_mode_frame)
        
        # Create alert status label
        self.alert_status = tk.Label(
            self.parent_frame,
            text="",
            fg='red',
            font=('Arial', 14, 'bold')
        )
        self.alert_status.place(relx=0.7, rely=0.05)

        self._create_test_interface()

    def _create_test_interface(self):
        """Create test mode interface elements"""
        # Test Mode toggle button
        self.test_mode_button = tk.Button(
            self.test_mode_frame,
            text="Enter Test Mode",
            command=self.toggle_test_mode,
            width=20,
            bg='yellow',
            activebackground='khaki',
            font=('Arial', 10)
        )
        self.test_mode_button.pack(side=tk.LEFT, padx=5)

        # Style configuration for test buttons
        button_style = {
            "width": 18,
            "relief": "raised",
            "bd": 2,
            "font": ('Arial', 10),
            "state": "normal"
        }

        self.test_buttons = {
            "Owl In Box": tk.Button(
                self.test_buttons_frame,
                text="Test Owl In Box",
                command=lambda: self.trigger_test_alert("Owl In Box"),
                bg='#ADD8E6',  # Light blue
                activebackground='#87CEEB',  # Sky blue
                **button_style
            ),
            "Owl On Box": tk.Button(
                self.test_buttons_frame,
                text="Test Owl On Box",
                command=lambda: self.trigger_test_alert("Owl On Box"),
                bg='#90EE90',  # Light green
                activebackground='#98FB98',  # Pale green
                **button_style
            ),
            "Owl In Area": tk.Button(
                self.test_buttons_frame,
                text="Test Owl In Area",
                command=lambda: self.trigger_test_alert("Owl In Area"),
                bg='#FFFFE0',  # Light yellow
                activebackground='#F0E68C',  # Khaki
                **button_style
            )
        }

        for btn in self.test_buttons.values():
            btn.pack(side=tk.LEFT, padx=10)
            btn.bind('<Enter>', lambda e, b=btn: self._on_button_hover(b, True))
            btn.bind('<Leave>', lambda e, b=btn: self._on_button_hover(b, False))
            btn.bind('<Button-1>', lambda e, b=btn: self._on_button_press(b))
            btn.bind('<ButtonRelease-1>', lambda e, b=btn: self._on_button_release(b))

    def _on_button_hover(self, button, entering):
        """Handle button hover effects"""
        if entering:
            button.config(relief="groove")
        else:
            button.config(relief="raised")

    def _on_button_press(self, button):
        """Handle button press effects"""
        self.active_test_button = button
        button.config(relief="sunken")
        # Darken the button color temporarily
        orig_color = button.cget('bg')
        button.config(bg=button.cget('activebackground'))
        # Schedule release effect
        self.parent_frame.after(200, lambda: self._button_release_effect(button, orig_color))

    def _button_release_effect(self, button, orig_color):
        """Handle button release effects"""
        if button == self.active_test_button:
            button.config(relief="raised", bg=orig_color)
            self.active_test_button = None

    def toggle_test_mode(self):
        """Toggle test mode on/off"""
        self.test_mode = not self.test_mode
        if self.test_mode:
            self.test_mode_button.config(
                text="Exit Test Mode",
                bg='orange',
                activebackground='darkorange'
            )
            self.test_buttons_frame.pack(side=tk.LEFT)
            self.logger.info("Test Mode Activated")
        else:
            self.test_mode_button.config(
                text="Enter Test Mode",
                bg='yellow',
                activebackground='khaki'
            )
            self.test_buttons_frame.pack_forget()
            self.alert_status.config(text="")
            self.logger.info("Test Mode Deactivated")

    def trigger_test_alert(self, alert_type):
        """Trigger a test alert with visual feedback"""
        try:
            # Visual feedback - flash the button
            button = self.test_buttons[alert_type]
            orig_bg = button.cget('bg')
            button.config(bg='white')
            self.parent_frame.after(100, lambda: button.config(bg=orig_bg))
            
            self.logger.info(f"Triggering test alert: {alert_type}")
            self.alert_status.config(text=alert_type)

            # Get camera name for this alert type
            camera_name = next(
                (name for name, type_ in CAMERA_MAPPINGS.items() 
                 if type_ == alert_type),
                "Test Camera"
            )

            # Create simulated detection result
            detection_result = {
                "status": alert_type,
                "pixel_change": 50.0,
                "luminance_change": 40.0,
                "snapshot_path": "",
                "lighting_condition": "day",
                "detection_info": {
                    "confidence": 0.8,
                    "is_test": True,
                    "test_camera": camera_name
                }
            }

            # Process test alert
            alert_sent = self.alert_manager.process_detection(camera_name, detection_result)
            
            if alert_sent:
                self.logger.info(f"Test alert sent: {alert_type}")
            else:
                self.logger.info(f"Test alert blocked by delay: {alert_type}")

        except Exception as e:
            self.logger.error(f"Error triggering test alert: {e}")