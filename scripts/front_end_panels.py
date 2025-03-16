# File: front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 16, 2025 Update - Version 1.3.2
# - Compacted Lighting Information panel for better space utilization
# - Added ImageViewerPanel for displaying comparison images
# - Added SysMonitorPanel as placeholder for future system monitoring

import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime, timedelta
import threading
import time
import os
from PIL import Image, ImageTk
from utilities.logging_utils import get_logger
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition
from utilities.constants import IMAGE_COMPARISONS_DIR, CAMERA_MAPPINGS, get_comparison_image_path

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

class ControlPanel(ttk.Frame):
    """Panel for controlling the application - Simplified for v1.3.0"""
    def __init__(self, parent, local_saving_enabled, capture_interval, alert_delay,
                 email_alerts_enabled, update_system_func, start_script_func,
                 stop_script_func, toggle_local_saving_func, update_capture_interval_func,
                 update_alert_delay_func, toggle_email_alerts_func, log_window,
                 clear_local_images_func):  # Added new parameter
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
        self.clear_local_images_func = clear_local_images_func  # Store the new callback
        
        # Create UI components
        self.create_control_interface()
        
    def create_control_interface(self):
        """Create simplified control interface components"""
        # Main controls frame
        main_controls = ttk.LabelFrame(self, text="Motion Detection Controls")
        main_controls.pack(padx=5, pady=5, fill="x")
        
        # Script control buttons
        button_frame = ttk.Frame(main_controls)
        button_frame.pack(pady=5, fill="x")
        
        self.start_button = ttk.Button(
            button_frame,
            text="Start Detection",
            command=self.start_script_func
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Detection",
            command=self.stop_script_func,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system_func
        )
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        # Update to use the dedicated callback function
        self.clear_images_button = ttk.Button(
            button_frame,
            text="Clear Images",
            command=self.clear_local_images_func
        )
        self.clear_images_button.pack(side=tk.LEFT, padx=5)
        
        # View logs button
        self.view_logs_button = ttk.Button(
            button_frame,
            text="View Logs",
            command=self.show_logs
        )
        self.view_logs_button.pack(side=tk.RIGHT, padx=5)
        
        # Combined Settings section (merged settings and alert settings)
        settings_frame = ttk.LabelFrame(self, text="Settings")
        settings_frame.pack(padx=5, pady=5, fill="x")
        
        # Create settings controls
        setting_controls = ttk.Frame(settings_frame)
        setting_controls.pack(pady=5, fill="x")
        
        # Local saving checkbox
        local_saving_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Local Image Saving",
            variable=self.local_saving_enabled,
            command=self.toggle_local_saving_func
        )
        local_saving_cb.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        # Capture interval
        interval_frame = ttk.Frame(setting_controls)
        interval_frame.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
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
        delay_frame = ttk.Frame(setting_controls)
        delay_frame.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        
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
        
        # Email alerts checkbox (only remaining alert type)
        email_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_func
        )
        email_cb.grid(row=3, column=0, sticky="w", padx=5, pady=2)
    
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

