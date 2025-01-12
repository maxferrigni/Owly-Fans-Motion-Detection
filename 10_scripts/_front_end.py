# _front_end.py

import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import datetime
import time as sleep_time


class OwlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Owl Monitoring App")
        print("Initializing Owl Monitoring App...")  # Debug: App initialization

        # Set the window geometry
        self.root.geometry("704x355+-1915+30")

        self.script_process = None
        self.in_darkness_only = tk.BooleanVar(value=True)  # Default: In Darkness Only

        # Add Start and Stop buttons
        self.start_button = tk.Button(root, text="Start Motion Detection", command=self.start_script, width=20)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Motion Detection", command=self.stop_script, state=tk.DISABLED, width=20)
        self.stop_button.pack(pady=10)

        # Add the toggle for "In Darkness Only" or "All the Time"
        self.darkness_toggle = tk.Checkbutton(
            root,
            text="Work in Darkness Only",
            variable=self.in_darkness_only,
            onvalue=True,
            offvalue=False,
        )
        self.darkness_toggle.pack(pady=10)

        # Add a log display
        self.log_display = scrolledtext.ScrolledText(root, width=80, height=15, wrap=tk.WORD)
        self.log_display.pack(pady=10)

        # Log initialization
        self.log_message("Log initialized.")

    def start_script(self):
        if not self.script_process:
            mode = "In Darkness Only" if self.in_darkness_only.get() else "All the Time"
            self.log_message(f"Starting motion detection script in mode: {mode}")
            try:
                self.script_process = subprocess.Popen(
                    [
                        "python3",
                        "/Users/maxferrigni/Insync/maxferrigni@gmail.com/Google Drive/01 - Owl Box/60 IT/20 Motion Detection/10 GIT/Owly-Fans-Motion-Detection/10 scripts/motion_detection.py",
                        "--darkness" if self.in_darkness_only.get() else "--all",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
                threading.Thread(target=self.refresh_logs, daemon=True).start()
            except Exception as e:
                self.log_message(f"Error starting script: {e}")

    def stop_script(self):
        if self.script_process:
            self.log_message("Stopping motion detection script...")
            try:
                self.script_process.terminate()
                self.script_process.wait()
                self.script_process = None
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
            except Exception as e:
                self.log_message(f"Error stopping script: {e}")

    def refresh_logs(self):
        try:
            while self.script_process and self.script_process.stdout:
                line = self.script_process.stdout.readline()
                if line.strip():
                    self.log_message(line.strip())
        except Exception as e:
            self.log_message(f"Error reading logs: {e}")

    def log_message(self, message):
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)
        print(message)


if __name__ == "__main__":
    root = tk.Tk()
    app = OwlApp(root)
    root.mainloop()
