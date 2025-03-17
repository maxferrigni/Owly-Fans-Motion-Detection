# File: scripts/front_end_components/monitor_tab.py
# Purpose: System monitoring tab component for the Owl Monitoring System GUI
# 
# March 17, 2025 Update - Version 1.4.1
# - Extracted from front_end_app.py and front_end_panels.py
# - Centralized system monitoring functionality

import tkinter as tk
from tkinter import ttk
from utilities.logging_utils import get_logger


class MonitorTab(ttk.Frame):
    """Tab containing system monitoring interface for the application"""
    
    def __init__(self, parent, app_reference):
        """
        Initialize Monitor Tab
        
        Args:
            parent (ttk.Frame): Parent frame (typically the notebook tab)
            app_reference: Reference to the main application for callbacks
        """
        super().__init__(parent)
        self.parent = parent
        self.app = app_reference
        self.logger = get_logger()
        
        # Create the system monitor panel
        self.sys_monitor = SysMonitorPanel(self)
        self.sys_monitor.pack(fill="both", expand=True)


class SysMonitorPanel(ttk.Frame):
    """
    Placeholder panel for system monitoring.
    Moved from front_end_panels.py
    """
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create simple placeholder content
        self.create_placeholder()
        
    def create_placeholder(self):
        """Create placeholder content"""
        # Center content
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add placeholder text
        placeholder_label = ttk.Label(
            main_frame,
            text="System Monitoring Coming Soon",
            font=("Arial", 14, "bold")
        )
        placeholder_label.pack(pady=20)
        
        details_label = ttk.Label(
            main_frame,
            text="This tab will contain system monitoring features in a future update.",
            wraplength=600
        )
        details_label.pack(pady=10)
        
        # Add some placeholder stats
        stats_frame = ttk.LabelFrame(main_frame, text="Future Monitoring Features")
        stats_frame.pack(fill="x", pady=20, padx=10)
        
        features = [
            "Camera Feed Status",
            "System Resource Usage",
            "Network Connectivity",
            "Storage Space",
            "Alert History"
        ]
        
        for feature in features:
            ttk.Label(stats_frame, text=f"• {feature}").pack(anchor="w", padx=10, pady=2)