class LightingInfoPanel(ttk.LabelFrame):
    """
    Panel showing lighting information, sunrise/sunset times, and countdown timers.
    Made more compact in v1.3.2 for better space utilization.
    """
    def __init__(self, parent):
        super().__init__(parent, text="Lighting Information")
        
        # Create custom progress bar style
        self.style = ttk.Style()
        self.style.configure(
            "Transition.Horizontal.TProgressbar", 
            troughcolor="#E0E0E0", 
            background="#FFA500"  # Orange for transition progress
        )
        
        # Create styles for different lighting conditions
        self.style.configure('Day.TLabel', foreground='blue', font=('Arial', 9, 'bold'))
        self.style.configure('Night.TLabel', foreground='purple', font=('Arial', 9, 'bold'))
        self.style.configure('Transition.TLabel', foreground='orange', font=('Arial', 9, 'bold'))
        self.style.configure('DuskDawn.TLabel', foreground='#FF6600', font=('Arial', 8))
        self.style.configure('CountdownTime.TLabel', foreground='green', font=('Arial', 9, 'bold'))
        self.style.configure('InfoLabel.TLabel', font=('Arial', 8))
        
        # Initialize variables
        self.lighting_condition = tk.StringVar(value="Unknown")
        self.detailed_condition = tk.StringVar(value="Unknown")
        self.sunrise_time = tk.StringVar(value="--:--")
        self.sunset_time = tk.StringVar(value="--:--")
        self.true_day_time = tk.StringVar(value="--:--")
        self.true_night_time = tk.StringVar(value="--:--")
        self.to_sunrise = tk.StringVar(value="--:--")
        self.to_sunset = tk.StringVar(value="--:--")
        self.to_true_day = tk.StringVar(value="--:--")
        self.to_true_night = tk.StringVar(value="--:--")
        self.transition_percentage = tk.DoubleVar(value=0)
        self.is_transition = False
        
        # Create compact layout
        self.create_compact_layout()
        
        # Start update thread
        self.update_thread = None
        self.running = True
        self.start_update_thread()
        
    def create_compact_layout(self):
        """Create more compact layout for lighting information"""
        # Main grid with 3 columns
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="x", padx=3, pady=3)
        
        # Current condition (Row 0)
        ttk.Label(main_frame, text="Current:").grid(row=0, column=0, sticky="w", padx=2)
        self.condition_label = ttk.Label(
            main_frame,
            textvariable=self.lighting_condition,
            style="Day.TLabel"
        )
        self.condition_label.grid(row=0, column=1, sticky="w", padx=2)
        self.detailed_label = ttk.Label(
            main_frame,
            textvariable=self.detailed_condition,
            style="DuskDawn.TLabel"
        )
        self.detailed_label.grid(row=0, column=2, sticky="w", padx=2)
        
        # Sun times with countdowns (Row 1-2) - More compact grid layout
        times_frame = ttk.Frame(main_frame)
        times_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=1)
        
        # Grid layout for times
        # Column 0-1: Sunrise info, Column 2-3: Sunset info
        # Column 4-5: True Day info, Column 6-7: True Night info
        
        # Labels - Row 0
        ttk.Label(times_frame, text="Sunrise:", style="InfoLabel.TLabel").grid(row=0, column=0, sticky="w", padx=2)
        ttk.Label(times_frame, text="Sunset:", style="InfoLabel.TLabel").grid(row=0, column=2, sticky="w", padx=2)
        ttk.Label(times_frame, text="True Day:", style="InfoLabel.TLabel").grid(row=0, column=4, sticky="w", padx=2)
        ttk.Label(times_frame, text="True Night:", style="InfoLabel.TLabel").grid(row=0, column=6, sticky="w", padx=2)
        
        # Time values - Row 0
        ttk.Label(times_frame, textvariable=self.sunrise_time, style="InfoLabel.TLabel").grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.sunset_time, style="InfoLabel.TLabel").grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.true_day_time, style="InfoLabel.TLabel").grid(row=0, column=5, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.true_night_time, style="InfoLabel.TLabel").grid(row=0, column=7, sticky="w", padx=2)
        
        # Countdown labels - Row 1
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=0, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_sunrise, style="CountdownTime.TLabel").grid(row=1, column=1, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=2, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_sunset, style="CountdownTime.TLabel").grid(row=1, column=3, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=4, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_true_day, style="CountdownTime.TLabel").grid(row=1, column=5, sticky="w", padx=2)
        
        ttk.Label(times_frame, text="Until:", style="InfoLabel.TLabel").grid(row=1, column=6, sticky="w", padx=2)
        ttk.Label(times_frame, textvariable=self.to_true_night, style="CountdownTime.TLabel").grid(row=1, column=7, sticky="w", padx=2)
        
        # Configure columns to expand proportionally
        for i in range(8):
            times_frame.columnconfigure(i, weight=1)
        
        # Transition progress (hidden initially)
        self.transition_frame = ttk.Frame(main_frame)
        self.transition_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=1)
        
        self.progress_label = ttk.Label(
            self.transition_frame, 
            text="Transition:",
            style="InfoLabel.TLabel"
        )
        self.progress_label.pack(side=tk.LEFT, padx=2)
        
        self.progress_bar = ttk.Progressbar(
            self.transition_frame,
            variable=self.transition_percentage,
            style="Transition.Horizontal.TProgressbar",
            length=150,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True, padx=2)
        
        self.percentage_label = ttk.Label(
            self.transition_frame,
            text="0%",
            style="InfoLabel.TLabel"
        )
        self.percentage_label.pack(side=tk.LEFT, padx=2)
        
        # Initially hide the transition progress
        self.transition_frame.grid_remove()
        
        # Configure grid
        main_frame.columnconfigure(2, weight=1)
        
    def update_lighting_info(self):
        """Update all lighting information"""
        try:
            # Get current lighting information
            lighting_info = get_lighting_info()
            
            # Update condition variables
            condition = lighting_info.get('condition', 'unknown')
            detailed = lighting_info.get('detailed_condition', 'unknown')
            
            self.lighting_condition.set(condition.upper())
            
            # Update condition label style
            if condition == 'day':
                self.condition_label.configure(style='Day.TLabel')
            elif condition == 'night':
                self.condition_label.configure(style='Night.TLabel')
            else:
                self.condition_label.configure(style='Transition.TLabel')
            
            # Update detailed condition if in transition
            if condition == 'transition':
                self.detailed_condition.set(f"({detailed.upper()})")
                self.detailed_label.grid()
            else:
                self.detailed_condition.set("")
                
            # Update times
            if lighting_info.get('next_sunrise'):
                self.sunrise_time.set(lighting_info.get('next_sunrise'))
            if lighting_info.get('next_sunset'):
                self.sunset_time.set(lighting_info.get('next_sunset'))
            if lighting_info.get('next_true_day'):
                self.true_day_time.set(lighting_info.get('next_true_day'))
            if lighting_info.get('next_true_night'):
                self.true_night_time.set(lighting_info.get('next_true_night'))
                
            # Update countdowns
            countdown = lighting_info.get('countdown', {})
            
            if countdown.get('to_sunrise') is not None:
                self.to_sunrise.set(format_time_until(countdown.get('to_sunrise')))
            if countdown.get('to_sunset') is not None:
                self.to_sunset.set(format_time_until(countdown.get('to_sunset')))
            if countdown.get('to_true_day') is not None:
                self.to_true_day.set(format_time_until(countdown.get('to_true_day')))
            if countdown.get('to_true_night') is not None:
                self.to_true_night.set(format_time_until(countdown.get('to_true_night')))
                
            # Update transition progress
            is_transition = lighting_info.get('is_transition', False)
            if is_transition:
                progress = lighting_info.get('transition_percentage', 0)
                self.transition_percentage.set(progress)
                self.percentage_label.config(text=f"{progress:.1f}%")
                
                # Show transition progress
                if not self.is_transition:
                    self.transition_frame.grid()
                    self.is_transition = True
            else:
                # Hide transition progress
                if self.is_transition:
                    self.transition_frame.grid_remove()
                    self.is_transition = False
                    
        except Exception as e:
            print(f"Error updating lighting info: {e}")
            
    def start_update_thread(self):
        """Start the background thread to update lighting information"""
        def update_loop():
            while self.running:
                try:
                    # Update lighting info
                    self.update_lighting_info()
                    
                    # Sleep for 5 seconds
                    for _ in range(50):  # 5 seconds in 100ms increments
                        if not self.running:
                            break
                        time.sleep(0.1)
                        
                except Exception as e:
                    print(f"Error in update thread: {e}")
                    time.sleep(5)  # Wait 5 seconds on error
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
        
    def stop_update_thread(self):
        """Stop the update thread when panel is destroyed"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
            
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        self.stop_update_thread()
        super().destroy()

class ImageViewerPanel(ttk.Frame):
    """
    Simple panel for displaying camera comparison images.
    Added in v1.3.2.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.logger = get_logger()
        
        # Store image references to prevent garbage collection
        self.image_refs = {
            "Wyze Internal Camera": None,
            "Bindy Patio Camera": None,
            "Upper Patio Camera": None
        }
        
        # Last modification times to detect changes
        self.last_modified = {
            "Wyze Internal Camera": 0,
            "Bindy Patio Camera": 0,
            "Upper Patio Camera": 0
        }
        
        # Create UI components
        self.create_layout()
        
        # Start refresh timer
        self.refresh_images()
        
    def create_layout(self):
        """Create simple layout with three image displays in vertical column"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create scrollable canvas for images
        self.canvas_frame = ttk.Frame(main_frame)
        self.canvas_frame.pack(fill="both", expand=True)
        
        # Create image frames - one for each camera (vertically stacked)
        self.camera_frames = {}
        self.image_labels = {}
        self.status_labels = {}
        
        # Set camera order: Wyze (top), Bindy (middle), Upper (bottom)
        camera_order = ["Wyze Internal Camera", "Bindy Patio Camera", "Upper Patio Camera"]
        
        for i, camera in enumerate(camera_order):
            # Create frame for this camera
            camera_frame = ttk.LabelFrame(self.canvas_frame, text=camera)
            camera_frame.pack(fill="x", pady=5)
            self.camera_frames[camera] = camera_frame
            
            # Add image label
            image_label = ttk.Label(camera_frame)
            image_label.pack(pady=2)
            self.image_labels[camera] = image_label
            
            # Add status label
            status_label = ttk.Label(
                camera_frame, 
                text="No image available", 
                font=("Arial", 8, "italic")
            )
            status_label.pack(pady=2)
            self.status_labels[camera] = status_label
    
    def load_image(self, camera):
        """
        Load comparison image for a specific camera.
        Returns True if image was updated.
        """
        try:
            # Get image path based on camera type
            image_path = get_comparison_image_path(camera)
            
            # Check if file exists
            if not os.path.exists(image_path):
                self.status_labels[camera].config(
                    text="No comparison image available"
                )
                return False
            
            # Check if file was modified since last load
            mod_time = os.path.getmtime(image_path)
            if mod_time <= self.last_modified[camera]:
                return False  # No update needed
            
            # Load and resize image
            image = Image.open(image_path)
            
            # Calculate new size to fit in frame
            # Target width around 850px (to fit in 900px window with margins)
            # Maintain aspect ratio
            width, height = image.size
            target_width = 850
            ratio = target_width / width
            new_size = (target_width, int(height * ratio))
            
            # Resize image
            resized = image.resize(new_size, Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(resized)
            
            # Update image label
            self.image_labels[camera].config(image=photo)
            
            # Store reference to prevent garbage collection
            self.image_refs[camera] = photo
            
            # Update last modified time
            self.last_modified[camera] = mod_time
            
            # Update status label with timestamp
            timestamp = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
            self.status_labels[camera].config(
                text=f"Last updated: {timestamp}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading image for {camera}: {e}")
            self.status_labels[camera].config(
                text=f"Error loading image: {str(e)[:50]}..."
            )
            return False
    
    def refresh_images(self):
        """Refresh all camera images"""
        try:
            # Load images for all cameras
            updates = 0
            for camera in self.image_labels.keys():
                if self.load_image(camera):
                    updates += 1
                    
            # Schedule next refresh
            # Every 5 seconds if no updates, more frequently if updates found
            refresh_time = 1000 if updates > 0 else 5000
            self.after(refresh_time, self.refresh_images)
            
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
            # On error, retry after longer delay
            self.after(10000, self.refresh_images)

class SysMonitorPanel(ttk.Frame):
    """
    Placeholder panel for system monitoring.
    Added in v1.3.2.
    """
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create simple placeholder content
        self.create_placeholder()
        
    def create_placeholder(self):
        """Create placeholder content"""
        # Center content
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add placeholder text
        placeholder_label = ttk.Label(
            main_frame,
            text="System Monitoring Coming Soon",
            font=("Arial", 14, "bold")
        )
        placeholder_label.pack(pady=20)
        
        details_label = ttk.Label(
            main_frame,
            text="This tab will contain system monitoring features in a future update.",
            wraplength=600
        )
        details_label.pack(pady=10)
        
        # Add some placeholder stats
        stats_frame = ttk.LabelFrame(main_frame, text="Future Monitoring Features")
        stats_frame.pack(fill="x", pady=20, padx=10)
        
        features = [
            "Camera Feed Status",
            "System Resource Usage",
            "Network Connectivity",
            "Storage Space",
            "Alert History"
        ]
        
        for feature in features:
            ttk.Label(stats_frame, text=f"• {feature}").pack(anchor="w", padx=10, pady=2)