import tkinter as tk
from tkinter import scrolledtext
import subprocess

class OwlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Owl Monitoring App")
        self.script_process = None

        # Create buttons
        self.start_button = tk.Button(root, text="Start Motion Detection", command=self.start_script, width=20)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Motion Detection", command=self.stop_script, state=tk.DISABLED, width=20)
        self.stop_button.pack(pady=10)

        # Create a log display
        self.log_display = scrolledtext.ScrolledText(root, width=60, height=20, wrap=tk.WORD)
        self.log_display.pack(pady=10)

        # Add periodic log refresh
        self.refresh_logs()

    def start_script(self):
        if not self.script_process:
            self.log_message("Starting motion detection script...")
            try:
                self.script_process = subprocess.Popen(
                    ["python3", "motion_detection.py"],  # Replace with the actual script path if necessary
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
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
        if self.script_process and self.script_process.stdout:
            try:
                output = self.script_process.stdout.readline()
                if output:
                    self.log_message(output.strip())
            except Exception as e:
                self.log_message(f"Error reading logs: {e}")
        self.root.after(1000, self.refresh_logs)

    def log_message(self, message):
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = OwlApp(root)
    root.mainloop()
