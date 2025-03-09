# File: _front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 8, 2025 Update - Version 1.5.4
# - Fixed redundant base image display
# - Improved base image display timing with detection state
# - Enhanced LogWindow functionality
# - Improved control panel design

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

class BaseImagesPanel(ttk.LabelFrame):
    """
    Improved panel to display base images for all cameras.
    In v1.5.4: Only shows images after detection starts.
    """
    def __init__(self, parent, logger=None):
        super().__init__(parent, text="Camera Base Images")
        
        self.logger = logger or get_logger()
        self.image_references = {}  # Store references to prevent garbage collection
        self.detection_active = False  # Track if detection is running
        
        # Create UI
        self.create_interface()
        
    def create_interface(self):
        """Create the improved image display interface"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Add status indicator
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.pack(fill="x", pady=(0, 5))
        
        self.status_var = tk.StringVar(value="Waiting for detection to start...")
        self.status_label = ttk.Label(
            self.status_frame, 
            textvariable=self.status_var,
            font=("Arial", 10, "italic"),
            foreground="gray"
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Add refresh button
        self.refresh_button = ttk.Button(
            self.status_frame,
            text="Refresh Images",
            command=self.refresh_images,
            state=tk.DISABLED  # Disabled until detection starts
        )
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
        
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
            
            # Add placeholder for when no images available
            placeholder_frame = ttk.Frame(camera_frame, width=200, height=150)
            placeholder_frame.pack(padx=5, pady=5)
            placeholder_frame.pack_propagate(False)  # Maintain size even when empty
            
            # Add placeholder text
            placeholder_label = ttk.Label(
                placeholder_frame,
                text="Base image will appear\nafter detection starts",
                justify="center"
            )
            placeholder_label.place(relx=0.5, rely=0.5, anchor="center")
            
            # Store reference to placeholder
            self.image_labels[camera_name] = {
                "frame": placeholder_frame,
                "placeholder": placeholder_label,
                "image_label": None  # Will be created when needed
            }
        
        # Configure grid to expand properly
        self.images_frame.columnconfigure(0, weight=1)
        self.images_frame.columnconfigure(1, weight=1)
        self.images_frame.columnconfigure(2, weight=1)
        self.images_frame.rowconfigure(0, weight=1)
        
        # Add last update time label
        self.last_update_var = tk.StringVar(value="Detection not active")
        last_update_label = ttk.Label(
            main_frame,
            textvariable=self.last_update_var,
            font=("Arial", 8),
            foreground="gray"
        )
        last_update_label.pack(side=tk.LEFT, padx=5, pady=(5, 0))
        
    def detection_started(self):
        """Called when detection script starts"""
        self.detection_active = True
        self.status_var.set("Loading base images...")
        self.refresh_button.config(state=tk.NORMAL)
        
        # Schedule image loading after a short delay
        self.after(2000, self.load_base_images)
        
    def detection_stopped(self):
        """Called when detection script stops"""
        self.detection_active = False
        self.status_var.set("Waiting for detection to start...")
        self.refresh_button.config(state=tk.DISABLED)
        self.last_update_var.set("Detection not active")
        
        # Clear all images and show placeholders
        self.clear_images()
        
    def clear_images(self):
        """Clear all images and show placeholders"""
        for camera_name, components in self.image_labels.items():
            # Remove image label if it exists
            if components["image_label"] is not None:
                components["image_label"].destroy()
                components["image_label"] = None
            
            # Show placeholder
            components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
            
        # Clear image references to release memory
        self.image_references.clear()
    
    def load_base_images(self):
        """Load all base images for display"""
        if not self.detection_active:
            return
            
        try:
            # Update all three lighting conditions
            lighting_conditions = ["day", "night", "transition"]
            found_images = False
            
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
                        found_images = True
                        # Load and resize image
                        img = Image.open(image_path)
                        img.thumbnail((200, 150), Image.LANCZOS)
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # Get component references
                        components = self.image_labels[camera_name]
                        
                        # Hide placeholder
                        components["placeholder"].place_forget()
                        
                        # Create or update image label
                        if components["image_label"] is None:
                            components["image_label"] = ttk.Label(components["frame"])
                            components["image_label"].pack(fill="both", expand=True)
                        
                        # Update image
                        components["image_label"].config(image=photo)
                        
                        # Keep reference to prevent garbage collection
                        self.image_references[camera_name] = photo
                    else:
                        self.logger.debug(f"No {latest_condition} base image found for {camera_name}")
                        
                        # Show placeholder with message
                        components = self.image_labels[camera_name]
                        if components["image_label"] is not None:
                            components["image_label"].destroy()
                            components["image_label"] = None
                            
                        components["placeholder"].config(
                            text=f"No {latest_condition} base image found"
                        )
                        components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
                        
                except Exception as e:
                    self.logger.error(f"Error loading base image for {camera_name}: {e}")
                    
                    # Show placeholder with error message
                    components = self.image_labels[camera_name]
                    if components["image_label"] is not None:
                        components["image_label"].destroy()
                        components["image_label"] = None
                        
                    components["placeholder"].config(
                        text=f"Error loading image:\n{str(e)[:50]}..."
                    )
                    components["placeholder"].place(relx=0.5, rely=0.5, anchor="center")
            
            # Update last update time and status
            if found_images:
                self.last_update_var.set(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
                self.status_var.set(f"Showing {latest_condition} base images")
            else:
                self.last_update_var.set("No base images found")
                self.status_var.set("Waiting for base images to be captured...")
                
                # Schedule another attempt in 5 seconds
                self.after(5000, self.load_base_images)
            
        except Exception as e:
            self.logger.error(f"Error loading base images: {e}")
            self.status_var.set(f"Error: {str(e)[:50]}...")
    
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
    
    def refresh_images(self):
        """Manual refresh of base images"""
        if self.detection_active:
            self.status_var.set("Refreshing base images...")
            self.load_base_images()
    
    def destroy(self):
        """Clean up resources"""
        # No special cleanup needed; clear image references for good practice
        self.image_references.clear()
        super().destroy()

class ControlPanel(ttk.Frame):
    """Panel for controlling the application with improved base image display"""
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
        
        # Base images panel reference - initialize after detection starts
        self.base_images_panel = None
        
    def create_control_interface(self):
        """Create control interface components - Simplified for v1.5.4"""
        # Main controls frame
        controls_frame = ttk.LabelFrame(self, text="Motion Detection Controls")
        controls_frame.pack(fill="x", padx=5, pady=5)
        
        # Button grid layout for controls
        button_grid = ttk.Frame(controls_frame)
        button_grid.pack(fill="x", padx=5, pady=5)
        
        # First row of buttons
        row1 = ttk.Frame(button_grid)
        row1.pack(fill="x", pady=2)
        
        self.start_button = ttk.Button(
            row1,
            text="Start Detection",
            command=self.start_script_func,
            width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=2)
        
        self.stop_button = ttk.Button(
            row1,
            text="Stop Detection",
            command=self.stop_script_func,
            state=tk.DISABLED,
            width=15
        )
        self.stop_button.pack(side=tk.LEFT, padx=2)
        
        # Add spacer between button groups
        ttk.Label(row1, text="").pack(side=tk.LEFT, padx=10)
        
        self.view_logs_button = ttk.Button(
            row1,
            text="View Logs",
            command=self.show_logs,
            width=15
        )
        self.view_logs_button.pack(side=tk.LEFT, padx=2)
        
        # Second row of buttons
        row2 = ttk.Frame(button_grid)
        row2.pack(fill="x", pady=2)
        
        self.update_button = ttk.Button(
            row2,
            text="Update System",
            command=self.update_system_func,
            width=15
        )
        self.update_button.pack(side=tk.LEFT, padx=2)
        
        self.cleanup_button = ttk.Button(
            row2,
            text="Clear Saved Images",
            command=self.cleanup_saved_images,
            width=15
        )
        self.cleanup_button.pack(side=tk.LEFT, padx=2)
        
        # Settings section - simplified for v1.5.4
        settings_frame = ttk.LabelFrame(self, text="Settings")
        settings_frame.pack(fill="x", padx=5, pady=5)
        
        # Create settings in two rows
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill="x", pady=5)
        
        # Local saving and Email alerts (checkboxes)
        local_saving_cb = ttk.Checkbutton(
            row1,
            text="Enable Local Image Saving",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving_func
        )
        local_saving_cb.pack(side=tk.LEFT, padx=10)
        
        email_cb = ttk.Checkbutton(
            row1,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_func
        )
        email_cb.pack(side=tk.LEFT, padx=10)
        
        # Capture interval and Alert delay (spinners)
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill="x", pady=5)
        
        # Capture interval
        interval_frame = ttk.Frame(row2)
        interval_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(interval_frame, text="Capture Interval (sec):").pack(side=tk.LEFT)
        interval_spinner = ttk.Spinbox(
            interval_frame,
            from_=10,
            to=300,
            width=5,
            textvariable=self.capture_interval,
            command=self.update_capture_interval_func
        )
        interval_spinner.pack(side=tk.LEFT, padx=5)
        
        # Alert delay
        delay_frame = ttk.Frame(row2)
        delay_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(delay_frame, text="Alert Delay (min):").pack(side=tk.LEFT)
        delay_spinner = ttk.Spinbox(
            delay_frame,
            from_=5,
            to=120,
            width=5,
            textvariable=self.alert_delay,
            command=self.update_alert_delay_func
        )
        delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Create container for base images panel - will be populated when detection starts
        self.images_container = ttk.Frame(self)
        self.images_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initialize empty base images panel
        self.base_images_panel = BaseImagesPanel(self.images_container, logger=get_logger())
        self.base_images_panel.pack(fill="both", expand=True)
    
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
    
    def notify_detection_started(self):
        """Notify base images panel that detection has started"""
        if self.base_images_panel:
            self.base_images_panel.detection_started()
            
    def notify_detection_stopped(self):
        """Notify base images panel that detection has stopped"""
        if self.base_images_panel:
            self.base_images_panel.detection_stopped()
            
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
    
    # Add test buttons for simulating detection state changes
    test_frame = ttk.Frame(root)
    test_frame.pack(pady=10)
    
    ttk.Button(
        test_frame,
        text="Simulate Detection Start",
        command=lambda: panel.notify_detection_started()
    ).pack(side=tk.LEFT, padx=5)
    
    ttk.Button(
        test_frame,
        text="Simulate Detection Stop",
        command=lambda: panel.notify_detection_stopped()
    ).pack(side=tk.LEFT, padx=5)
    
    root.geometry("800x600")
    root.mainloop()