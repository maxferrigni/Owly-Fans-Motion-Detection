# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System
#
# March 8, 2025 Update - Version 1.5.0
# - Added clock display to the UI
# - Improved subprocess log reading for better reliability
# - Made GUI properly resizable with minimum dimensions
# - Added simple image viewer for base images
# - Added system health monitoring framework

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import json
from datetime import datetime, timedelta
import pytz

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from utilities.time_utils import get_current_lighting_condition

# Import GUI panels - now including all panel components
from _front_end_panels import (
    LogWindow, 
    LightingInfoPanel,
    ControlPanel
)

# Import remaining components
from motion_detection_settings import MotionDetectionSettings

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")
        
        # Allow resizing but with minimum dimensions
        self.root.minsize(800, 500)
        self.root.resizable(True, True)
        
        self.root.update_idletasks()

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.IntVar(value=60)  # Default to 60 seconds
        self.alert_delay = tk.IntVar(value=30)      # Default to 30 minutes
        
        # Add alert toggle variables - simplified to only email alerts
        self.email_alerts_enabled = tk.BooleanVar(value=True)
        
        # Initialize lighting condition
        self.current_lighting_condition = get_current_lighting_condition()
        self.in_transition = self.current_lighting_condition == 'transition'
        
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Set style for more immediate button rendering
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TFrame', padding=2)
        self.style.configure('TLabelframe', padding=3)
        
        # Add custom styles for lighting indicators
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 10, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 10, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 10, 'bold'))

        # Initialize managers
        self.alert_manager = AlertManager()
        self.logger = get_logger()

        # Create header frame to contain environment, version, clock, and health indicators
        self.header_frame = ttk.Frame(self.root)
        self.header_frame.pack(side="top", fill="x", pady=5)

        # Add environment label
        self.env_label = ttk.Label(
            self.header_frame,
            text="DEV ENVIRONMENT" if "Dev" in BASE_DIR else "PRODUCTION",
            font=("Arial", 12, "bold"),
            foreground="red" if "Dev" in BASE_DIR else "green"
        )
        self.env_label.pack(side="top", pady=5)

        # Add version label
        self.version_label = ttk.Label(
            self.header_frame,
            text=f"Version: {VERSION}",
            font=("Arial", 8)
        )
        self.version_label.pack(side="top", pady=2)
        
        # Initialize clock
        self.initialize_clock()
        
        # Add lighting information panel
        self.lighting_info_panel = LightingInfoPanel(self.root)
        self.lighting_info_panel.pack(side="top", pady=3, fill="x")

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=3, pady=3)

        # Create main notebook for tab-based layout
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True)

        # Create tabs
        self.control_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.test_tab = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.test_tab, text="Test")

        # Initialize components
        self.initialize_components()
        
        # Initialize system health monitoring
        self.initialize_health_monitor()
        
        # Initialize image viewers
        self.initialize_image_viewers()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")
    
    def initialize_clock(self):
        """Add simple clock to the UI"""
        self.clock_label = ttk.Label(
            self.header_frame,
            font=("Arial", 11),
            foreground="darkblue"
        )
        self.clock_label.pack(side="right", padx=10)
        self.update_clock()
    
    def update_clock(self):
        """Update clock display every second"""
        current_time = datetime.now().strftime('%H:%M:%S')
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_clock)

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Create control panel - Now uses the panel class with simplified parameters
        self.control_panel = ControlPanel(
            self.control_tab,
            self.local_saving_enabled,
            self.capture_interval,
            self.alert_delay,
            self.email_alerts_enabled,
            self.update_system,
            self.start_script,
            self.stop_script,
            self.toggle_local_saving,
            self.update_capture_interval,
            self.update_alert_delay,
            self.toggle_email_alerts,
            self.log_window
        )
        self.control_panel.pack(fill="both", expand=True)
        
        # Create motion detection settings in settings tab
        settings_scroll = ttk.Frame(self.settings_tab)
        settings_scroll.pack(fill="both", expand=True)
        self.settings = MotionDetectionSettings(settings_scroll, self.logger)
        
        # Create test interface in test tab
        test_scroll = ttk.Frame(self.test_tab)
        test_scroll.pack(fill="both", expand=True)
        
        # Import test interface here to avoid circular import issues
        from test_interface import TestInterface
        self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)
    
    def initialize_health_monitor(self):
        """Initialize system health monitoring"""
        # Import the health monitor
        from system_health import SystemHealthMonitor
        
        # Create status frame in the header area
        self.health_status_frame = ttk.Frame(self.header_frame)
        self.health_status_frame.pack(side="left", padx=10)
        
        # Create status indicators
        self.health_status_label = ttk.Label(
            self.health_status_frame,
            text="System: --",
            font=("Arial", 9),
            foreground="gray"
        )
        self.health_status_label.pack(side="left", padx=5)
        
        # Component status indicators
        self.camera_status_label = ttk.Label(
            self.health_status_frame,
            text="Camera: --",
            font=("Arial", 9),
            foreground="gray"
        )
        self.camera_status_label.pack(side="left", padx=5)
        
        self.obs_status_label = ttk.Label(
            self.health_status_frame,
            text="OBS: --",
            font=("Arial", 9),
            foreground="gray"
        )
        self.obs_status_label.pack(side="left", padx=5)
        
        # Initialize health monitor with status callback
        self.health_monitor = SystemHealthMonitor()
        self.health_monitor.add_status_callback(self.update_health_status)
        
        # Start monitoring
        self.health_monitor.start_monitoring()
    
    def update_health_status(self, status):
        """Update health status indicators"""
        # Update overall status
        if status["healthy"]:
            self.health_status_label.config(text="System: OK", foreground="green")
        else:
            self.health_status_label.config(text="System: ISSUE", foreground="red")
            
        # Update component statuses
        for check in status["checks"]:
            if check["name"] == "Wyze Camera":
                if check["healthy"]:
                    self.camera_status_label.config(text="Camera: OK", foreground="green")
                else:
                    self.camera_status_label.config(text=f"Camera: {check['status']}", foreground="red")
            elif check["name"] == "OBS Process":
                if check["healthy"]:
                    self.obs_status_label.config(text="OBS: Running", foreground="green")
                else:
                    self.obs_status_label.config(text="OBS: Stopped", foreground="red")
    
    def initialize_image_viewers(self):
        """Initialize simple image viewers"""
        # Create bottom panel for viewers
        self.bottom_frame = ttk.Frame(self.root)
        self.bottom_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        
        # Import the viewer
        from simple_image_viewer import SimpleImageViewer
        
        # Create day viewer
        self.day_image_viewer = SimpleImageViewer(self.bottom_frame, "Day Base Image")
        self.day_image_viewer.pack(side="left", fill="both", expand=True, padx=5)
        
        # Create night viewer
        self.night_image_viewer = SimpleImageViewer(self.bottom_frame, "Night Base Image")
        self.night_image_viewer.pack(side="left", fill="both", expand=True, padx=5)
        
        # Schedule initial image loading
        self.root.after(2000, self.load_base_images)
    
    def load_base_images(self):
        """Load base images into viewers"""
        from utilities.constants import get_base_image_path
        
        # Default camera
        camera_name = "Wyze Internal Camera"
        
        # Load day image
        day_path = get_base_image_path(camera_name, "day")
        self.day_image_viewer.load_image(day_path)
        
        # Load night image
        night_path = get_base_image_path(camera_name, "night")
        self.night_image_viewer.load_image(night_path)
        
        # Schedule refresh
        self.root.after(60000, self.load_base_images)  # Refresh every minute

    def log_message(self, message, level="INFO"):
        """Log message to log window"""
        try:
            self.log_window.log_message(message, level)
        except Exception as e:
            print(f"Error logging message: {e}")

    def verify_directories(self):
        """Verify all required directories exist"""
        try:
            self.log_message("Verifying directory structure...")
            ensure_directories_exist()
            self.log_message("Directory verification complete")
        except Exception as e:
            self.log_message(f"Error verifying directories: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to verify directories: {e}")

    def toggle_local_saving(self):
        """Handle local saving toggle"""
        is_enabled = self.local_saving_enabled.get()
        self.log_message(f"Local image saving {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_LOCAL_SAVING'] = str(is_enabled)

        if is_enabled:
            try:
                ensure_directories_exist()
            except Exception as e:
                self.log_message(f"Error creating local directories: {e}", "ERROR")
                messagebox.showerror("Error", f"Failed to create local directories: {e}")
                self.local_saving_enabled.set(False)

    def toggle_email_alerts(self):
        """Handle email alerts toggle"""
        is_enabled = self.email_alerts_enabled.get()
        self.log_message(f"Email alerts {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_EMAIL_ALERTS'] = str(is_enabled)

    def update_capture_interval(self, *args):
        """Handle changes to the capture interval"""
        try:
            interval = self.capture_interval.get()
            
            # Validate interval is within reasonable range
            if interval < 10:
                self.capture_interval.set(10)
                interval = 10
                self.log_message("Minimum capture interval is 10 seconds", "WARNING")
            elif interval > 300:
                self.capture_interval.set(300)
                interval = 300
                self.log_message("Maximum capture interval is 300 seconds", "WARNING")
                
            # Update environment variable for child processes
            os.environ['OWL_CAPTURE_INTERVAL'] = str(interval)
            
            self.log_message(f"Capture interval updated to {interval} seconds")
            
        except Exception as e:
            self.log_message(f"Error updating capture interval: {e}", "ERROR")
            # Reset to default on error
            self.capture_interval.set(60)
            
    def update_alert_delay(self, *args):
        """Handle changes to the alert delay"""
        try:
            delay = self.alert_delay.get()
            
            # Validate delay is within reasonable range
            if delay < 5:
                self.alert_delay.set(5)
                delay = 5
                self.log_message("Minimum alert delay is 5 minutes", "WARNING")
            elif delay > 120:
                self.alert_delay.set(120)
                delay = 120
                self.log_message("Maximum alert delay is 120 minutes", "WARNING")
                
            # Update alert manager
            self.alert_manager.set_alert_delay(delay)
            
            self.log_message(f"Alert delay updated to {delay} minutes")
            
        except Exception as e:
            self.log_message(f"Error updating alert delay: {e}", "ERROR")
            # Reset to default on error
            self.alert_delay.set(30)

    class LogRedirector:
        """Redirects stdout/stderr to log window"""
        def __init__(self, app):
            self.app = app

        def write(self, message):
            if message.strip():
                if "error" in message.lower():
                    self.app.log_message(message.strip(), "ERROR")
                elif "warning" in message.lower():
                    self.app.log_message(message.strip(), "WARNING")
                else:
                    self.app.log_message(message.strip(), "INFO")

        def flush(self):
            pass

    def update_system(self):
        """Update the system from git repository"""
        if self.script_process:
            messagebox.showwarning(
                "Warning",
                "Please stop motion detection before updating."
            )
            return

        try:
            self.log_message("Fetching latest updates from GitHub...")
            original_dir = os.getcwd()
            os.chdir(os.path.dirname(SCRIPTS_DIR))

            try:
                # Fetch the latest from origin
                result_fetch = subprocess.run(
                    ["git", "fetch", "origin"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_fetch.stdout)
                
                # Reset to exactly match the remote dev branch
                result_reset = subprocess.run(
                    ["git", "reset", "--hard", "origin/dev"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_reset.stdout)

                # Clean untracked files (but respect .gitignore)
                result_clean = subprocess.run(
                    ["git", "clean", "-fd"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_clean.stdout)

                self.log_message("Update successful. Restarting application...")
                self.restart_application()
            except Exception as e:
                self.log_message(f"Git update failed: {e}", "ERROR")
                messagebox.showerror("Update Failed", f"Failed to update from GitHub: {e}")
            finally:
                os.chdir(original_dir)
        except Exception as e:
            self.log_message(f"Error during update: {e}", "ERROR")
            messagebox.showerror("Update Error", f"An error occurred: {e}")

    def restart_application(self):
        """Restart the entire application"""
        self.root.destroy()
        python_executable = sys.executable
        script_path = os.path.join(SCRIPTS_DIR, "_front_end.py")
        os.execv(python_executable, [python_executable, script_path])

    def start_script(self):
        """Start the motion detection script"""
        if not self.script_process:
            self.log_message("Starting motion detection script...")
            try:
                # Pass configuration through environment variables
                env = os.environ.copy()
                env['OWL_LOCAL_SAVING'] = str(self.local_saving_enabled.get())
                # Use the capture interval from the UI control
                env['OWL_CAPTURE_INTERVAL'] = str(self.capture_interval.get())
                
                # Add the alert setting environment variables
                env['OWL_EMAIL_ALERTS'] = str(self.email_alerts_enabled.get())
                
                # Set alert delay
                self.alert_manager.set_alert_delay(self.alert_delay.get())
                
                cmd = [sys.executable, self.main_script_path]
                self.script_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )

                # Update UI state
                self.control_panel.update_run_state(True)
                
                # Start log monitoring
                threading.Thread(target=self.refresh_logs, daemon=True).start()

            except Exception as e:
                self.log_message(f"Error starting script: {e}", "ERROR")

    def stop_script(self):
        """Stop the motion detection script"""
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            try:
                self.script_process.terminate()
                self.script_process.wait(timeout=5)
                self.script_process = None
                self.control_panel.update_run_state(False)
            except Exception as e:
                self.log_message(f"Error stopping script: {e}", "ERROR")

    def refresh_logs(self):
        """Refresh log display with script output - more reliable version"""
        try:
            while self.script_process and self.script_process.stdout:
                # Read line by line
                line = self.script_process.stdout.readline()
                if not line:  # EOF reached
                    break
                if line.strip():
                    self.log_message(line.strip())
        except Exception as e:
            self.log_message(f"Error reading logs: {e}", "ERROR")