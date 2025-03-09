# File: _front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 8, 2025 Update - Version 1.5.3
# - Removed LightingInfoPanel completely
# - Added Base Images display to ControlPanel
# - Simplified UI for improved stability

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import traceback
import os
import glob
from PIL import Image, ImageTk

from utilities.logging_utils import get_logger
from utilities.constants import (
    SAVED_IMAGES_DIR, 
    BASE_IMAGES_DIR,
    CAMERA_MAPPINGS,
    get_base_image_path
)

class LogWindow(tk.Toplevel):
    """Enhanced logging window with filtering and search"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Configure window
        self.title("Owl Monitor Log")
        self.geometry("1000x600")
        self.resizable(True, True)
        
        # Create main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create filter frame
        self.create_filter_frame(main_frame)
        
        # Create log display
        self.create_log_display(main_frame)
        
        # Keep reference to parent
        self.parent = parent
        
        # Position window
        self.position_window()
        
        # Bind parent movement
        parent.bind("<Configure>", self.follow_main_window)
        
        # Initially hide the window - will be shown when View Logs is clicked
        self.withdraw()

    def create_filter_frame(self, parent):
        """Create log filtering controls"""
        filter_frame = ttk.LabelFrame(parent, text="Log Filters")
        filter_frame.pack(fill="x", pady=(0, 5))
        
        # Level filter
        level_frame = ttk.Frame(filter_frame)
        level_frame.pack(fill="x", pady=2)
        
        ttk.Label(level_frame, text="Log Level:").pack(side=tk.LEFT, padx=5)
        
        self.level_var = tk.StringVar(value="ALL")
        for level in ["ALL", "INFO", "WARNING", "ERROR"]:
            ttk.Radiobutton(
                level_frame,
                text=level,
                variable=self.level_var,
                value=level,
                command=self.apply_filters
            ).pack(side=tk.LEFT, padx=5)
        
        # Search
        search_frame = ttk.Frame(filter_frame)
        search_frame.pack(fill="x", pady=2)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.apply_filters())
        
        ttk.Entry(
            search_frame,
            textvariable=self.search_var
        ).pack(side=tk.LEFT, fill="x", expand=True, padx=5)

    def create_log_display(self, parent):
        """Create enhanced log display"""
        self.log_display = scrolledtext.ScrolledText(
            parent,
            width=100,
            height=30,
            wrap=tk.WORD,
            font=('Consolas', 10)  # Monospaced font for better readability
        )
        self.log_display.pack(fill="both", expand=True)
        
        # Configure tags for coloring with more visible colors
        self.log_display.tag_configure("ERROR", foreground="#FF0000")  # Bright red
        self.log_display.tag_configure("WARNING", foreground="#FF8C00")  # Dark orange
        self.log_display.tag_configure("INFO", foreground="#000080")  # Navy blue
        self.log_display.tag_configure("HIGHLIGHT", background="#FFFF00")  # Yellow highlight
        self.log_display.tag_configure("filtered", elide=True)  # For hiding filtered entries
        
        # Configure the base text color and background
        self.log_display.config(bg="#F8F8F8", fg="#000000")  # Light gray background, black text

    def apply_filters(self):
        """Apply all active filters to log display"""
        # Get current filters
        level = self.level_var.get()
        search = self.search_var.get().lower()
        
        # First, show all text
        self.log_display.tag_remove("filtered", "1.0", tk.END)
        
        # Filter by level - collect ranges to hide
        if level != "ALL":
            for tag in ["ERROR", "WARNING", "INFO"]:
                if tag != level:
                    index = "1.0"
                    while True:
                        tag_range = self.log_display.tag_nextrange(tag, index, tk.END)
                        if not tag_range:
                            break
                        # Mark these lines to be hidden
                        self.log_display.tag_add("filtered", tag_range[0], tag_range[1])
                        index = tag_range[1]
        
        # Apply search highlighting
        self.log_display.tag_remove("HIGHLIGHT", "1.0", tk.END)
        if search:
            start_pos = "1.0"
            while True:
                pos = self.log_display.search(search, start_pos, tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(search)}c"
                self.log_display.tag_add("HIGHLIGHT", pos, end_pos)
                start_pos = end_pos

    def log_message(self, message, level="INFO"):
        """Add enhanced log message"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] [{level}] {message}\n"
            
            self.log_display.insert(tk.END, formatted_message, level)
            self.log_display.see(tk.END)
            self.apply_filters()
                
        except Exception as e:
            print(f"Error logging to window: {e}")

    def position_window(self):
        """Position log window next to main window"""
        main_x = self.parent.winfo_x()
        main_y = self.parent.winfo_y()
        main_width = self.parent.winfo_width()
        self.geometry(f"+{main_x + main_width + 10}+{main_y}")
        
    def follow_main_window(self, event=None):
        """Reposition log window when main window moves"""
        if event.widget == self.parent:
            self.position_window()
            
    def on_closing(self):
        """Handle window closing"""
        self.withdraw()  # Hide instead of destroy
        
    def show(self):
        """Show the log window"""
        self.deiconify()
        self.position_window()
        self.lift()  # Bring to front

