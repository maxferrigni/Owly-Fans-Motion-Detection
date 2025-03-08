# File: health_status_panel.py
# Purpose: Display system health monitoring information
# Version: 1.5.1

import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime
import os
import sys

from utilities.logging_utils import get_logger

class HealthStatusPanel(ttk.LabelFrame):
    """Panel to display system health status and monitoring information"""
    
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="System Health Monitor")
        
        self.logger = logger or get_logger()
        
        # Store system components to monitor
        self.components = {
            "Main Script": {"status": "Unknown", "healthy": False},
            "Camera Feeds": {"status": "Unknown", "healthy": False},
            "OBS Process": {"status": "Unknown", "healthy": False},
            "Disk Space": {"status": "Unknown", "healthy": False}
        }
        
        # Monitoring state
        self.monitoring_thread = None
        self.running = False
        
        # Create panel components
        self.create_interface()
        
        # Start monitoring in background
        self.start_monitoring()
    
    def create_interface(self):
        """Create the health status interface components"""
        try:
            # Main container
            main_frame = ttk.Frame(self)
            main_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Status indicators
            self.status_frames = {}
            self.status_indicators = {}
            
            # Create a box for each monitored component
            for i, (component, info) in enumerate(self.components.items()):
                # Create frame for this component
                component_frame = ttk.LabelFrame(main_frame, text=component)
                component_frame.grid(row=i//2, column=i%2, padx=5, pady=5, sticky="nsew")
                
                # Status indicator (colored circle)
                indicator = tk.Canvas(component_frame, width=20, height=20)
                indicator.pack(side=tk.LEFT, padx=5, pady=5)
                
                # Draw circle with default gray color
                circle = indicator.create_oval(2, 2, 18, 18, fill="gray", outline="black")
                
                # Status text
                status_var = tk.StringVar(value=info["status"])
                status_label = ttk.Label(
                    component_frame,
                    textvariable=status_var,
                    padding=(5, 5)
                )
                status_label.pack(side=tk.LEFT, fill="x", expand=True)
                
                # Store references
                self.status_frames[component] = component_frame
                self.status_indicators[component] = {
                    "canvas": indicator,
                    "circle": circle,
                    "status_var": status_var
                }
            
            # Configure grid weights
            rows = (len(self.components) + 1) // 2
            cols = min(2, len(self.components))
            
            for i in range(rows):
                main_frame.rowconfigure(i, weight=1)
            for i in range(cols):
                main_frame.columnconfigure(i, weight=1)
            
            # Add last check time display
            footer_frame = ttk.Frame(self)
            footer_frame.pack(fill="x", padx=5, pady=5)
            
            self.last_check_var = tk.StringVar(value="Last check: Never")
            last_check_label = ttk.Label(
                footer_frame,
                textvariable=self.last_check_var
            )
            last_check_label.pack(side=tk.LEFT, padx=5)
            
            # Add manual check button
            check_button = ttk.Button(
                footer_frame,
                text="Check Now",
                command=self.check_health
            )
            check_button.pack(side=tk.RIGHT, padx=5)
            
            self.logger.info("Health status panel initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error creating health status interface: {e}")
            error_label = ttk.Label(
                self,
                text=f"Error initializing health status panel: {e}",
                foreground="red"
            )
            error_label.pack(padx=10, pady=10)
    
    def update_component_status(self, component, status, healthy):
        """Update the status of a monitored component"""
        try:
            if component not in self.status_indicators:
                return
                
            # Update status text
            self.status_indicators[component]["status_var"].set(status)
            
            # Update indicator color
            color = "green" if healthy else "red"
            canvas = self.status_indicators[component]["canvas"]
            circle = self.status_indicators[component]["circle"]
            canvas.itemconfig(circle, fill=color)
            
            # Update component info
            self.components[component]["status"] = status
            self.components[component]["healthy"] = healthy
            
        except Exception as e:
            self.logger.error(f"Error updating component status: {e}")
    
    def check_health(self):
        """Perform a comprehensive health check of all system components"""
        try:
            self.logger.info("Performing system health check")
            
            # Update last check time
            check_time = datetime.now().strftime('%H:%M:%S')
            self.last_check_var.set(f"Last check: {check_time}")
            
            # Check each component
            self.check_main_script()
            self.check_camera_feeds()
            self.check_obs_process()
            self.check_disk_space()
            
            # Determine overall health
            overall_healthy = all(info["healthy"] for info in self.components.values())
            
            self.logger.info(f"Health check completed: System {'' if overall_healthy else 'NOT '}healthy")
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {e}")
    
    def check_main_script(self):
        """Check if the main motion detection script is running"""
        try:
            # Look for script process in parent application
            parent_window = self.winfo_toplevel()
            if hasattr(parent_window, 'script_process') and parent_window.script_process:
                # Check if process is still running
                process = parent_window.script_process
                if process.poll() is None:  # None means still running
                    self.update_component_status("Main Script", "Running", True)
                else:
                    exit_code = process.poll()
                    self.update_component_status("Main Script", f"Exited (code: {exit_code})", False)
            else:
                self.update_component_status("Main Script", "Not running", False)
        except Exception as e:
            self.logger.error(f"Error checking main script: {e}")
            self.update_component_status("Main Script", f"Error: {str(e)[:20]}", False)
    
    def check_camera_feeds(self):
        """Check if camera feed images are being updated"""
        try:
            from utilities.constants import IMAGE_COMPARISONS_DIR, COMPARISON_IMAGE_FILENAMES
            
            # Look for comparison images and check their timestamps
            if os.path.exists(IMAGE_COMPARISONS_DIR):
                # Get the newest comparison image
                newest_time = 0
                newest_file = None
                
                for filename in COMPARISON_IMAGE_FILENAMES.values():
                    file_path = os.path.join(IMAGE_COMPARISONS_DIR, filename)
                    if os.path.exists(file_path):
                        mod_time = os.path.getmtime(file_path)
                        if mod_time > newest_time:
                            newest_time = mod_time
                            newest_file = file_path
                
                if newest_file:
                    # Check if the newest image is recent (within last 5 minutes)
                    age_seconds = time.time() - newest_time
                    if age_seconds < 300:  # 5 minutes
                        self.update_component_status(
                            "Camera Feeds", 
                            f"Updated {int(age_seconds)}s ago", 
                            True
                        )
                    else:
                        # Convert to minutes if more than 5 minutes
                        age_minutes = age_seconds / 60
                        self.update_component_status(
                            "Camera Feeds",
                            f"Stale ({int(age_minutes)}m old)",
                            False
                        )
                else:
                    self.update_component_status("Camera Feeds", "No images found", False)
            else:
                self.update_component_status("Camera Feeds", "Directory not found", False)
        except Exception as e:
            self.logger.error(f"Error checking camera feeds: {e}")
            self.update_component_status("Camera Feeds", f"Error: {str(e)[:20]}", False)
    
    def check_obs_process(self):
        """Check if OBS is running (basic check)"""
        try:
            # Simple check for process by name
            # More robust would use psutil but avoiding extra dependencies
            import subprocess
            
            if sys.platform == "win32":
                # Windows - use tasklist
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"],
                    capture_output=True,
                    text=True
                )
                is_running = "obs64.exe" in result.stdout
            else:
                # Unix-like - use ps and grep
                result = subprocess.run(
                    ["ps", "-ax"],
                    capture_output=True,
                    text=True
                )
                is_running = any("obs" in line.lower() for line in result.stdout.splitlines())
            
            if is_running:
                self.update_component_status("OBS Process", "Running", True)
            else:
                self.update_component_status("OBS Process", "Not running", False)
                
        except Exception as e:
            self.logger.error(f"Error checking OBS process: {e}")
            self.update_component_status("OBS Process", f"Error: {str(e)[:20]}", False)
    
    def check_disk_space(self):
        """Check available disk space"""
        try:
            from utilities.constants import LOCAL_FILES_DIR
            
            # Get disk usage statistics
            if sys.platform == "win32":
                # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(LOCAL_FILES_DIR), 
                    None, None,
                    ctypes.pointer(free_bytes)
                )
                free_gb = free_bytes.value / (1024**3)
            else:
                # Unix-like
                import os
                stats = os.statvfs(LOCAL_FILES_DIR)
                free_gb = (stats.f_frsize * stats.f_bavail) / (1024**3)
            
            # Check if enough space is available (1GB minimum)
            if free_gb > 1.0:
                self.update_component_status(
                    "Disk Space", 
                    f"{free_gb:.1f} GB available", 
                    True
                )
            else:
                self.update_component_status(
                    "Disk Space",
                    f"Low: {free_gb:.1f} GB",
                    False
                )
                
        except Exception as e:
            self.logger.error(f"Error checking disk space: {e}")
            self.update_component_status("Disk Space", f"Error: {str(e)[:20]}", False)
    
    def start_monitoring(self):
        """Start the health monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return  # Already running
            
        self.running = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """Stop the health monitoring thread"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
        self.logger.info("Health monitoring stopped")
    
    def monitoring_loop(self):
        """Background thread to check health periodically"""
        check_interval = 60  # seconds
        
        while self.running:
            try:
                # Perform health check
                self.check_health()
                
                # Sleep in small increments to allow for clean shutdown
                for _ in range(check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                # Sleep before retry
                time.sleep(check_interval)
    
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        self.stop_monitoring()
        super().destroy()


if __name__ == "__main__":
    # Test code for standalone testing
    root = tk.Tk()
    root.title("Health Status Panel Test")
    
    # Create logger
    try:
        from utilities.logging_utils import get_logger
        logger = get_logger()
    except:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger()
    
    # Create panel
    panel = HealthStatusPanel(root, logger)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Start the main loop
    root.mainloop()