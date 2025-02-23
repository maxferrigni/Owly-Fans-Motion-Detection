# File: _front_end.py
# Purpose: Main GUI for the Owl Monitoring System

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
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
from test_interface import TestInterface
from motion_detection_settings import MotionDetectionSettings

class LogWindow(tk.Toplevel):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Configure window
        self.title("Owl Monitor Log")
        self.geometry("800x455")  # Match main window size
        self.resizable(False, False)
        
        # Create log display
        self.log_display = scrolledtext.ScrolledText(
            self,
            width=80,
            height=25,
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.log_display.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Keep reference to parent
        self.parent = parent
        
        # Position window
        self.position_window()
        
        # Bind parent movement to reposition log window
        parent.bind("<Configure>", self.follow_main_window)
        
    def position_window(self):
        """Position log window next to main window"""
        main_x = self.parent.winfo_x()
        main_y = self.parent.winfo_y()
        main_width = self.parent.winfo_width()
        
        # Position to the right of main window
        self.geometry(f"+{main_x + main_width + 10}+{main_y}")
        
    def follow_main_window(self, event=None):
        """Reposition log window when main window moves"""
        if event.widget == self.parent:
            self.position_window()
            
    def on_closing(self):
        """Handle window closing"""
        # Just hide the window instead of destroying
        self.withdraw()
        
    def show(self):
        """Show the log window"""
        self.deiconify()
        self.position_window()
        
    def log_message(self, message):
        """Add message to log display"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            self.log_display.insert(tk.END, f"{formatted_message}\n")
            self.log_display.see(tk.END)
        except Exception as e:
            print(f"Error logging to separate window: {e}")

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("800x455+-1920+0")
        self.root.update_idletasks()
        self.root.resizable(False, False)

        # Initialize variables
        self.script_process = None
        self.alert_delay_enabled = tk.BooleanVar(value=True)
        self.alert_delay_minutes = tk.StringVar(value="30")
        # Changed default to True for local saving
        self.local_saving_enabled = tk.BooleanVar(value=True)
        # NEW: Added capture interval variable with default 60 seconds
        self.capture_interval = tk.StringVar(value="60")
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Initialize managers
        self.alert_manager = AlertManager()
        self.logger = get_logger()

        # Create main container for better organization
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)

        # Create left and right panels for layout
        self.left_panel = ttk.Frame(self.main_container)
        self.left_panel.pack(side=tk.LEFT, fill="both", padx=5)

        self.right_panel = ttk.Frame(self.main_container)
        self.right_panel.pack(side=tk.LEFT, fill="both", expand=True, padx=5)

        # Initialize log window
        self.log_window = LogWindow(self.root)

        # Initialize components
        self._create_control_panel()
        self._create_settings_panel()
        self._create_test_panel()
        self._create_control_buttons()

        # Initialize redirector
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Verify directories
        self.verify_directories()
        self.log_message("GUI initialized and ready")

    class LogRedirector:
        def __init__(self, app):
            self.app = app

        def write(self, message):
            if message.strip():
                self.app.log_message(message.strip())

        def flush(self):
            pass

    def _create_control_panel(self):
        """Create main control buttons and options"""
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

        # Alert Delay frame
        delay_frame = ttk.Frame(control_frame)
        delay_frame.pack(pady=5)

        ttk.Checkbutton(
            delay_frame,
            text="Alert Delay",
            variable=self.alert_delay_enabled,
            command=self.toggle_alert_delay
        ).pack(side=tk.LEFT)

        self.alert_delay_entry = ttk.Entry(
            delay_frame,
            textvariable=self.alert_delay_minutes,
            width=5
        )
        self.alert_delay_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(delay_frame, text="minutes").pack(side=tk.LEFT)

        # NEW: Capture Interval frame
        interval_frame = ttk.Frame(control_frame)
        interval_frame.pack(pady=5)

        ttk.Label(interval_frame, text="Capture Interval:").pack(side=tk.LEFT)

        # Create combobox for interval selection
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

    def _create_settings_panel(self):
        """Create motion detection settings panel"""
        self.settings = MotionDetectionSettings(self.right_panel, self.logger)

    def _create_test_panel(self):
        """Create test interface panel"""
        test_frame = ttk.LabelFrame(self.left_panel, text="Testing")
        test_frame.pack(fill="x", pady=5)
        self.test_interface = TestInterface(test_frame, self.logger, self.alert_manager)

    def _create_control_buttons(self):
        """Create additional control buttons"""
        button_frame = ttk.Frame(self.right_panel)
        button_frame.pack(fill="x", pady=5)
        
        # Log window toggle button
        ttk.Button(
            button_frame,
            text="Toggle Log Window",
            command=self.toggle_log_window
        ).pack(side=tk.RIGHT, padx=5)

    def toggle_log_window(self):
        """Toggle log window visibility"""
        if self.log_window.winfo_viewable():
            self.log_window.withdraw()
        else:
            self.log_window.show()

    def toggle_local_saving(self):
        """Handle local saving toggle"""
        is_enabled = self.local_saving_enabled.get()
        self.log_message(f"Local image saving {'enabled' if is_enabled else 'disabled'}")
        
        # Set environment variable for child processes
        os.environ['OWL_LOCAL_SAVING'] = str(is_enabled)

        if is_enabled:
            # Ensure local directories exist
            try:
                ensure_directories_exist()
            except Exception as e:
                self.log_message(f"Error creating local directories: {e}")
                messagebox.showerror("Error", f"Failed to create local directories: {e}")
                self.local_saving_enabled.set(False)

    def toggle_alert_delay(self):
        """Handle alert delay toggle"""
        try:
            if self.alert_delay_enabled.get():
                delay = int(self.alert_delay_minutes.get())
                if delay < 1:
                    messagebox.showwarning("Invalid Delay", "Delay must be at least 1 minute")
                    self.alert_delay_minutes.set("1")
                    delay = 1
                self.alert_manager.set_alert_delay(delay)
                self.alert_delay_entry.config(state='normal')
                self.log_message(f"Alert delay enabled: {delay} minutes")
            else:
                self.alert_delay_entry.config(state='disabled')
                self.alert_manager.set_alert_delay(1)
                self.log_message("Alert delay disabled")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of minutes")
            self.alert_delay_minutes.set("30")
            self.alert_delay_enabled.set(True)

    def verify_directories(self):
        """Verify all required directories exist"""
        try:
            self.log_message("Verifying directory structure...")
            ensure_directories_exist()
            self.log_message("Directory verification complete")
        except Exception as e:
            self.log_message(f"Error verifying directories: {e}")
            messagebox.showerror("Error", f"Failed to verify directories: {e}")

    def update_system(self):
        """Update the system from git repository"""
        if self.script_process:
            messagebox.showwarning("Warning", "Please stop motion detection before updating.")
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
                    self.log_message(f"Git pull failed: {result_pull.stderr}")
                    messagebox.showerror("Update Failed", "Git pull failed. Check logs for details.")
            finally:
                os.chdir(original_dir)
        except Exception as e:
            self.log_message(f"Error during update: {e}")
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
                
                cmd = [sys.executable, self.main_script_path]
                self.script_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )

                # Update button states
                self.stop_button.config(state=tk.NORMAL)
                
                # Start log monitoring
                threading.Thread(target=self.refresh_logs, daemon=True).start()

            except Exception as e:
                self.log_message(f"Error starting script: {e}")

    def stop_script(self):
        """Stop the motion detection script"""
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            try:
                self.script_process.terminate()
                self.script_process.wait(timeout=5)
                self.script_process = None
                self.stop_button.config(state=tk.DISABLED)
            except Exception as e:
                self.log_message(f"Error stopping script: {e}")

    def refresh_logs(self):
        """Refresh the log display with new output"""
        try:
            while self.script_process and self.script_process.stdout:
                line = self.script_process.stdout.readline()
                if line.strip():
                    self.log_message(line.strip())
        except Exception as e:
            self.log_message(f"Error reading logs: {e}")
            
    def log_message(self, message):
        """Add a message to both log displays"""
        try:
            # Send to separate log window
            self.log_window.log_message(message)
        except Exception as e:
            print(f"Error logging message: {e}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        logger = get_logger()
        logger.info("Tkinter root window created")
        root.after(100)  # Short delay for window manager
        app = OwlApp(root)
        logger.info(f"Final window geometry: {root.geometry()}")
        root.mainloop()
    except Exception as e:
        print(f"Fatal error in GUI: {e}")
        raise