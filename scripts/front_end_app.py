# File: scripts/front_end_app.py
# Purpose: Main application window for the Owl Monitoring System
#
# March 19, 2025 Update - Version 1.4.4
# - Added global is_running flag to prevent background image saving
# - Enhanced image clearing to remove all images from all directories
# - Added version tagging support for image filenames
# - Fixed issues with Images tab behavior and initialization

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import json
from datetime import datetime, timedelta
import pytz
import glob

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from utilities.time_utils import get_current_lighting_condition

# Import GUI panels (shared components)
from front_end_panels import LogWindow, LightingInfoPanel

# Import tab components from front_end_components
from front_end_components.control_tab import ControlTab
from front_end_components.settings_tab import SettingsTab
from front_end_components.test_tab import TestTab
from front_end_components.images_tab import ImagesTab
from front_end_components.monitor_tab import MonitorTab

# Global running flag that can be accessed by other modules
# This is a sentinel to prevent image saving when the app isn't running
IS_RUNNING = False

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")
        self.root.update_idletasks()
        self.root.resizable(True, True)

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

        # Add environment and version labels
        self.env_label = ttk.Label(
            self.root,
            text="DEV ENVIRONMENT" if "Dev" in BASE_DIR else "PRODUCTION",
            font=("Arial", 12, "bold"),
            foreground="red" if "Dev" in BASE_DIR else "green"
        )
        self.env_label.pack(side="top", pady=5)

        # Add version label
        self.version_label = ttk.Label(
            self.root,
            text=f"Version: {VERSION}",
            font=("Arial", 8)
        )
        self.version_label.pack(side="top", pady=2)
        
        # Add lighting information panel
        self.lighting_info_panel = LightingInfoPanel(self.root)
        self.lighting_info_panel.pack(side="top", pady=2, fill="x")

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
        self.images_tab = ttk.Frame(self.notebook)
        self.sys_monitor_tab = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.test_tab, text="Test")
        self.notebook.add(self.images_tab, text="Images")
        self.notebook.add(self.sys_monitor_tab, text="Sys Monitor")

        # Initialize components
        self.initialize_components()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready", "INFO")
        
        # Clear any leftover "empty" directories to ensure clean state
        self.clear_empty_image_directories()

    def initialize_components(self):
        """Initialize all GUI components"""
        # Initialize log window
        self.log_window = LogWindow(self.root)
        
        # Initialize tab components
        self.control_tab_component = ControlTab(
            self.control_tab, 
            self
        )
        
        self.settings_tab_component = SettingsTab(
            self.settings_tab, 
            self
        )
        
        self.test_tab_component = TestTab(
            self.test_tab, 
            self
        )
        
        self.images_tab_component = ImagesTab(
            self.images_tab, 
            self,
            is_running=self.is_running  # Pass the running state to Images tab
        )
        
        self.sys_monitor_tab_component = MonitorTab(
            self.sys_monitor_tab, 
            self
        )

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

    @property
    def is_running(self):
        """Get the current running state of the application"""
        return self.script_process is not None
    
    def get_version(self):
        """Get the current version of the application"""
        return VERSION

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
        script_path = os.path.join(SCRIPTS_DIR, "front_end.py")
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
                env['OWL_EMAIL_ALERTS'] = str(self.email_alerts_enabled.get())
                
                # NEW - Set the app version for image naming
                env['OWL_APP_VERSION'] = VERSION
                
                # Set alert delay
                self.alert_manager.set_alert_delay(self.alert_delay.get())
                
                # Set the global running flag to True
                global IS_RUNNING
                IS_RUNNING = True
                
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
                self.control_tab_component.update_run_state(True)
                
                # Update Images tab with running state
                if hasattr(self.images_tab_component, 'set_running_state'):
                    self.images_tab_component.set_running_state(True)
                
                # Start log monitoring
                threading.Thread(target=self.refresh_logs, daemon=True).start()

            except Exception as e:
                self.log_message(f"Error starting script: {e}", "ERROR")
                # Reset running flag if startup fails
                IS_RUNNING = False

    def stop_script(self):
        """Stop the motion detection script"""
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            try:
                self.script_process.terminate()
                self.script_process.wait(timeout=5)
                self.script_process = None
                
                # Set the global running flag to False
                global IS_RUNNING
                IS_RUNNING = False
                
                # Update UI state
                self.control_tab_component.update_run_state(False)
                
                # Update Images tab with running state
                if hasattr(self.images_tab_component, 'set_running_state'):
                    self.images_tab_component.set_running_state(False)
                
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
    
    def clear_empty_image_directories(self):
        """Clear any empty image directories on startup"""
        try:
            from utilities.constants import BASE_IMAGES_DIR, IMAGE_COMPARISONS_DIR, SAVED_IMAGES_DIR
            
            # Create list of directories to check
            image_dirs = [
                BASE_IMAGES_DIR,
                IMAGE_COMPARISONS_DIR,
                SAVED_IMAGES_DIR
            ]
            
            # Check each directory
            for directory in image_dirs:
                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
        except Exception as e:
            self.log_message(f"Error checking image directories: {e}", "ERROR")
            
    def clear_local_images(self):
        """
        Clear all local images from storage directories.
        Updated in v1.4.4 to ensure all image directories are completely cleared.
        """
        try:
            from utilities.constants import (
                BASE_IMAGES_DIR, 
                IMAGE_COMPARISONS_DIR, 
                SAVED_IMAGES_DIR
            )
            
            # Create list of all directories to clear
            image_dirs = [
                BASE_IMAGES_DIR,
                IMAGE_COMPARISONS_DIR,
                SAVED_IMAGES_DIR
            ]
            
            # Also check for subdirectories in IMAGE_COMPARISONS_DIR
            # (for component images organized by camera)
            if os.path.exists(IMAGE_COMPARISONS_DIR):
                for item in os.listdir(IMAGE_COMPARISONS_DIR):
                    subdir_path = os.path.join(IMAGE_COMPARISONS_DIR, item)
                    if os.path.isdir(subdir_path):
                        image_dirs.append(subdir_path)
            
            # Clear all images
            total_deleted = 0
            for directory in image_dirs:
                if os.path.exists(directory):
                    # Use glob to find all files including those in subdirectories
                    for file_path in glob.glob(os.path.join(directory, "**/*.*"), recursive=True):
                        if os.path.isfile(file_path):
                            try:
                                os.unlink(file_path)
                                total_deleted += 1
                            except Exception as e:
                                self.log_message(f"Error deleting {file_path}: {e}", "WARNING")
            
            # Update Images tab to display blank placeholders
            if hasattr(self.images_tab_component, 'clear_images'):
                self.images_tab_component.clear_images()
                            
            self.log_message(f"{total_deleted:,} images deleted", "INFO")
        except Exception as e:
            self.log_message(f"Error clearing images: {e}", "ERROR")