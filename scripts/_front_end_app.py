# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System - MINIMAL VERSION FOR DEBUGGING

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import json
from datetime import datetime, timedelta
import pytz

# Debug statement
print("Starting application initialization...")

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    # Import utilities and modules
    print("Importing utilities...")
    from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
    from utilities.logging_utils import get_logger
    
    print("Importing alert manager...")
    from utilities.alert_manager import AlertManager
    
    print("Importing time utils...")
    from utilities.time_utils import get_current_lighting_condition
    
    # Import GUI panels - now including all panel components
    print("Importing frontend panels...")
    from _front_end_panels import (
        LogWindow, 
        ControlPanel
    )
    
    # Skip LightingInfoPanel for now
    # LightingInfoPanel
    
    # Import remaining components
    print("Importing motion detection settings...")
    from motion_detection_settings import MotionDetectionSettings
    
    print("All imports completed successfully")
except Exception as e:
    print(f"ERROR during imports: {e}")
    raise

class OwlApp:
    def __init__(self, root):
        print("Starting OwlApp initialization...")
        
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("900x600+-1920+0")
        
        # Allow resizing but with minimum dimensions
        self.root.minsize(800, 500)
        self.root.resizable(True, True)
        
        self.root.update_idletasks()
        print("Window initialization complete")

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.IntVar(value=60)  # Default to 60 seconds
        self.alert_delay = tk.IntVar(value=30)      # Default to 30 minutes
        
        # Add alert toggle variables - simplified to only email alerts
        self.email_alerts_enabled = tk.BooleanVar(value=True)
        
        # Initialize lighting condition
        try:
            print("Getting current lighting condition...")
            self.current_lighting_condition = get_current_lighting_condition()
            self.in_transition = self.current_lighting_condition == 'transition'
            print(f"Current lighting condition: {self.current_lighting_condition}")
        except Exception as e:
            print(f"ERROR getting lighting condition: {e}")
            self.current_lighting_condition = "day"  # Default
            self.in_transition = False
        
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        try:
            print("Setting up styles...")
            # Set style for more immediate button rendering
            self.style = ttk.Style()
            self.style.configure('TButton', font=('Arial', 10))
            self.style.configure('TFrame', padding=2)
            self.style.configure('TLabelframe', padding=3)
            
            # Add custom styles for lighting indicators
            self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 10, 'bold'))
            self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 10, 'bold'))
            self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 10, 'bold'))
            print("Styles configured successfully")
        except Exception as e:
            print(f"ERROR setting up styles: {e}")

        try:
            print("Initializing managers...")
            # Initialize managers
            self.alert_manager = AlertManager()
            self.logger = get_logger()
            print("Managers initialized successfully")
        except Exception as e:
            print(f"ERROR initializing managers: {e}")
            raise
            
        try:
            print("Creating UI framework...")
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
            print("UI framework created successfully")
        except Exception as e:
            print(f"ERROR creating UI framework: {e}")
            raise
        
        # Initialize clock
        try:
            print("Initializing clock...")
            self.initialize_clock()
            print("Clock initialized successfully")
        except Exception as e:
            print(f"ERROR initializing clock: {e}")
        
        # SKIP LIGHTING PANEL - likely cause of crash
        print("SKIPPING lighting information panel for debugging")
        
        try:
            print("Creating main container...")
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
            print("Main container created successfully")
        except Exception as e:
            print(f"ERROR creating main container: {e}")
            raise

        try:
            print("Initializing UI components...")
            # Initialize components - basic only
            self.initialize_basic_components()
            print("UI components initialized successfully")
        except Exception as e:
            print(f"ERROR initializing UI components: {e}")
            raise
        
        # SKIP NEW COMPONENTS FOR NOW
        print("SKIPPING health monitoring for debugging")
        print("SKIPPING image viewers for debugging")

        # Initialize redirector
        try:
            print("Setting up log redirectors...")
            sys.stdout = self.LogRedirector(self)
            sys.stderr = self.LogRedirector(self)
            print("Log redirectors set up successfully")
        except Exception as e:
            print(f"ERROR setting up log redirectors: {e}")

        # Verify directories
        try:
            print("Verifying directories...")
            self.verify_directories()
            print("Directories verified successfully")
        except Exception as e:
            print(f"ERROR verifying directories: {e}")
        
        self.log_message("GUI initialized and ready", "INFO")
        print("OwlApp initialization complete")
    
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

    def initialize_basic_components(self):
        """Initialize minimal GUI components"""
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
        
        # Skip test interface for now
        test_scroll = ttk.Frame(self.test_tab)
        test_scroll.pack(fill="both", expand=True)
        # self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)

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