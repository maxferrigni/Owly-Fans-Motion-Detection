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
from _front_end_panels import LogWindow, AlertHierarchyFrame, StatusPanel

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("1000x700+-1920+0")
        self.root.update_idletasks()
        self.root.resizable(True, True)

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.StringVar(value="60")
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Initialize managers
        self.alert_manager = AlertManager()
        self.logger = get_logger()

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)

        # Create layout frames
        self.create_layout_frames()

        # Initialize components
        self.initialize_components()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")

    def create_layout_frames(self):
        """Create main layout frames"""
        # Left panel for controls
        self.left_panel = ttk.Frame(self.main_container)
        self.left_panel.pack(side=tk.LEFT, fill="both", padx=5)
        
        # Right panel for settings and status
        self.right_panel = ttk.Frame(self.main_container)
        self.right_panel.pack(side=tk.LEFT, fill="both", expand=True, padx=5)

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Create control panel
        self.create_control_panel()
        
        # Create alert hierarchy panel
        self.alert_hierarchy = AlertHierarchyFrame(self.left_panel, self.alert_manager)
        self.alert_hierarchy.pack(fill="x", pady=5)
        
        # Create motion detection settings
        self.settings = MotionDetectionSettings(self.right_panel, self.logger)
        
        # Create test interface
        test_frame = ttk.LabelFrame(self.left_panel, text="Testing")
        test_frame.pack(fill="x", pady=5)
        self.test_interface = TestInterface(test_frame, self.logger, self.alert_manager)
        
        # Create status panel
        self.status_panel = StatusPanel(self.right_panel)
        self.status_panel.pack(fill="x", pady=5)

    def create_control_panel(self):
        """Create main control panel"""
        control_frame = ttk.LabelFrame(self.left_panel, text="System Controls")
        control_frame.pack(fill="x", pady=5)

        # Update System button
        ttk.Button(
            control_frame,
            text="Update System",
            command=self.update_system,
            width=20
        ).pack(pady=5)

        # Motion Detection buttons
        ttk.Button(
            control_frame,
            text="Start Motion Detection",
            command=self.start_script,
            width=20
        ).pack(pady=5)

        self.stop_button = ttk.Button(
            control_frame,
            text="Stop Motion Detection",
            command=self.stop_script,
            state=tk.DISABLED,
            width=20
        )
        self.stop_button.pack(pady=5)

        # Capture Interval frame
        interval_frame = ttk.Frame(control_frame)
        interval_frame.pack(pady=5)

        ttk.Label(interval_frame, text="Capture Interval:").pack(side=tk.LEFT)

        self.capture_interval_combo = ttk.Combobox(
            interval_frame,
            textvariable=self.capture_interval,
            width=5,
            state="readonly",
            values=["1", "5", "15", "30", "60"]
        )
        self.capture_interval_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(interval_frame, text="seconds").pack(side=tk.LEFT)

        # Local Saving toggle
        ttk.Checkbutton(
            control_frame,
            text="Save Images Locally",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving
        ).pack(pady=5)

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
                env['OWL_CAPTURE_INTERVAL'] = str(self.capture_interval.get())
                
                # Update alert delay from hierarchy panel
                self.alert_manager.set_alert_delay(
                    self.alert_hierarchy.get_base_delay()
                )
                
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