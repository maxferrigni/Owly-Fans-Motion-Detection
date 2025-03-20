# File: scripts/front_end_components/settings_tab.py
# Purpose: Settings tab component for the Owl Monitoring System GUI
# 
# March 19, 2025 Update - Version 1.4.6
# - Added day/night settings toggle
# - Removed outdated confidence threshold guidance text
# - Streamlined UI for better space utilization

import tkinter as tk
from tkinter import ttk
from utilities.logging_utils import get_logger
from motion_detection_settings import MotionDetectionSettings


class SettingsTab(ttk.Frame):
    """Tab containing settings interface for the application"""
    
    def __init__(self, parent, app_reference):
        """
        Initialize Settings Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        
        # Create scrollable frame for settings
        settings_scroll = ttk.Frame(self)
        settings_scroll.pack(fill="both", expand=True)
        
        # Initialize the motion detection settings component
        self.settings = MotionDetectionSettings(settings_scroll, self.logger)

        # Pack self into parent container
        self.pack(fill="both", expand=True)
        
    def get_confidence_thresholds(self):
        """Proxy method to access confidence thresholds from settings"""
        if hasattr(self.settings, 'get_confidence_thresholds'):
            return self.settings.get_confidence_thresholds()
        return {}
        
    def validate_config_files(self):
        """Validate configuration files when tab is activated"""
        if hasattr(self.settings, 'validate_config_files'):
            return self.settings.validate_config_files()
        return True