class BaseImageViewer(ttk.LabelFrame):
    """
    Component to display base images for all cameras.
    Added in v1.5.3 to provide basic visual feedback.
    """
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="Current Base Images")
        
        self.logger = logger or get_logger()
        self.image_references = {}  # Store references to prevent garbage collection
        
        # Create UI
        self.create_interface()
        
        # Load images initially
        self.load_base_images()
        
        # Set up periodic refresh
        self.start_refresh_timer()
    
    def create_interface(self):
        """Create the image display interface"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Container for images
        self.images_frame = ttk.Frame(main_frame)
        self.images_frame.pack(fill="both", expand=True)
        
        # Create image labels for each camera
        self.image_labels = {}
        
        # Get camera names and sort them
        camera_names = sorted(CAMERA_MAPPINGS.keys())
        
        # Create a frame for each camera with label and image
        for i, camera_name in enumerate(camera_names):
            camera_frame = ttk.LabelFrame(self.images_frame, text=camera_name)
            camera_frame.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            
            # Add label for lighting condition
            condition_var = tk.StringVar(value="Loading...")
            condition_label = ttk.Label(camera_frame, textvariable=condition_var)
            condition_label.pack(pady=(5, 0))
            
            # Add image label
            image_label = ttk.Label(camera_frame, text="Loading base image...")
            image_label.pack(padx=5, pady=5)
            
            # Store references
            self.image_labels[camera_name] = {
                "label": image_label,
                "condition_var": condition_var
            }
        
        # Configure grid to expand properly
        self.images_frame.columnconfigure(0, weight=1)
        self.images_frame.columnconfigure(1, weight=1)
        self.images_frame.columnconfigure(2, weight=1)
        self.images_frame.rowconfigure(0, weight=1)
        
        # Add refresh button at the bottom
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill="x", pady=5)
        
        ttk.Button(
            controls_frame,
            text="Refresh Images",
            command=self.load_base_images
        ).pack(side=tk.RIGHT, padx=5)
        
        # Add last update time label
        self.last_update_var = tk.StringVar(value="Last update: Never")
        ttk.Label(
            controls_frame,
            textvariable=self.last_update_var
        ).pack(side=tk.LEFT, padx=5)
    
    def load_base_images(self):
        """Load all base images for display"""
        try:
            # Update all three lighting conditions
            lighting_conditions = ["day", "night", "transition"]
            
            # Check which lighting condition has the most recent base images
            latest_condition = self.get_latest_base_image_condition()
            
            # Get camera names
            camera_names = CAMERA_MAPPINGS.keys()
            
            # Load base images for each camera using the most recent condition
            for camera_name in camera_names:
                try:
                    # Get the base image path
                    image_path = get_base_image_path(camera_name, latest_condition)
                    
                    # Check if file exists
                    if os.path.exists(image_path):
                        # Load and resize image
                        img = Image.open(image_path)
                        img.thumbnail((200, 150), Image.LANCZOS)
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # Update label
                        self.image_labels[camera_name]["label"].config(image=photo, text="")
                        
                        # Update condition label
                        self.image_labels[camera_name]["condition_var"].set(
                            f"Current: {latest_condition.capitalize()}"
                        )
                        
                        # Keep reference to prevent garbage collection
                        self.image_references[camera_name] = photo
                    else:
                        self.image_labels[camera_name]["label"].config(
                            text=f"No {latest_condition} base image found",
                            image=""
                        )
                        self.image_labels[camera_name]["condition_var"].set(
                            f"Missing: {latest_condition.capitalize()}"
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error loading base image for {camera_name}: {e}")
                    self.image_labels[camera_name]["label"].config(
                        text=f"Error loading image: {str(e)[:50]}",
                        image=""
                    )
            
            # Update last update time
            self.last_update_var.set(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"Error loading base images: {e}")
    
    def get_latest_base_image_condition(self):
        """
        Determine which lighting condition has the most recent base images.
        
        Returns:
            str: The lighting condition with the most recent base images
        """
        latest_time = 0
        latest_condition = "day"  # Default to day
        
        # Check all lighting conditions
        for condition in ["day", "night", "transition"]:
            # Check all cameras for this condition
            for camera_name in CAMERA_MAPPINGS.keys():
                image_path = get_base_image_path(camera_name, condition)
                if os.path.exists(image_path):
                    mod_time = os.path.getmtime(image_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_condition = condition
        
        return latest_condition
    
    def start_refresh_timer(self):
        """Start a timer to periodically refresh the base images"""
        # Refresh every 5 minutes
        self.after(300000, self.refresh_timer_callback)
    
    def refresh_timer_callback(self):
        """Callback for the refresh timer"""
        try:
            self.load_base_images()
        finally:
            # Schedule next refresh regardless of success/failure
            self.start_refresh_timer()
    
    def destroy(self):
        """Clean up resources"""
        # No special cleanup needed; clear image references for good practice
        self.image_references.clear()
        super().destroy()

class ControlPanel(ttk.Frame):
    """Panel for controlling the application with base image display"""
    def __init__(self, parent, local_saving_enabled, capture_interval, alert_delay,
                 email_alerts_enabled, update_system_func, start_script_func,
                 stop_script_func, toggle_local_saving_func, update_capture_interval_func,
                 update_alert_delay_func, toggle_email_alerts_func, log_window):
        super().__init__(parent)
        
        self.local_saving_enabled = local_saving_enabled
        self.capture_interval = capture_interval
        self.alert_delay = alert_delay
        self.email_alerts_enabled = email_alerts_enabled
        
        # Store callback functions
        self.update_system_func = update_system_func
        self.start_script_func = start_script_func
        self.stop_script_func = stop_script_func
        self.toggle_local_saving_func = toggle_local_saving_func
        self.update_capture_interval_func = update_capture_interval_func
        self.update_alert_delay_func = update_alert_delay_func
        self.toggle_email_alerts_func = toggle_email_alerts_func
        self.log_window = log_window
        
        # Create UI components
        self.create_control_interface()
        
    def create_control_interface(self):
        """Create control interface components"""
        # Create scrollable frame for all content
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Main controls frame - now inside scrollable_frame
        main_controls = ttk.LabelFrame(self.scrollable_frame, text="Motion Detection Controls")
        main_controls.pack(padx=5, pady=5, fill="x")
        
        # More compact button layout with multiple rows
        button_frame1 = ttk.Frame(main_controls)
        button_frame1.pack(pady=2, fill="x")
        
        self.start_button = ttk.Button(
            button_frame1,
            text="Start Detection",
            command=self.start_script_func,
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=2)
        
        self.stop_button = ttk.Button(
            button_frame1,
            text="Stop Detection",
            command=self.stop_script_func,
            state=tk.DISABLED,
            width=15
        )
        self.stop_button.pack(side=tk.LEFT, padx=2)
        
        button_frame2 = ttk.Frame(main_controls)
        button_frame2.pack(pady=2, fill="x")
        
        self.update_button = ttk.Button(
            button_frame2,
            text="Update System",
            command=self.update_system_func,
            width=15
        )
        self.update_button.pack(side=tk.LEFT, padx=2)
        
        self.cleanup_button = ttk.Button(
            button_frame2,
            text="Clear Saved Images",
            command=self.cleanup_saved_images,
            width=15
        )
        self.cleanup_button.pack(side=tk.LEFT, padx=2)
        
        # View logs button
        self.view_logs_button = ttk.Button(
            button_frame2,
            text="View Logs",
            command=self.show_logs,
            width=15
        )
        self.view_logs_button.pack(side=tk.LEFT, padx=2)
        
        # Combined Settings section (merged settings and alert settings)
        settings_frame = ttk.LabelFrame(self.scrollable_frame, text="Settings")
        settings_frame.pack(padx=5, pady=5, fill="x")
        
        # Create settings controls - more compact layout
        setting_controls = ttk.Frame(settings_frame)
        setting_controls.pack(pady=2, fill="x")
        
        # 2-column layout for more compact display
        # Local saving checkbox and Capture interval on first row
        row1 = ttk.Frame(setting_controls)
        row1.pack(fill="x", pady=1)
        
        # Left column
        col1 = ttk.Frame(row1)
        col1.pack(side=tk.LEFT, fill="x", expand=True)
        
        local_saving_cb = ttk.Checkbutton(
            col1,
            text="Enable Local Image Saving",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving_func
        )
        local_saving_cb.pack(side=tk.LEFT, padx=2, pady=1, anchor="w")
        
        # Right column
        col2 = ttk.Frame(row1)
        col2.pack(side=tk.RIGHT, fill="x", expand=True)
        
        interval_frame = ttk.Frame(col2)
        interval_frame.pack(side=tk.LEFT, fill="x", padx=2, pady=1)
        
        ttk.Label(interval_frame, text="Capture Interval (sec):").pack(side=tk.LEFT)
        
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            width=5,
            textvariable=self.capture_interval,
            command=self.update_capture_interval_func
        )
        interval_spinner.pack(side=tk.LEFT, padx=2)
        
        # Alert delay and Email alerts on second row
        row2 = ttk.Frame(setting_controls)
        row2.pack(fill="x", pady=1)
        
        # Left column
        col3 = ttk.Frame(row2)
        col3.pack(side=tk.LEFT, fill="x", expand=True)
        
        delay_frame = ttk.Frame(col3)
        delay_frame.pack(side=tk.LEFT, fill="x", padx=2, pady=1)
        
        ttk.Label(delay_frame, text="Alert Delay (min):").pack(side=tk.LEFT)
        
        delay_spinner = ttk.Spinbox(
            delay_frame,
            from_=5,
            to=120,
            width=5,
            textvariable=self.alert_delay,
            command=self.update_alert_delay_func
        )
        delay_spinner.pack(side=tk.LEFT, padx=2)
        
        # Right column
        col4 = ttk.Frame(row2)
        col4.pack(side=tk.RIGHT, fill="x", expand=True)
        
        email_cb = ttk.Checkbutton(
            col4,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_func
        )
        email_cb.pack(side=tk.LEFT, padx=2, pady=1, anchor="w")
        
        # Add base image viewer component
        self.base_image_viewer = BaseImageViewer(self.scrollable_frame)
        self.base_image_viewer.pack(padx=5, pady=10, fill="both", expand=True)
    
    def show_logs(self):
        """Show the log window"""
        if hasattr(self.log_window, 'show'):
            self.log_window.show()
    
    def update_run_state(self, is_running):
        """Update UI based on whether the script is running"""
        if is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            
    def cleanup_saved_images(self):
        """Delete all saved image files"""
        try:
            # Confirm with user
            if messagebox.askyesno("Confirm Delete",
                                  "Are you sure you want to delete all saved images?\nThis cannot be undone."):
                # Count files before deletion
                image_files = glob.glob(os.path.join(SAVED_IMAGES_DIR, "*.jpg"))
                file_count = len(image_files)
                
                # Delete all jpg files
                for file_path in image_files:
                    os.remove(file_path)
                
                # Log success
                self.log_window.log_message(f"Deleted {file_count} saved image files", "INFO")
                messagebox.showinfo("Success", f"Deleted {file_count} saved image files")
        except Exception as e:
            self.log_window.log_message(f"Error cleaning up images: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to delete images: {e}")


if __name__ == "__main__":
    # Test window
    root = tk.Tk()
    root.title("Front End Panels Test")
    
    # Create a simple log window for testing
    log = LogWindow(root)
    
    # Variables for testing
    local_saving = tk.BooleanVar(value=True)
    capture_interval = tk.IntVar(value=60)
    alert_delay = tk.IntVar(value=30)
    email_alerts = tk.BooleanVar(value=True)
    
    # Create test control panel
    def dummy_func(*args): pass
    
    panel = ControlPanel(
        root,
        local_saving,
        capture_interval,
        alert_delay,
        email_alerts,
        dummy_func,  # update_system
        dummy_func,  # start_script
        dummy_func,  # stop_script
        dummy_func,  # toggle_local_saving
        dummy_func,  # update_capture_interval
        dummy_func,  # update_alert_delay
        dummy_func,  # toggle_email_alerts
        log
    )
    panel.pack(fill="both", expand=True)
    
    root.geometry("800x600")
    root.mainloop()