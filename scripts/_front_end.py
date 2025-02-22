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

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("800x455+-1920+0")  # Increased width for better spacing
        self.root.update_idletasks()
        self.root.resizable(False, False)

        # Initialize variables
        self.script_process = None
        self.alert_delay_enabled = tk.BooleanVar(value=True)
        self.alert_delay_minutes = tk.StringVar(value="30")
        self.local_saving_enabled = tk.BooleanVar(value=False)  # New local saving toggle
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")

        # Initialize alert manager
        self.alert_manager = AlertManager()

        # Create GUI elements
        self._create_gui()

        # Initialize logger
        self.logger = get_logger()
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)

        # Initialize test interface
        self.test_interface = TestInterface(self.root, self.logger, self.alert_manager)

        # Ensure directories exist
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

    def _create_gui(self):
        """Create main GUI elements"""
        # Update System button
        self.update_button = tk.Button(
            self.root,
            text="Update System",
            command=self.update_system,
            width=20,
            bg='lightblue',
            activebackground='skyblue',
            font=('Arial', 10)
        )
        self.update_button.pack(pady=5)

        # Motion Detection buttons
        self.start_button = tk.Button(
            self.root,
            text="Start Motion Detection",
            command=self.start_script,
            width=20,
            bg='lightgreen',
            activebackground='palegreen',
            font=('Arial', 10)
        )
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(
            self.root,
            text="Stop Motion Detection",
            command=self.stop_script,
            state=tk.DISABLED,
            width=20,
            bg='salmon',
            activebackground='lightcoral',
            font=('Arial', 10)
        )
        self.stop_button.pack(pady=5)

        # Alert Delay frame
        self.alert_delay_frame = tk.Frame(self.root)
        self.alert_delay_frame.pack(pady=5)

        self.alert_delay_button = tk.Checkbutton(
            self.alert_delay_frame,
            text="Alert Delay",
            variable=self.alert_delay_enabled,
            command=self.toggle_alert_delay,
            width=10
        )
        self.alert_delay_button.pack(side=tk.LEFT, padx=5)

        self.alert_delay_entry = ttk.Entry(
            self.alert_delay_frame,
            textvariable=self.alert_delay_minutes,
            width=5
        )
        self.alert_delay_entry.pack(side=tk.LEFT)

        tk.Label(
            self.alert_delay_frame,
            text="minutes"
        ).pack(side=tk.LEFT, padx=5)

        # Local Saving frame
        self.local_saving_frame = tk.Frame(self.root)
        self.local_saving_frame.pack(pady=5)

        # Local saving toggle with custom colors and styling
        self.local_saving_button = tk.Checkbutton(
            self.local_saving_frame,
            text="Save Images Locally",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving,
            width=20,
            bg='light gray',
            activebackground='gray',
            selectcolor='light green',
            font=('Arial', 10)
        )
        self.local_saving_button.pack(pady=5)

        # Log display
        self.log_display = scrolledtext.ScrolledText(
            self.root,
            width=80,
            height=15,
            wrap=tk.WORD
        )
        self.log_display.pack(pady=10)

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
                # Pass local saving setting through environment variable
                env = os.environ.copy()
                env['OWL_LOCAL_SAVING'] = str(self.local_saving_enabled.get())
                
                cmd = [sys.executable, self.main_script_path]
                self.script_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
                self.update_button.config(state=tk.DISABLED)
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
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.update_button.config(state=tk.NORMAL)
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
        """Add a message to the log display"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            self.log_display.insert(tk.END, f"{formatted_message}\n")
            self.log_display.see(tk.END)
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