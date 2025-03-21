# File: scripts/front_end_components/monitor_tab.py
# Purpose: System monitoring tab component for the Owl Monitoring System GUI
# 
# March 20, 2025 Update - Version 1.4.7.1
# - Added OBS Stream status monitoring
# - Added status display with auto-refresh
# - Added manual check button for OBS status
# - Enhanced UI with status indicators

import tkinter as tk
from tkinter import ttk
import time
import threading
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

        # Pack self into parent container
        self.pack(fill="both", expand=True)
        
    def refresh_status(self):
        """Refresh all system status information"""
        if hasattr(self.sys_monitor, 'refresh_status'):
            self.sys_monitor.refresh_status()


class SysMonitorPanel(ttk.Frame):
    """
    System monitoring panel with OBS status display.
    Updated in v1.4.7.1 to include OBS stream monitoring.
    """
    def __init__(self, parent):
        super().__init__(parent)
        
        # Store reference to parent for callbacks
        self.parent = parent
        self.logger = get_logger()
        
        # Status tracking
        self.obs_status = {
            'is_running': False,
            'last_check_time': None,
            'error_count': 0,
            'cooldown_active': False,
            'cooldown_remaining': 0
        }
        
        # Initialize UI with auto-refresh
        self.create_monitor_ui()
        self.start_auto_refresh()
        
    def create_monitor_ui(self):
        """Create system monitoring UI components"""
        # Create scrollable container for all monitoring components
        self.create_scrollable_container()
        
        # Add title and description
        title_label = ttk.Label(
            self.main_frame,
            text="System Monitoring",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(20, 10))
        
        description_label = ttk.Label(
            self.main_frame,
            text="Monitor and troubleshoot system components",
            wraplength=600
        )
        description_label.pack(pady=(0, 20))
        
        # Create OBS monitoring section
        self.create_obs_monitor_section()
        
        # Create Wyze camera monitoring section (placeholder)
        self.create_camera_monitor_section()
        
        # Create general system info section (placeholder)
        self.create_system_info_section()
        
        # Add refresh controls
        refresh_frame = ttk.Frame(self.main_frame)
        refresh_frame.pack(fill="x", pady=20, padx=10)
        
        # Last refreshed label
        self.last_refreshed_label = ttk.Label(
            refresh_frame,
            text="Last refreshed: Never",
            font=("Arial", 8),
            foreground="gray"
        )
        self.last_refreshed_label.pack(side=tk.LEFT, padx=5)
        
        # Manual refresh button
        self.refresh_button = ttk.Button(
            refresh_frame,
            text="Refresh Now",
            command=self.refresh_status
        )
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
    
    def create_scrollable_container(self):
        """Create scrollable container for monitoring components"""
        # Create a canvas with scrollbar
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create main frame inside canvas for content
        self.main_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        # Configure canvas to resize with window
        self.bind("<Configure>", self.on_canvas_configure)
        self.main_frame.bind("<Configure>", self.on_frame_configure)
    
    def on_canvas_configure(self, event):
        """Handle canvas resize events"""
        # Update the inner frame's width to match the canvas
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def on_frame_configure(self, event):
        """Update the scrollregion when the inner frame changes size"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def create_obs_monitor_section(self):
        """Create the OBS monitoring section"""
        # Create OBS status frame
        obs_frame = ttk.LabelFrame(self.main_frame, text="OBS Stream Status")
        obs_frame.pack(fill="x", pady=10, padx=10)
        
        # Add status display
        status_frame = ttk.Frame(obs_frame)
        status_frame.pack(fill="x", pady=5, padx=5)
        
        # Status indicator
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.obs_status_label = ttk.Label(
            status_frame,
            text="Checking...",
            font=("Arial", 10, "bold")
        )
        self.obs_status_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        # Last check time
        ttk.Label(status_frame, text="Last Check:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.obs_check_time_label = ttk.Label(
            status_frame,
            text="Never",
            font=("Arial", 9)
        )
        self.obs_check_time_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Alert status
        ttk.Label(status_frame, text="Alert Status:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.obs_alert_status_label = ttk.Label(
            status_frame,
            text="No alerts sent",
            font=("Arial", 9)
        )
        self.obs_alert_status_label.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # Add check now button
        button_frame = ttk.Frame(obs_frame)
        button_frame.pack(fill="x", pady=10, padx=5)
        
        self.check_obs_button = ttk.Button(
            button_frame,
            text="Check OBS Status Now",
            command=self.check_obs_status
        )
        self.check_obs_button.pack(side=tk.LEFT, padx=5)
        
        # Add status history display (placeholder)
        history_frame = ttk.Frame(obs_frame)
        history_frame.pack(fill="x", pady=5, padx=5)
        
        ttk.Label(
            history_frame,
            text="Status History:",
            font=("Arial", 9, "italic")
        ).pack(anchor="w", padx=5, pady=2)
        
        self.obs_history_text = tk.Text(
            history_frame,
            height=3,
            width=50,
            wrap=tk.WORD,
            font=("Consolas", 8),
            state=tk.DISABLED
        )
        self.obs_history_text.pack(fill="x", padx=5, pady=5)
    
    def create_camera_monitor_section(self):
        """Create the camera monitoring section (placeholder)"""
        camera_frame = ttk.LabelFrame(self.main_frame, text="Wyze Camera Monitor")
        camera_frame.pack(fill="x", pady=10, padx=10)
        
        ttk.Label(
            camera_frame,
            text="Camera monitoring feature coming in future updates",
            font=("Arial", 9),
            foreground="gray"
        ).pack(pady=10, padx=10)
        
        # Features list
        features = [
            "Camera Feed Status",
            "Connection Health",
            "Frame Rate Monitoring",
            "Automatic Recovery"
        ]
        
        for feature in features:
            ttk.Label(camera_frame, text=f"• {feature}").pack(anchor="w", padx=10, pady=2)
    
    def create_system_info_section(self):
        """Create the system info section (placeholder)"""
        system_frame = ttk.LabelFrame(self.main_frame, text="System Information")
        system_frame.pack(fill="x", pady=10, padx=10)
        
        # System statistics placeholders
        stats_frame = ttk.Frame(system_frame)
        stats_frame.pack(fill="x", pady=5)
        
        # Create a 2x3 grid of statistics
        stats = [
            ("Uptime", "0d 0h 0m"),
            ("Memory Usage", "0%"),
            ("CPU Usage", "0%"),
            ("Storage Free", "0 GB"),
            ("Network Status", "Unknown"),
            ("Alerts Today", "0")
        ]
        
        row, col = 0, 0
        for stat, value in stats:
            stat_frame = ttk.Frame(stats_frame)
            stat_frame.grid(row=row, column=col, padx=10, pady=5, sticky="nsew")
            
            ttk.Label(
                stat_frame,
                text=stat,
                font=("Arial", 8)
            ).pack(anchor="w")
            
            ttk.Label(
                stat_frame,
                text=value,
                font=("Arial", 10, "bold")
            ).pack(anchor="w")
            
            col += 1
            if col > 2:  # 3 columns per row
                col = 0
                row += 1
        
        # Configure the grid to expand columns evenly
        for i in range(3):
            stats_frame.columnconfigure(i, weight=1)
    
    def check_obs_status(self):
        """
        Check OBS process status and update the UI.
        This is the manual check triggered by the button.
        """
        self.logger.info("Manually checking OBS status")
        
        # Disable the button temporarily to prevent multiple clicks
        self.check_obs_button.config(state=tk.DISABLED)
        
        try:
            # Import the OBS checker from system_monitoring
            from system_monitoring import OwlySystemMonitor
            
            # Create a temporary monitor instance
            monitor = OwlySystemMonitor()
            
            # Check OBS status
            is_running = monitor.check_obs_process()
            
            # Update the UI with the result
            self.update_obs_status_ui(
                is_running=is_running,
                last_check_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_count=0 if is_running else 1,
                cooldown_active=False,
                cooldown_remaining=0
            )
            
            # Add to history
            self.add_obs_history_entry(
                f"{datetime.datetime.now().strftime('%H:%M:%S')}: "
                f"Manual check - OBS {'running' if is_running else 'not running'}"
            )
        except Exception as e:
            self.logger.error(f"Error checking OBS status: {e}")
            self.obs_status_label.config(
                text=f"Error: {str(e)}",
                foreground="red"
            )
            
            # Add to history
            self.add_obs_history_entry(
                f"{datetime.datetime.now().strftime('%H:%M:%S')}: "
                f"Error checking OBS status: {str(e)}"
            )
        finally:
            # Re-enable the button after a short delay
            self.after(1000, lambda: self.check_obs_button.config(state=tk.NORMAL))
    
    def update_obs_status_ui(self, is_running, last_check_time, error_count, cooldown_active, cooldown_remaining):
        """
        Update the OBS status UI elements.
        
        Args:
            is_running (bool): Whether OBS is running
            last_check_time (str): Time of last check
            error_count (int): Number of consecutive errors
            cooldown_active (bool): Whether alert cooldown is active
            cooldown_remaining (int): Seconds remaining in cooldown
        """
        # Update status label
        if is_running:
            self.obs_status_label.config(
                text="Running",
                foreground="green"
            )
        else:
            self.obs_status_label.config(
                text="Not Running",
                foreground="red"
            )
        
        # Update last check time
        self.obs_check_time_label.config(text=last_check_time)
        
        # Update alert status
        if cooldown_active:
            self.obs_alert_status_label.config(
                text=f"Alert cooldown active ({cooldown_remaining // 60} min remaining)",
                foreground="orange"
            )
        else:
            if error_count > 0:
                self.obs_alert_status_label.config(
                    text=f"Alert will be sent if still down ({error_count} check{'s' if error_count > 1 else ''})",
                    foreground="orange"
                )
            else:
                self.obs_alert_status_label.config(
                    text="No alerts needed",
                    foreground="green"
                )
        
        # Update local status tracking
        self.obs_status = {
            'is_running': is_running,
            'last_check_time': last_check_time,
            'error_count': error_count,
            'cooldown_active': cooldown_active,
            'cooldown_remaining': cooldown_remaining
        }
    
    def add_obs_history_entry(self, text):
        """
        Add an entry to the OBS history text widget.
        
        Args:
            text (str): Text to add to history
        """
        # Enable editing
        self.obs_history_text.config(state=tk.NORMAL)
        
        # Add text to the top of the history
        self.obs_history_text.insert("1.0", text + "\n")
        
        # Limit history to 10 lines
        content = self.obs_history_text.get("1.0", tk.END)
        lines = content.split("\n")
        if len(lines) > 11:  # 10 lines + empty line at end
            self.obs_history_text.delete("1.0", tk.END)
            self.obs_history_text.insert("1.0", "\n".join(lines[:10]))
        
        # Disable editing
        self.obs_history_text.config(state=tk.DISABLED)
    
    def start_auto_refresh(self):
        """Start the auto-refresh timer"""
        # Initial refresh
        self.refresh_status()
        
        # Schedule periodic refresh (every 60 seconds)
        self.after(60000, self.start_auto_refresh)
    
    def refresh_status(self):
        """Refresh all system status information"""
        try:
            # Update last refreshed time
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.last_refreshed_label.config(text=f"Last refreshed: {current_time}")
            
            # Try to get OBS status from system monitor
            try:
                from system_monitoring import OwlySystemMonitor
                
                # Import the monitor and get status
                monitor = OwlySystemMonitor()
                status = monitor.get_status()
                
                # Extract OBS status
                obs_status = status.get('obs_stream', {})
                is_running = obs_status.get('is_running', False)
                last_check = obs_status.get('last_check')
                error_count = obs_status.get('error_count', 0)
                cooldown_active = obs_status.get('cooldown_active', False)
                cooldown_remaining = obs_status.get('cooldown_remaining_seconds', 0)
                
                # Format last check time
                last_check_str = "Never"
                if last_check:
                    if isinstance(last_check, str):
                        last_check_str = last_check
                    else:
                        last_check_str = last_check.strftime("%Y-%m-%d %H:%M:%S")
                
                # Update UI
                self.update_obs_status_ui(
                    is_running=is_running,
                    last_check_time=last_check_str,
                    error_count=error_count,
                    cooldown_active=cooldown_active,
                    cooldown_remaining=cooldown_remaining
                )
                
                # Only add history entry if status changed
                if is_running != self.obs_status.get('is_running', None):
                    status_text = "running" if is_running else "not running"
                    self.add_obs_history_entry(
                        f"{time.strftime('%H:%M:%S')}: OBS is {status_text}"
                    )
            except Exception as e:
                self.logger.warning(f"Error refreshing OBS status: {e}")
                # Don't update UI on error, just log it
        except Exception as e:
            self.logger.error(f"Error in refresh_status: {e}")
            
        # Return True to continue the timer
        return True