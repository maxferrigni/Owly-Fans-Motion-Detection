# File: front_end_app.py
# Purpose: Main application window for the Owl Monitoring System
#
# March 7, 2025 Update - Version 1.4.3
# - Fixed application crash on startup issues
# - Completely rewrote image panel initialization
# - Adjusted window sizing for better display
# - Improved error handling throughout initialization

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import sys
import json
from datetime import datetime, timedelta
import pytz
from PIL import Image, ImageTk
import traceback
import time

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities and modules
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist, VERSION, BASE_DIR, BASE_IMAGES_DIR, IMAGE_COMPARISONS_DIR, get_base_image_path
from utilities.logging_utils import get_logger
from utilities.alert_manager import AlertManager
from utilities.time_utils import get_current_lighting_condition
from utilities.configs_loader import load_camera_config  # Import the config loader

# Import GUI panels
from front_end_panels import (
    LogWindow, 
    LightingInfoPanel,
    ControlPanel
)

# Import image viewer
from front_end_image_viewer import ImageViewer

# Import remaining components
from motion_detection_settings import MotionDetectionSettings
from wyze_camera_monitor import WyzeCameraMonitor

class OwlApp:
    def __init__(self, root):
        # Initialize logger immediately
        self.logger = get_logger()
        self.logger.info("Starting Owl Monitoring App initialization...")
        
        try:
            # Initialize window
            self.root = root
            self.root.title("Owl Monitoring App")
            self.root.geometry("900x650+-1920+0")  # Adjusted height for better fit
            self.root.minsize(900, 650)  # Set minimum size
            self.root.update_idletasks()
            self.root.resizable(True, True)  # Enable resizing

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
            
            # Add clock style
            self.style.configure('Clock.TLabel', foreground='darkblue', font=('Arial', 14, 'bold'))

            # Initialize managers
            self.alert_manager = AlertManager()
            
            # Create UI structure from top to bottom
            self.create_ui_structure()
            
            # Initialize redirector
            sys.stdout = self.LogRedirector(self)
            sys.stderr = self.LogRedirector(self)

            # Verify directories
            self.verify_directories()
            self.log_message("GUI initialized and ready", "INFO")
            
        except Exception as e:
            # Critical error handling - show error and log it
            error_msg = f"Critical error during initialization: {str(e)}\n\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            messagebox.showerror("Initialization Error", f"Error initializing application:\n{str(e)}")
            
    def create_ui_structure(self):
        """Create the entire UI structure in the correct order"""
        try:
            # Add environment and version labels
            self.env_label = ttk.Label(
                self.root,
                text="DEV ENVIRONMENT" if "Dev" in BASE_DIR else "PRODUCTION",
                font=("Arial", 12, "bold"),
                foreground="red" if "Dev" in BASE_DIR else "green"
            )
            self.env_label.pack(side="top", pady=5)

            # Create a frame for top elements (version label and clock)
            self.top_frame = ttk.Frame(self.root)
            self.top_frame.pack(side="top", fill="x", pady=2)
            
            # Add version label on the left
            self.version_label = ttk.Label(
                self.top_frame,
                text=f"Version: {VERSION}",
                font=("Arial", 8)
            )
            self.version_label.pack(side="left", padx=10)
            
            # Add clock on the right
            self.initialize_clock()
            
            # Add lighting information panel
            self.lighting_info_panel = LightingInfoPanel(self.root)
            self.lighting_info_panel.pack(side="top", pady=3, fill="x")

            # Create main container for center content
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
            
            # Create bottom panel for images AFTER main components
            self.initialize_image_panels()
            
            # Initialize Wyze camera monitor LAST (after all UI is ready)
            self.wyze_monitor = WyzeCameraMonitor()
            self.wyze_monitor.start_monitoring()
            
        except Exception as e:
            self.log_message(f"Error creating UI structure: {e}", "ERROR")
            # Show detailed traceback in logs
            self.logger.error(traceback.format_exc())
            raise

    def initialize_clock(self):
        """Initialize clock display in the upper right corner"""
        try:
            self.clock_frame = ttk.Frame(self.top_frame)
            self.clock_frame.pack(side="right", padx=10)
            
            self.clock_label = ttk.Label(
                self.clock_frame,
                style="Clock.TLabel"
            )
            self.clock_label.pack()
            
            # Start clock update
            self.update_clock()
        except Exception as e:
            self.log_message(f"Error initializing clock: {e}", "ERROR")

    def update_clock(self):
        """Update the clock display every second"""
        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            self.clock_label.config(text=current_time)
            self.root.after(1000, self.update_clock)  # Update every second
        except Exception as e:
            self.log_message(f"Error updating clock: {e}", "ERROR")

    def initialize_components(self):
        """Initialize all GUI components"""
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
                self.log_window,
                self.clear_saved_images
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
        except Exception as e:
            self.log_message(f"Error initializing components: {e}", "ERROR")
            # Show detailed traceback in logs
            self.logger.error(traceback.format_exc())
            raise

    def initialize_image_panels(self):
        """Initialize the image viewer panel at the bottom - completely rewritten for v1.4.3"""
        try:
            # Create a fixed-height frame at the bottom of root
            self.bottom_frame = ttk.Frame(self.root)
            self.bottom_frame.pack(side="bottom", fill="x", padx=2, pady=2)
            
            # Set explicit height and prevent propagation of child sizes
            self.bottom_frame.configure(height=180)
            self.bottom_frame.pack_propagate(False)
            
            # Load camera configurations with robust error handling
            try:
                camera_configs = load_camera_config()
                if not camera_configs:
                    self.log_message("No camera configs found, using empty configuration", "WARNING")
                    camera_configs = {}
            except Exception as e:
                self.log_message(f"Error loading camera configs: {e}", "ERROR")
                camera_configs = {}
            
            # Create a separator line above the image panel
            ttk.Separator(self.root, orient="horizontal").pack(fill="x", pady=2, before=self.bottom_frame)
            
            # Create the image viewer with explicit sizing
            try:
                self.image_viewer = ImageViewer(self.bottom_frame, camera_configs)
                self.image_viewer.pack(fill="both", expand=True)
                self.log_message("Image viewer initialized successfully", "INFO")
            except Exception as e:
                self.log_message(f"Error initializing image viewer: {e}", "ERROR")
                self.logger.error(traceback.format_exc())
                # Create a label instead of the image viewer as a fallback
                ttk.Label(
                    self.bottom_frame, 
                    text=f"Could not initialize image viewer: {str(e)}",
                    foreground="red"
                ).pack(fill="both", expand=True)
        except Exception as e:
            self.log_message(f"Error creating image panels: {e}", "ERROR")
            self.logger.error(traceback.format_exc())

    def log_message(self, message, level="INFO"):
        """Log message to log window with robust error handling"""
        try:
            if hasattr(self, 'log_window') and self.log_window:
                self.log_window.log_message(message, level)
            else:
                # Fall back to logger if log window isn't ready
                if level == "ERROR":
                    self.logger.error(message)
                elif level == "WARNING":
                    self.logger.warning(message)
                else:
                    self.logger.info(message)
        except Exception as e:
            # Last resort: print to console
            print(f"Error logging message: {e}")
            print(f"[{level}] {message}")

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
                # Give it 5 seconds to terminate gracefully
                try:
                    self.script_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # If it doesn't terminate, force kill it
                    self.log_message("Script did not terminate gracefully, forcing kill", "WARNING")
                    self.script_process.kill()
                    self.script_process.wait(timeout=2)
                
                self.script_process = None
                self.control_panel.update_run_state(False)
            except Exception as e:
                self.log_message(f"Error stopping script: {e}", "ERROR")

    def refresh_logs(self):
        """Refresh log display with script output - improved error handling for v1.4.3"""
        if not self.script_process or not self.script_process.stdout:
            self.log_message("No active script process for logs", "WARNING")
            return

        try:
            while self.script_process and self.script_process.poll() is None:
                try:
                    # Use readline with timeout to prevent blocking
                    line = self.script_process.stdout.readline()
                    if not line:
                        # Check if process is still running
                        if self.script_process.poll() is not None:
                            break
                        # Small sleep to prevent CPU spinning
                        time.sleep(0.1)
                        continue
                        
                    if line.strip():
                        self.log_message(line.strip())
                    
                    # Periodically yield control to keep UI responsive
                    try:
                        self.root.update_idletasks()
                    except tk.TclError:
                        # Root may be destroyed
                        break
                        
                except (ValueError, IOError) as e:
                    # Process pipe issues
                    self.log_message(f"Error reading process output: {e}", "ERROR")
                    break
                        
            # Process has ended or pipe closed
            exit_code = self.script_process.poll() if self.script_process else None
            self.log_message(f"Script process ended with exit code: {exit_code}", "INFO")
            self.script_process = None
            
            # Update UI safely
            try:
                if self.root.winfo_exists():
                    self.control_panel.update_run_state(False)
            except tk.TclError:
                pass  # Root window may have been destroyed
                
        except Exception as e:
            self.log_message(f"Error in log refresh thread: {e}", "ERROR")
            self.logger.error(traceback.format_exc())
            # Clean up process if error occurs
            if self.script_process:
                try:
                    self.script_process.terminate()
                except:
                    pass
                self.script_process = None
                
                # Update UI safely
                try:
                    if self.root.winfo_exists():
                        self.control_panel.update_run_state(False)
                except tk.TclError:
                    pass  # Root window may have been destroyed
    
    def clear_saved_images(self):
        """Permanently delete all images in the saved_images directory"""
        from tkinter import messagebox
        import os
        import shutil
        from utilities.constants import SAVED_IMAGES_DIR
        
        try:
            # Confirm action with user
            response = messagebox.askyesno(
                "Confirm Delete",
                "This will PERMANENTLY DELETE all saved images.\nThis cannot be undone. Continue?",
                icon='warning'
            )
            
            if not response:
                self.log_message("Clear saved images operation cancelled by user.")
                return
            
            if not os.path.exists(SAVED_IMAGES_DIR):
                self.log_message(f"Saved images directory not found: {SAVED_IMAGES_DIR}", "WARNING")
                return
            
            # Count files before deletion
            file_count = 0
            for file in os.listdir(SAVED_IMAGES_DIR):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    file_count += 1
            
            if file_count == 0:
                self.log_message("No images found to delete.")
                messagebox.showinfo("No Images", "No saved images were found to delete.")
                return
            
            # Delete all image files in the directory
            deleted_count = 0
            for file in os.listdir(SAVED_IMAGES_DIR):
                file_path = os.path.join(SAVED_IMAGES_DIR, file)
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    os.unlink(file_path)
                    deleted_count += 1
            
            self.log_message(f"Successfully deleted {deleted_count} saved images.", "INFO")
            messagebox.showinfo("Success", f"Successfully deleted {deleted_count} saved images.")
            
        except Exception as e:
            self.log_message(f"Error clearing saved images: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to clear saved images: {e}")