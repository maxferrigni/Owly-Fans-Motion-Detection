# File: scripts/front_end_components/test_tab.py
# Purpose: Test tab component for the Owl Monitoring System GUI
# 
# March 17, 2025 Update - Version 1.4.1
# - Extracted from front_end_app.py
# - Centralized testing interface functionality

import tkinter as tk
from tkinter import ttk
from utilities.logging_utils import get_logger
from test_interface import TestInterface


class TestTab(ttk.Frame):
    """Tab containing testing interface for the application"""
    
    def __init__(self, parent, app_reference):
        """
        Initialize Test Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        
        # Create scrollable frame for test interface
        test_scroll = ttk.Frame(self)
        test_scroll.pack(fill="both", expand=True)
        
        # Initialize the test interface
        self.test_interface = TestInterface(test_scroll, self.logger, self.app.alert_manager)
        
    def reset_frame_history(self):
        """Reset detection frame history"""
        if hasattr(self.test_interface, 'reset_frame_history'):
            self.test_interface.reset_frame_history()
            
    def log_message(self, message):
        """Proxy method to log messages through the test interface"""
        if hasattr(self.test_interface, 'log_message'):
            self.test_interface.log_message(message)
        else:
            self.logger.info(message)