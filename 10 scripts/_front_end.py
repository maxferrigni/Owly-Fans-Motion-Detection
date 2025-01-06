import tkinter as tk
from tkinter import scrolledtext
import subprocess


class OwlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Owl Monitoring App")
        self.script_process = None

        # Add Start and Stop buttons
        self.start_button = tk.Button(root, text="Start Motion Detection", command=self.start_script, width=20)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop Motion Detection", command=self.stop_script, state=tk.DISABLED, width=20)
        self.stop_button.pack(pady=10)

        # Add a log display
        self.log_display = scrolledtext.ScrolledText(root, width=60, height=20, wrap=tk.WORD)
        self.log_display.pack(pady=10)

        # Log initialization
        self.log_message("Log initialized.")

    def start_script(self):
        if not self.script_process:
            self.log_message("Starting motion detection script...")
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
                self.refresh_logs()  # Start the log refresh process
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
                # Read output from the script line by line
                output = self.script_process.stdout.readline()
                if output:
                    print(f"Debug: {output.strip()}")  # Print to terminal for debugging
                    self.log_message(output.strip())  # Display in the GUI log
            except Exception as e:
                self.log_message(f"Error reading logs: {e}")
        if self.script_process:
            # Schedule the next refresh
            self.root.after(100, self.refresh_logs)

    def log_message(self, message):
        self.log_display.insert(tk.END, f"{message}\n")
        self.log_display.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = OwlApp(root)
    root.mainloop()
