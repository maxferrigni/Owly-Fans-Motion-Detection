# File: _front_end_app.py
# Purpose: Main application window for the Owl Monitoring System - ENHANCED WITH ERROR HANDLING
# Version: 1.5.1

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import json
import traceback
from datetime import datetime, timedelta
import pytz

# Debug statement
print("Starting application initialization...")

# Create a special exception hook to log uncaught exceptions
def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception handler to log uncaught exceptions"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"UNCAUGHT EXCEPTION: {error_msg}")
    
    # Also show a message box if possible
    try:
        tk.messagebox.showerror("Uncaught Exception", 
                              f"An unhandled error occurred:\n\n{exc_value}\n\nSee logs for details.")
    except:
        pass
    
    # Call the original exception hook
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Install the custom exception hook
sys.excepthook = exception_hook

# Add parent directory to Python path
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.append(parent_dir)
    print(f"Added parent directory to path: {parent_dir}")
except Exception as e:
    print(f"ERROR setting up path: {e}")
    raise

# Create a lock file to prevent multiple instances
lock_file_path = os.path.join(os.path.expanduser("~"), ".owl_monitor.lock")

def acquire_lock():
    """Try to acquire a lock file"""
    try:
        if os.path.exists(lock_file_path):
            # Check if the lock file is stale
            try:
                with open(lock_file_path, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if the process is still running
                # This is a basic check without psutil
                try:
                    # On Unix-like systems, sending signal 0 checks if process exists
                    if sys.platform != "win32":
                        os.kill(pid, 0)
                        print(f"Lock file exists and process {pid} is still running")
                        return False
                    else:
                        # On Windows, we can't easily check without psutil, so just assume it's stale
                        print(f"Assuming stale lock file on Windows. Removing.")
                        os.remove(lock_file_path)
                except OSError:
                    # Process doesn't exist
                    print(f"Stale lock file found (PID {pid} not running). Removing.")
                    os.remove(lock_file_path)
            except Exception as e:
                print(f"Error checking lock file: {e}. Removing lock file.")
                os.remove(lock_file_path)
        
        # Create a new lock file with current PID
        with open(lock_file_path, 'w') as f:
            f.write(str(os.getpid()))
            
        print(f"Lock file created: {lock_file_path}")
        return True
    except Exception as e:
        print(f"Error acquiring lock: {e}")
        return False

def release_lock():
    """Release the lock file"""
    try:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
            print(f"Lock file removed: {lock_file_path}")
    except Exception as e:
        print(f"Error releasing lock: {e}")

# Try to acquire lock
if not acquire_lock():
    print("Could not acquire lock. Another instance may be running.")
    sys.exit(1)

# Make sure we release the lock when the program exits
import atexit
atexit.register(release_lock)

# Now try to import all required modules with detailed error handling
try:
    # Import utilities and modules - track each import separately
    print("Importing utilities...")
    try:
        from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR
        print("Imported constants successfully")
    except Exception as e:
        print(f"ERROR importing constants: {e}")
        traceback.print_exc()
        raise
    
    try:
        from utilities.logging_utils import get_logger
        print("Imported logging_utils successfully")
    except Exception as e:
        print(f"ERROR importing logging_utils: {e}")
        traceback.print_exc()
        raise
    
    print("Importing alert manager...")
    try:
        from utilities.alert_manager import AlertManager
        print("Imported alert_manager successfully")
    except Exception as e:
        print(f"ERROR importing alert_manager: {e}")
        traceback.print_exc()
        raise
    
    print("Importing time utils...")
    try:
        from utilities.time_utils import get_current_lighting_condition, get_lighting_info
        print("Imported time_utils successfully")
    except Exception as e:
        print(f"ERROR importing time_utils: {e}")
        traceback.print_exc()
        raise
    
    # Import GUI panels - now including all panel components
    print("Importing frontend panels...")
    try:
        from _front_end_panels import (
            LogWindow, 
            ControlPanel,
            LightingInfoPanel  # Re-enable LightingInfoPanel
        )
        print("Imported frontend panels successfully")
    except Exception as e:
        print(f"ERROR importing frontend panels: {e}")
        traceback.print_exc()
        raise
    
    # Import remaining components
    print("Importing motion detection settings...")
    try:
        from motion_detection_settings import MotionDetectionSettings
        print("Imported motion_detection_settings successfully")
    except Exception as e:
        print(f"ERROR importing motion_detection_settings: {e}")
        traceback.print_exc()
        raise
    
    # Import TestInterface
    print("Importing test interface...")
    try:
        from test_interface import TestInterface
        print("Imported test_interface successfully")
    except Exception as e:
        print(f"ERROR importing test_interface: {e}")
        traceback.print_exc()
        # Continue without TestInterface if it fails
    
    # Import new components
    print("Importing camera feed panel...")
    try:
        from camera_feed_panel import CameraFeedPanel
        print("Imported camera_feed_panel successfully")
    except Exception as e:
        print(f"ERROR importing camera_feed_panel: {e}")
        traceback.print_exc()
        # Continue without CameraFeedPanel if it fails
    
    print("Importing health status panel...")
    try:
        from health_status_panel import HealthStatusPanel
        print("Imported health_status_panel successfully")
    except Exception as e:
        print(f"ERROR importing health_status_panel: {e}")
        traceback.print_exc()
        # Continue without HealthStatusPanel if it fails
    
    print("All imports completed successfully")
except Exception as e:
    print(f"ERROR during imports: {e}")
    traceback.print_exc()
    raise

# Initialize logger
try:
    logger = get_logger()
    logger.info("Application startup initiated")
except Exception as e:
    print(f"ERROR initializing logger: {e}")
    traceback.print_exc()
    # Continue without logger if it fails

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
        
        # Set up a handler for the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.root.update_idletasks()
        print("Window initialization complete")

        # Initialize variables
        self.script_process = None
        self.local_saving_enabled = tk.BooleanVar(value=True)
        self.capture_interval = tk.IntVar(value=60)  # Default to 60 seconds
        self.alert_delay = tk.IntVar(value=30)      # Default to 30 minutes
        
        # Add alert toggle variables - simplified to only email alerts
        self.email_alerts_enabled = tk.BooleanVar(value=True)
        
        # Reference to panels and components
        self.log_window = None
        self.control_panel = None
        self.settings = None
        self.lighting_panel = None
        self.test_interface = None
        self.camera_panel = None
        self.health_panel = None
        
        # Initialize lighting condition
        try:
            print("Getting current lighting condition...")
            self.current_lighting_condition = get_current_lighting_condition()
            self.in_transition = self.current_lighting_condition == 'transition'
            print(f"Current lighting condition: {self.current_lighting_condition}")
        except Exception as e:
            print(f"ERROR getting lighting condition: {e}")
            traceback.print_exc()
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
            traceback.print_exc()

        try:
            print("Initializing managers...")
            # Initialize managers - catch each separately
            try:
                self.alert_manager = AlertManager()
                print("Alert manager initialized successfully")
            except Exception as e:
                print(f"ERROR initializing alert manager: {e}")
                traceback.print_exc()
                messagebox.showerror("Error", f"Failed to initialize alert manager: {e}")
                raise
            
            try:
                self.logger = get_logger()
                print("Logger initialized successfully")
            except Exception as e:
                print(f"ERROR initializing logger: {e}")
                traceback.print_exc()
                # Continue without logger
                self.logger = None
            
            print("Managers initialized successfully")
        except Exception as e:
            print(f"ERROR initializing managers: {e}")
            traceback.print_exc()
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
            traceback.print_exc()
            raise
        
        # Initialize clock
        try:
            print("Initializing clock...")
            self.initialize_clock()
            print("Clock initialized successfully")
        except Exception as e:
            print(f"ERROR initializing clock: {e}")
            traceback.print_exc()
        
        # Add Lighting Information Panel - Re-enabling in v1.5.1
        try:
            print("Initializing lighting information panel...")
            self.lighting_panel = LightingInfoPanel(self.root)
            self.lighting_panel.pack(side="top", fill="x", padx=5, pady=2)
            print("Lighting panel initialized successfully")
        except Exception as e:
            print(f"ERROR initializing lighting panel: {e}")
            traceback.print_exc()
            # Continue without lighting panel
        
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
            self.monitor_tab = ttk.Frame(self.notebook)  # New tab for monitoring
            self.health_tab = ttk.Frame(self.notebook)   # New tab for health monitoring

            # Add tabs to notebook
            self.notebook.add(self.control_tab, text="Control")
            self.notebook.add(self.settings_tab, text="Settings")
            self.notebook.add(self.test_tab, text="Test")
            self.notebook.add(self.monitor_tab, text="Monitoring")
            self.notebook.add(self.health_tab, text="Health")
            print("Main container created successfully")
        except Exception as e:
            print(f"ERROR creating main container: {e}")
            traceback.print_exc()
            raise

        try:
            print("Initializing UI components...")
            # Initialize components - basic only
            self.initialize_basic_components()
            print("UI components initialized successfully")
        except Exception as e:
            print(f"ERROR initializing UI components: {e}")
            traceback.print_exc()
            raise
        
        # Initialize new components in v1.5.1
        try:
            print("Initializing camera feed panel...")
            self.camera_panel = CameraFeedPanel(self.monitor_tab, self.logger)
            self.camera_panel.pack(fill="both", expand=True, padx=5, pady=5)
            print("Camera feed panel initialized successfully")
        except Exception as e:
            print(f"ERROR initializing camera feed panel: {e}")
            traceback.print_exc()
            # Continue without camera panel
        
        try:
            print("Initializing health status panel...")
            self.health_panel = HealthStatusPanel(self.health_tab, self.logger)
            self.health_panel.pack(fill="both", expand=True, padx=5, pady=5)
            print("Health status panel initialized successfully")
        except Exception as e:
            print(f"ERROR initializing health status panel: {e}")
            traceback.print_exc()
            # Continue without health panel

        # SKIP LOG REDIRECTORS - potential cause of crash
        print("SKIPPING log redirectors for debugging")
        # DO NOT initialize redirector
        # sys.stdout = self.LogRedirector(self)
        # sys.stderr = self.LogRedirector(self)

        # Verify directories
        try:
            print("Verifying directories...")
            self.verify_directories()
            print("Directories verified successfully")
        except Exception as e:
            print(f"ERROR verifying directories: {e}")
            traceback.print_exc()
        
        # Log startup success
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
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            self.clock_label.config(text=current_time)
            self.root.after(1000, self.update_clock)
        except Exception as e:
            print(f"Error updating clock: {e}")
            # Don't reschedule on error

    def initialize_basic_components(self):
        """Initialize minimal GUI components"""
        try:
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
            
            # Initialize test interface - Re-enabled in v1.5.1
            try:
                test_scroll = ttk.Frame(self.test_tab)
                test_scroll.pack(fill="both", expand=True)
                
                self.test_interface = TestInterface(test_scroll, self.logger, self.alert_manager)
            except Exception as e:
                print(f"Error initializing test interface: {e}")
                traceback.print_exc()
                # Show an error message in the test tab
                error_label = ttk.Label(
                    self.test_tab,
                    text=f"Error initializing test interface: {str(e)}",
                    foreground="red",
                    wraplength=600
                )
                error_label.pack(padx=20, pady=20)
            
        except Exception as e:
            print(f"Error initializing basic components: {e}")
            traceback.print_exc()
            raise

    def log_message(self, message, level="INFO"):
        """Log message to log window"""
        try:
            if self.log_window:
                self.log_window.log_message(message, level)
            else:
                print(f"[{level}] {message}")
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
        try:
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
        except Exception as e:
            self.log_message(f"Error toggling local saving: {e}", "ERROR")

    def toggle_email_alerts(self):
        """Handle email alerts toggle"""
        try:
            is_enabled = self.email_alerts_enabled.get()
            self.log_message(f"Email alerts {'enabled' if is_enabled else 'disabled'}")
            
            # Set environment variable for child processes
            os.environ['OWL_EMAIL_ALERTS'] = str(is_enabled)
        except Exception as e:
            self.log_message(f"Error toggling email alerts: {e}", "ERROR")

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
            self.buffer = ""

        def write(self, message):
            try:
                self.buffer += message
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    for line in lines[:-1]:  # Process all but the last line
                        if line.strip():
                            if "error" in line.lower():
                                self.app.log_message(line.strip(), "ERROR")
                            elif "warning" in line.lower():
                                self.app.log_message(line.strip(), "WARNING")
                            else:
                                self.app.log_message(line.strip(), "INFO")
                    self.buffer = lines[-1]  # Keep the last line in buffer
            except Exception as e:
                print(f"Error in log redirector: {e}")
                # Fall back to standard output
                sys.__stdout__.write(message)

        def flush(self):
            if self.buffer.strip():
                try:
                    self.app.log_message(self.buffer.strip(), "INFO")
                except:
                    sys.__stdout__.write(self.buffer)
                self.buffer = ""

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
        try:
            # Release lock before restarting
            release_lock()
            
            self.root.destroy()
            python_executable = sys.executable
            script_path = os.path.join(SCRIPTS_DIR, "_front_end.py")
            os.execv(python_executable, [python_executable, script_path])
        except Exception as e:
            print(f"Error restarting application: {e}")
            # Try to recover by reopening
            subprocess.Popen([sys.executable, os.path.join(SCRIPTS_DIR, "_front_end.py")])
            sys.exit(1)

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
    
    def on_closing(self):
        """Handle window closing event"""
        try:
            # Stop any running scripts
            if self.script_process:
                self.stop_script()
            
            # Clean up component resources
            if self.camera_panel:
                self.camera_panel.destroy()
                
            if self.health_panel:
                self.health_panel.destroy()
                
            if self.lighting_panel:
                self.lighting_panel.destroy()
            
            # Release the lock file
            release_lock()
            
            # Destroy the root window
            self.root.destroy()
        except Exception as e:
            print(f"Error during shutdown: {e}")
            # Force exit if clean shutdown fails
            os._exit(1)

def main():
    try:
        print("Creating Tkinter root window...")
        
        # Register a function to release lock on unexpected exit
        atexit.register(release_lock)
        
        # Initialize root window
        root = tk.Tk()
        
        # Initialize logger
        try:
            logger = get_logger()
            logger.info("Tkinter root window created")
        except Exception as e:
            print(f"WARNING: Could not initialize logger: {e}")
        
        # Short delay for window manager
        root.after(100)
        
        # Create application
        app = OwlApp(root)
        
        # Log final window geometry
        print(f"Final window geometry: {root.geometry()}")
        logger.info(f"Final window geometry: {root.geometry()}")
        
        # Start main loop
        print("Starting Tkinter main loop...")
        root.mainloop()
        
        # Clean shutdown
        print("Application closed normally")
        release_lock()
        
    except Exception as e:
        print(f"Fatal error in GUI: {e}")
        traceback.print_exc()
        # Clean up lock on error
        release_lock()
        # Show error message
        try:
            tk.messagebox.showerror("Fatal Error", f"The application encountered a fatal error:\n\n{e}")
        except:
            pass
        raise

if __name__ == "__main__":
    main()