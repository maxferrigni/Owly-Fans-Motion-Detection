# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
from datetime import datetime

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from motion_detection_settings import MotionDetectionSettings
from test_interface import TestInterface

# Import GUI panels
from _front_end_panels import LogWindow, StatusPanel

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")  # Reduced height to 600
        self.root.update_idletasks()
        self.root.resizable(True, True)

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.IntVar(value=60)  # Default to 60 seconds
        self.alert_delay = tk.IntVar(value=30)      # Default to 30 minutes
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Set style for more immediate button rendering
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TFrame', padding=2)  # Reduced padding
        self.style.configure('TLabelframe', padding=3)  # Reduced padding

        # Initialize managers
        self.alert_manager = AlertManager()
        self.logger = get_logger()

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=3, pady=3)  # Reduced padding

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

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Create control panel
        self.create_control_panel()
        
        # Create status panel
        self.status_panel = StatusPanel(self.control_tab)
        self.status_panel.pack(fill="x", pady=3)  # Reduced padding
        
        # Create motion detection settings in settings tab (more compact)
        settings_scroll = ttk.Frame(self.settings_tab)
        settings_scroll.pack(fill="both", expand=True)
        self.settings = MotionDetectionSettings(settings_scroll, self.logger)
        
        # Create test interface in test tab (more compact)
        test_scroll = ttk.Frame(self.test_tab)
        test_scroll.pack(fill="both", expand=True)
        self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)

    def create_control_panel(self):
        """Create main control panel"""
        # Main control frame with a clear title
        control_frame = ttk.LabelFrame(self.control_tab, text="System Controls")
        control_frame.pack(fill="x", pady=3, padx=3)  # Reduced padding

        # Grid layout for better button placement with reduced spacing
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill="x", pady=3, padx=3)  # Reduced padding
        
        # Update button
        update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system,
            style='TButton'
        )
        update_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Start button
        start_button = ttk.Button(
            button_frame,
            text="Start Motion Detection",
            command=self.start_script,
            style='TButton'
        )
        start_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Stop button
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Motion Detection",
            command=self.stop_script,
            state=tk.DISABLED,
            style='TButton'
        )
        self.stop_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")  # Reduced padding

        # Local saving option in the right column, second row
        save_frame = ttk.Frame(button_frame)
        save_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")  # Reduced padding
        
        ttk.Checkbutton(
            save_frame,
            text="Save Images Locally",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving
        ).pack(pady=2)  # Reduced padding

        # Make columns expand evenly
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # Add interval settings frame
        settings_frame = ttk.LabelFrame(control_frame, text="Timing Settings")
        settings_frame.pack(fill="x", pady=3, padx=3)
        
        # Add capture interval setting
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.pack(fill="x", pady=2, padx=3)
        
        ttk.Label(
            interval_frame,
            text="Capture Interval (seconds):"
        ).pack(side=tk.LEFT, padx=5)
        
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            increment=10,
            textvariable=self.capture_interval,
            width=5
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the interval spinner to the update handler
        interval_spinner.bind('<FocusOut>', self.update_capture_interval)
        interval_spinner.bind('<Return>', self.update_capture_interval)
        # Also update when using the spinbox arrows
        self.capture_interval.trace_add("write", self.update_capture_interval)
        
        # Add status indication for the interval
        ttk.Label(
            interval_frame,
            text="(Default: 60 seconds)"
        ).pack(side=tk.LEFT, padx=5)
        
        # Add alert delay setting
        alert_delay_frame = ttk.Frame(settings_frame)
        alert_delay_frame.pack(fill="x", pady=2, padx=3)
        
        ttk.Label(
            alert_delay_frame,
            text="Alert Delay (minutes):"
        ).pack(side=tk.LEFT, padx=5)
        
        alert_delay_spinner = ttk.Spinbox(
            alert_delay_frame,
            from_=5,
            to=120,
            increment=5,
            textvariable=self.alert_delay,
            width=5
        )
        alert_delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Connect the alert delay spinner to the update handler
        alert_delay_spinner.bind('<FocusOut>', self.update_alert_delay)
        alert_delay_spinner.bind('<Return>', self.update_alert_delay)
        # Also update when using the spinbox arrows
        self.alert_delay.trace_add("write", self.update_alert_delay)
        
        # Add status indication for the alert delay
        ttk.Label(
            alert_delay_frame,
            text="(Default: 30 minutes)"
        ).pack(side=tk.LEFT, padx=5)

        # Log viewing button in a separate section
        log_frame = ttk.Frame(control_frame)
        log_frame.pack(fill="x", pady=2, padx=3)  # Reduced padding
        
        ttk.Button(
            log_frame,
            text="View Logs",
            command=lambda: self.log_window.show()
        ).pack(pady=2)  # Reduced padding

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
            
            # Update status panel
            self.status_panel.update_status(
                "Capture Interval",
                f"{interval} sec"
            )
            
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
            
            # Update status panel
            self.status_panel.update_status(
                "Alert Delay",
                f"{delay} min"
            )
            
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
        
        # Update status panel
        self.status_panel.update_status(
            "Local Saving",
            "enabled" if is_enabled else "disabled"
        )

    def update_system(self):
        """Update the system from git repository"""
        if self.script_process:
            messagebox.showwarning(
                "Warning",
                "Please stop motion detection before updating."
            )
            return

        try:
            self.log_message("Resetting local repository and pulling latest updates...")
            original_dir = os.getcwd()
            os.chdir(os.path.dirname(SCRIPTS_DIR))

            try:
                result_reset = subprocess.run(
                    ["git", "reset", "--hard"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_reset.stdout)

                result_clean = subprocess.run(
                    ["git", "clean", "-fd"],
                    capture_output=True,
                    text=True
                )
                self.log_message(result_clean.stdout)

                result_pull = subprocess.run(
                    ["git", "pull"],
                    capture_output=True,
                    text=True
                )

                if result_pull.returncode == 0:
                    self.log_message("Git pull successful. Restarting application...")
                    self.restart_application()
                else:
                    self.log_message(f"Git pull failed: {result_pull.stderr}", "ERROR")
                    messagebox.showerror("Update Failed", "Git pull failed. Check logs for details.")
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
                self.stop_button.config(state=tk.NORMAL)
                self.status_panel.update_status("Motion Detection", "running")
                
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
                self.stop_button.config(state=tk.DISABLED)
                self.status_panel.update_status("Motion Detection", "stopped")
            except Exception as e:
                self.log_message(f"Error stopping script: {e}", "ERROR")

    def refresh_logs(self):
        """Refresh log display with script output"""
        try:
            while self.script_process and self.script_process.stdout:
                line = self.script_process.stdout.readline()
                if line.strip():
                    self.log_message(line.strip())
        except Exception as e:
            self.log_message(f"Error reading logs: {e}", "ERROR")