# File: _front_end.py
# Purpose:
# This script provides a graphical user interface (GUI) for the Owl Monitoring System.
# It allows users to control motion detection settings, monitor logs in real time,
# and update the system files from git.
# Features:
# - Start and stop motion detection scripts with a button
# - Toggle between "In Darkness Only" and "All the Time" operational modes
# - Display real-time logs of motion detection activity
# - Git pull functionality to update system files (excluding this frontend script)
# - Auto-restart after updates
# Typical Usage:
# Run this script to launch the GUI: `python _front_end.py`
# Use the "Update System" button to pull latest changes from git

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import shutil
from datetime import datetime

class OwlApp:
    def __init__(self, root):
        # Initialize window first
        self.root = root
        self.root.title("Owl Monitoring App")
        self.root.geometry("704x455+1917+24")
        
        # Initialize variables first
        self.script_process = None
        self.in_darkness_only = tk.BooleanVar(value=True)
        
        # Store the path of this script
        self.frontend_path = os.path.abspath(__file__)
        
        # Create GUI elements
        self._create_gui()
        
        # Log initialization
        self.log_message("Log initialized.")
        
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

        # Add the toggle for "In Darkness Only" or "All the Time"
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
        """Update all system files from git except this frontend script"""
        if self.script_process:
            messagebox.showwarning(
                "Warning", 
                "Please stop motion detection before updating."
            )
            return

        try:
            # Store backup path
            backup_path = f"{self.frontend_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            
            # Backup this script
            shutil.copy2(self.frontend_path, backup_path)
            self.log_message(f"Created backup at {backup_path}")

            # Perform git pull
            self.log_message("Performing git pull...")
            result = subprocess.run(
                ['git', 'pull'], 
                capture_output=True, 
                text=True
            )

            if result.returncode == 0:
                self.log_message("Git pull successful.")
                
                # Restore our frontend script from backup
                shutil.copy2(backup_path, self.frontend_path)
                self.log_message("Restored frontend script from backup.")

                # Ask user if they want to restart
                if messagebox.askyesno(
                    "Update Complete", 
                    "System updated successfully. Restart application?"
                ):
                    self.restart_application()
            else:
                self.log_message(f"Git pull failed: {result.stderr}")

        except Exception as e:
            self.log_message(f"Error during update: {e}")
            # Restore from backup if we have one
            if 'backup_path' in locals() and os.path.exists(backup_path):
                shutil.copy2(backup_path, self.frontend_path)
                self.log_message("Restored frontend script from backup after error.")

    def restart_application(self):
        """Restart the application using the same interpreter"""
        self.root.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def start_script(self):
        """Start the motion detection script"""
        if not self.script_process:
            mode = "In Darkness Only" if self.in_darkness_only.get() else "All the Time"
            self.log_message(f"Starting motion detection script in mode: {mode}")
            try:
                script_path = os.path.join(os.path.dirname(self.frontend_path), "main.py")
                self.script_process = subprocess.Popen(
                    [
                        sys.executable,
                        script_path,
                        "--darkness" if self.in_darkness_only.get() else "--all",
                    ],
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
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)
        print(message)

if __name__ == "__main__":
    print("Starting Tkinter application...")
    root = tk.Tk()
    print("Creating root window...")
    app = OwlApp(root)
    print("Created OwlApp, starting mainloop...")
    root.mainloop()
    print("Mainloop ended.")  # This will only print if the window is closed