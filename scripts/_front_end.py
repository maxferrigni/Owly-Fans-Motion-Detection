# File: _front_end.py
# Purpose: Graphical user interface for the Owl Monitoring System

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import sys
from datetime import datetime

# Import utilities
from utilities.constants import SCRIPTS_DIR, ensure_directories_exist
from utilities.logging_utils import get_logger

class OwlApp:
    def __init__(self, root):
        # Initialize logger
        self.logger = get_logger()
        
        # Initialize window
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("704x455+-1920+0")
        
        # Initialize variables
        self.script_process = None
        self.in_darkness_only = tk.BooleanVar(value=True)
        
        # Store the path of main.py
        self.main_script_path = os.path.join(SCRIPTS_DIR, "main.py")
        
        # Create GUI elements
        self._create_gui()
        
        # Ensure directories exist
        ensure_directories_exist()
        
        # Log initialization
        self.log_message("GUI initialized")
        
        # Update UI
        self.root.update()

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

        # Add the toggle for "In Darkness Only"
        self.darkness_toggle = tk.Checkbutton(
            self.root,
            text="Work in Darkness Only",
            variable=self.in_darkness_only,
            onvalue=True,
            offvalue=False
        )
        self.darkness_toggle.pack(pady=10)

        # Add a log display
        self.log_display = scrolledtext.ScrolledText(
            self.root, 
            width=80, 
            height=15, 
            wrap=tk.WORD
        )
        self.log_display.pack(pady=10)

    def update_system(self):
        """Update the system from git repository"""
        if self.script_process:
            messagebox.showwarning("Warning", "Please stop motion detection before updating.")
            return

        try:
            self.log_message("Resetting local repository and pulling latest updates...")

            # Perform a hard reset and clean
            result_reset = subprocess.run(
                ["git", "reset", "--hard"],
                capture_output=True,
                text=True
            )
            result_clean = subprocess.run(
                ["git", "clean", "-fd"],
                capture_output=True,
                text=True
            )

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
            mode = "In Darkness Only" if self.in_darkness_only.get() else "All the Time"
            self.log_message(f"Starting motion detection script in mode: {mode}")
            try:
                cmd = [sys.executable, self.main_script_path]
                if self.in_darkness_only.get():
                    cmd.append("--darkness")
                
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
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_display.insert(tk.END, f"{formatted_message}\n")
        self.log_display.see(tk.END)
        self.logger.info(message)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = OwlApp(root)
        root.mainloop()
    except Exception as e:
        logger = get_logger()
        logger.error(f"Fatal error in GUI: {e}")
        raise