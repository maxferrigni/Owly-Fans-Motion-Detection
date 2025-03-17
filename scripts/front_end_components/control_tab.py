# File: scripts/front_end_components/control_tab.py
# Purpose: Control tab component for the Owl Monitoring System GUI
# 
# March 17, 2025 Update - Version 1.4.1
# - Extracted from front_end_app.py and front_end_panels.py
# - Centralized control tab functionality

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import threading

from utilities.logging_utils import get_logger

class ControlTab(ttk.Frame):
    """Tab containing control interface for the application"""
    
    def __init__(self, parent, app_reference):
        """
        Initialize Control Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        
        # Create the control panel
        self.control_panel = ControlPanel(
            self,
            self.app.local_saving_enabled,
            self.app.capture_interval,
            self.app.alert_delay,
            self.app.email_alerts_enabled,
            self.app.update_system,
            self.app.start_script,
            self.app.stop_script,
            self.app.toggle_local_saving,
            self.app.update_capture_interval,
            self.app.update_alert_delay,
            self.app.toggle_email_alerts,
            self.app.log_window,
            self.app.clear_local_images
        )
        self.control_panel.pack(fill="both", expand=True)
        
    def update_run_state(self, is_running):
        """Update run state in the control panel"""
        self.control_panel.update_run_state(is_running)


class ControlPanel(ttk.Frame):
    """Panel for controlling the application - Moved from front_end_panels.py"""
    def __init__(self, parent, local_saving_enabled, capture_interval, alert_delay,
                 email_alerts_enabled, update_system_func, start_script_func,
                 stop_script_func, toggle_local_saving_func, update_capture_interval_func,
                 update_alert_delay_func, toggle_email_alerts_func, log_window,
                 clear_local_images_func):
        super().__init__(parent)
        
        self.local_saving_enabled = local_saving_enabled
        self.capture_interval = capture_interval
        self.alert_delay = alert_delay
        self.email_alerts_enabled = email_alerts_enabled
        
        # Store callback functions
        self.update_system_func = update_system_func
        self.start_script_func = start_script_func
        self.stop_script_func = stop_script_func
        self.toggle_local_saving_func = toggle_local_saving_func
        self.update_capture_interval_func = update_capture_interval_func
        self.update_alert_delay_func = update_alert_delay_func
        self.toggle_email_alerts_func = toggle_email_alerts_func
        self.log_window = log_window
        self.clear_local_images_func = clear_local_images_func
        
        # Create UI components
        self.create_control_interface()
        
    def create_control_interface(self):
        """Create simplified control interface components"""
        # Main controls frame
        main_controls = ttk.LabelFrame(self, text="Motion Detection Controls")
        main_controls.pack(padx=5, pady=5, fill="x")
        
        # Script control buttons
        button_frame = ttk.Frame(main_controls)
        button_frame.pack(pady=5, fill="x")
        
        self.start_button = ttk.Button(
            button_frame,
            text="Start Detection",
            command=self.start_script_func
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Detection",
            command=self.stop_script_func,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system_func
        )
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        # Update to use the dedicated callback function
        self.clear_images_button = ttk.Button(
            button_frame,
            text="Clear Images",
            command=self.clear_local_images_func
        )
        self.clear_images_button.pack(side=tk.LEFT, padx=5)
        
        # View logs button
        self.view_logs_button = ttk.Button(
            button_frame,
            text="View Logs",
            command=self.show_logs
        )
        self.view_logs_button.pack(side=tk.RIGHT, padx=5)
        
        # Combined Settings section (merged settings and alert settings)
        settings_frame = ttk.LabelFrame(self, text="Settings")
        settings_frame.pack(padx=5, pady=5, fill="x")
        
        # Create settings controls
        setting_controls = ttk.Frame(settings_frame)
        setting_controls.pack(pady=5, fill="x")
        
        # Local saving checkbox
        local_saving_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Local Image Saving",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving_func
        )
        local_saving_cb.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Capture interval
        interval_frame = ttk.Frame(setting_controls)
        interval_frame.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(interval_frame, text="Capture Interval (sec):").pack(side=tk.LEFT)
        
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            width=5,
            textvariable=self.capture_interval,
            command=self.update_capture_interval_func
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Alert delay
        delay_frame = ttk.Frame(setting_controls)
        delay_frame.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(delay_frame, text="Alert Delay (min):").pack(side=tk.LEFT)
        
        delay_spinner = ttk.Spinbox(
            delay_frame,
            from_=5,
            to=120,
            width=5,
            textvariable=self.alert_delay,
            command=self.update_alert_delay_func
        )
        delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Email alerts checkbox (only remaining alert type)
        email_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_func
        )
        email_cb.grid(row=3, column=0, sticky="w", padx=5, pady=2)
    
    def show_logs(self):
        """Show the log window"""
        if hasattr(self.log_window, 'show'):
            self.log_window.show()
    
    def update_run_state(self, is_running):
        """Update UI based on whether the script is running"""
        if is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)