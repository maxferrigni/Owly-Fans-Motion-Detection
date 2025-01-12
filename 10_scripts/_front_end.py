import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import datetime  # For timestamping logs
import time as sleep_time  # For pauses in idle state

class OwlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Owl Monitoring App")
        print("Initializing Owl Monitoring App...")  # Debug: App initialization

        # Set the window geometry (704x355 at position -1915, 30 for secondary monitor)
        width = 704
        height = 355
        x_offset = -1915  # Position for top-left of the secondary monitor
        y_offset = 30

        try:
            # Use wm_geometry for precise positioning
            self.root.geometry(f"{width}x{height}+{x_offset}+{y_offset}")
            self.root.update_idletasks()
            print(f"Window positioned to {x_offset}, {y_offset}...")  # Debug: Window positioned
        except Exception as e:
            print(f"Error positioning window: {e}")  # Debug: Positioning error

        self.script_process = None

        # Add Start and Stop buttons
        self.start_button = tk.Button(root, text="Start Motion Detection", command=self.start_script, width=20)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Motion Detection", command=self.stop_script, state=tk.DISABLED, width=20)
        self.stop_button.pack(pady=10)

        # Add a log display
        self.log_display = scrolledtext.ScrolledText(root, width=80, height=15, wrap=tk.WORD)
        self.log_display.pack(pady=10)

        # Log initialization
        self.log_message("Log initialized.")

    def start_script(self):
        if not self.script_process:
            self.log_message("Starting motion detection script...")
            print("Starting motion_detection.py...")  # Debug: Starting the script
            try:
                self.script_process = subprocess.Popen(
                    ["python3", "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/10 GIT/Owly-Fans-Motion-Detection/10 scripts/motion_detection.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stdout and stderr into one stream
                    text=True,
                    bufsize=1,  # Line-buffered output
                )
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
                threading.Thread(target=self.refresh_logs, daemon=True).start()  # Run log refresh in a thread
            except Exception as e:
                self.log_message(f"Error starting script: {e}")
                print(f"Error starting script: {e}")  # Debug: Error when starting script

    def stop_script(self):
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            print("Stopping motion_detection.py...")  # Debug: Stopping the script
            try:
                self.script_process.terminate()
                self.script_process.wait()
                self.script_process = None
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
            except Exception as e:
                self.log_message(f"Error stopping script: {e}")
                print(f"Error stopping script: {e}")  # Debug: Error when stopping script

    def refresh_logs(self):
        """Read logs from the subprocess and display them in the GUI."""
        print("Refreshing logs...")  # Debug: Refresh logs initiated
        try:
            while self.script_process and self.script_process.stdout:
                # Read one line from the script's output
                line = self.script_process.stdout.readline()
                if line.strip():
                    # If there's a log from the script, display it
                    log_message = line.strip()
                    self.log_message(f"{log_message}")
                    print(f"Log: {log_message}")  # Debug: Log output to terminal
                else:
                    # If no log is present, display "Nothing Detected" every second
                    idle_message = f"Nothing Detected at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    self.log_message(idle_message)
                    print(f"Log: {idle_message}")  # Debug: Log idle output to terminal
                    sleep_time.sleep(1)  # Wait for a second before retrying
        except Exception as e:
            self.log_message(f"Error reading logs: {e}")
            print(f"Error reading logs: {e}")  # Debug: Error while reading logs

    def log_message(self, message):
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)
        print(f"Log Message: {message}")  # Debug: Log message to terminal


if __name__ == "__main__":
    print("Launching Owl Monitoring App...")  # Debug: App launch
    root = tk.Tk()
    app = OwlApp(root)
    print("App is running...")  # Debug: App running
    root.mainloop()