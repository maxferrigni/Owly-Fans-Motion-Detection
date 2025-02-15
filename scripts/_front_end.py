# File: _front_end.py
# Purpose: Graphical user interface for the Owl Monitoring System

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import sys
from datetime import datetime

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import utilities
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist
from utilities.logging_utils import get_logger

class OwlApp:
    def __init__(self, root):
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        
        # Set window size and position
        window_width = 704
        window_height = 455
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate position for center of primary screen
        x_position = int((screen_width - window_width) / 2)
        y_position = int((screen_height - window_height) / 2)
        
        # Set geometry and force update
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        self.root.update_idletasks()  # Force geometry update
        
        # Prevent window resizing
        self.root.resizable(False, False)
        
        # Force window to stay on top initially
        self.root.attributes('-topmost', True)
        self.root.update()
        self.root.attributes('-topmost', False)
        
        # Initialize variables
        self.script_process = None
        
        # Store the path of main.py
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")
        
        # Create GUI elements
        self._create_gui()
        
        # Initialize logger after GUI creation so we can capture output
        self.logger = get_logger()
        sys.stdout = self.LogRedirector(self)
        sys.stderr = self.LogRedirector(self)
        
        # Ensure directories exist
        self.verify_directories()
        
        # Log initialization
        self.log_message("GUI initialized and ready")
        
        # Update UI
        self.root.update()

    class LogRedirector:
        def __init__(self, app):
            self.app = app

        def write(self, message):
            if message.strip():  # Only log non-empty messages
                self.app.log_message(message.strip())

        def flush(self):
            pass

    def _create_gui(self):
        """Create all GUI elements"""
        # Add Update System button at the top
        self.update_button = tk.Button(
            self.root, 
            text="Update System", 
            command=self.update_system,
            width=20,
            bg='lightblue'
        )
        self.update_button.pack(pady=10)

        # Add Start and Stop buttons
        self.start_button = tk.Button(
            self.root, 
            text="Start Motion Detection", 
            command=self.start_script, 
            width=20
        )
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(
            self.root, 
            text="Stop Motion Detection", 
            command=self.stop_script, 
            state=tk.DISABLED, 
            width=20
        )
        self.stop_button.pack(pady=10)

        # Add a log display
        self.log_display = scrolledtext.ScrolledText(
            self.root, 
            width=80, 
            height=15, 
            wrap=tk.WORD
        )
        self.log_display.pack(pady=10)

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

            # Change to Git repository directory
            original_dir = os.getcwd()
            os.chdir(os.path.dirname(SCRIPTS_DIR))

            try:
                # Perform a hard reset and clean
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

                # Perform git pull
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
                # Restore original directory
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
                cmd = [sys.executable, self.main_script_path]
                
                self.script_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
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
        
        # Force a short delay to ensure window manager is ready
        root.after(100)
        
        app = OwlApp(root)
        logger.info(f"Final window geometry: {root.geometry()}")
        root.mainloop()
    except Exception as e:
        print(f"Fatal error in GUI: {e}")
        raise