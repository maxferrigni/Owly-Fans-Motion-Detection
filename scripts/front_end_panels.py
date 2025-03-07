# File: front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 7, 2025 Update - Version 1.4.2
# - Added error handling to all button event handlers
# - Improved lighting info panel display
# - Fixed subprocess termination issues
# - Enhanced UI responsiveness with better state management

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import os
import traceback
from PIL import Image, ImageTk
from utilities.logging_utils import get_logger
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition
from utilities.constants import get_base_image_path, IMAGE_COMPARISONS_DIR

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
    """Panel for controlling the application - Enhanced with error handling for v1.4.2"""
    def __init__(self, parent, local_saving_enabled, capture_interval, alert_delay,
                 email_alerts_enabled, update_system_func, start_script_func,
                 stop_script_func, toggle_local_saving_func, update_capture_interval_func,
                 update_alert_delay_func, toggle_email_alerts_func, log_window, 
                 clear_saved_images_func=None):
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
        self.clear_saved_images_func = clear_saved_images_func
        self.log_window = log_window
        
        # For logging
        self.logger = get_logger()
        
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
            command=self.start_script_handler
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Detection",
            command=self.stop_script_handler,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.update_button = ttk.Button(
            button_frame,
            text="Update System",
            command=self.update_system_handler
        )
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        # Maintenance button
        self.clear_images_button = ttk.Button(
            button_frame,
            text="Clear Saved Images",
            command=self.clear_saved_images_handler
        )
        self.clear_images_button.pack(side=tk.LEFT, padx=5)
        
        # View logs button
        self.view_logs_button = ttk.Button(
            button_frame,
            text="View Logs",
            command=self.show_logs_handler
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
            command=self.toggle_local_saving_handler
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
            command=self.update_capture_interval_handler
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
            command=self.update_alert_delay_handler
        )
        delay_spinner.pack(side=tk.LEFT, padx=5)
        
        # Email alerts checkbox (only remaining alert type)
        email_cb = ttk.Checkbutton(
            setting_controls,
            text="Enable Email Alerts",
            variable=self.email_alerts_enabled,
            command=self.toggle_email_alerts_handler
        )
        email_cb.grid(row=3, column=0, sticky="w", padx=5, pady=2)
    
    # Adding error handling to all button handlers
    def start_script_handler(self):
        """Start script with error handling"""
        try:
            self.logger.info("Start detection button clicked")
            self.start_script_func()
        except Exception as e:
            error_message = f"Error starting detection: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def stop_script_handler(self):
        """Stop script with error handling"""
        try:
            self.logger.info("Stop detection button clicked")
            self.stop_script_func()
        except Exception as e:
            error_message = f"Error stopping detection: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def update_system_handler(self):
        """Update system with error handling"""
        try:
            self.logger.info("Update system button clicked")
            self.update_system_func()
        except Exception as e:
            error_message = f"Error updating system: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)

    def clear_saved_images_handler(self):
        """Clear saved images with error handling"""
        try:
            self.logger.info("Clear saved images button clicked")
            if self.clear_saved_images_func:
                self.clear_saved_images_func()
            else:
                messagebox.showinfo("Not Available", "Clear saved images function is not available")
        except Exception as e:
            error_message = f"Error clearing saved images: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)

    def show_logs_handler(self):
        """Show logs with error handling"""
        try:
            self.logger.info("View logs button clicked")
            if hasattr(self.log_window, 'show'):
                self.log_window.show()
            else:
                messagebox.showinfo("Not Available", "Log window is not available")
        except Exception as e:
            error_message = f"Error showing logs: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def toggle_local_saving_handler(self):
        """Toggle local saving with error handling"""
        try:
            self.toggle_local_saving_func()
        except Exception as e:
            error_message = f"Error toggling local saving: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
            # Reset checkbox to previous state
            self.local_saving_enabled.set(not self.local_saving_enabled.get())
    
    def update_capture_interval_handler(self):
        """Update capture interval with error handling"""
        try:
            self.update_capture_interval_func()
        except Exception as e:
            error_message = f"Error updating capture interval: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def update_alert_delay_handler(self):
        """Update alert delay with error handling"""
        try:
            self.update_alert_delay_func()
        except Exception as e:
            error_message = f"Error updating alert delay: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
    
    def toggle_email_alerts_handler(self):
        """Toggle email alerts with error handling"""
        try:
            self.toggle_email_alerts_func()
        except Exception as e:
            error_message = f"Error toggling email alerts: {e}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", error_message)
            # Reset checkbox to previous state
            self.email_alerts_enabled.set(not self.email_alerts_enabled.get())
    
    def update_run_state(self, is_running):
        """Update UI based on whether the script is running"""
        try:
            if is_running:
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            else:
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
        except Exception as e:
            self.logger.error(f"Error updating run state: {e}")

class LightingInfoPanel(ttk.LabelFrame):
    """
    Panel showing lighting information, sunrise/sunset times, and countdown timers.
    Updated in v1.4.2 for more compact display and error handling.
    """
    def __init__(self, parent):
        super().__init__(parent, text="Lighting Information")
        
        # For logging
        self.logger = get_logger()
        
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
        
        # Create panel components with more compact layout
        self.create_compact_layout()
        
        # Start update thread
        self.update_thread = None
        self.running = True
        self.start_update_thread()
        
    def create_compact_layout(self):
        """Create a more compact layout for the lighting information panel"""
        try:
            # Main container with three columns
            main_frame = ttk.Frame(self)
            main_frame.pack(fill="x", padx=5, pady=3)
            
            # Column 1: Current condition and transition progress
            condition_frame = ttk.Frame(main_frame)
            condition_frame.grid(row=0, column=0, sticky="nw", padx=5)
            
            # Current lighting condition (row 1)
            ttk.Label(condition_frame, text="Current:").grid(row=0, column=0, sticky="w")
            self.condition_label = ttk.Label(
                condition_frame,
                textvariable=self.lighting_condition,
                style="Day.TLabel"  # Default style, will be updated
            )
            self.condition_label.grid(row=0, column=1, sticky="w", padx=5)
            
            # Detailed condition (dawn/dusk/etc)
            self.detailed_label = ttk.Label(
                condition_frame,
                textvariable=self.detailed_condition,
                style="DuskDawn.TLabel"
            )
            self.detailed_label.grid(row=0, column=2, sticky="w")
            
            # Transition progress (row 2) - only shown during transitions
            self.transition_frame = ttk.Frame(condition_frame)
            self.transition_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=2)
            
            self.progress_label = ttk.Label(
                self.transition_frame, 
                text="Progress:"
            )
            self.progress_label.pack(side=tk.LEFT)
            
            self.progress_bar = ttk.Progressbar(
                self.transition_frame,
                variable=self.transition_percentage,
                style="Transition.Horizontal.TProgressbar",
                length=100,
                mode='determinate'
            )
            self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True, padx=2)
            
            self.percentage_label = ttk.Label(
                self.transition_frame,
                text="0%"
            )
            self.percentage_label.pack(side=tk.LEFT)
            
            # Initially hide the transition progress
            self.transition_frame.grid_remove()
            
            # Column 2: Sun times
            times_frame = ttk.Frame(main_frame)
            times_frame.grid(row=0, column=1, sticky="nw", padx=10)
            
            # Row 1: Sunrise/Sunset
            ttk.Label(times_frame, text="Sunrise:").grid(row=0, column=0, sticky="w")
            ttk.Label(times_frame, textvariable=self.sunrise_time).grid(row=0, column=1, sticky="w", padx=2)
            
            ttk.Label(times_frame, text="Sunset:").grid(row=0, column=2, sticky="w", padx=(10,0))
            ttk.Label(times_frame, textvariable=self.sunset_time).grid(row=0, column=3, sticky="w", padx=2)
            
            # Row 2: True Day/Night
            ttk.Label(times_frame, text="True Day:").grid(row=1, column=0, sticky="w")
            ttk.Label(times_frame, textvariable=self.true_day_time).grid(row=1, column=1, sticky="w", padx=2)
            
            ttk.Label(times_frame, text="True Night:").grid(row=1, column=2, sticky="w", padx=(10,0))
            ttk.Label(times_frame, textvariable=self.true_night_time).grid(row=1, column=3, sticky="w", padx=2)
            
            # Column 3: Countdowns
            countdown_frame = ttk.Frame(main_frame)
            countdown_frame.grid(row=0, column=2, sticky="nw", padx=10)
            
            # Row 1: Until Sunrise/Sunset
            ttk.Label(countdown_frame, text="Until Sunrise:").grid(row=0, column=0, sticky="w")
            ttk.Label(
                countdown_frame, 
                textvariable=self.to_sunrise,
                style="CountdownTime.TLabel"
            ).grid(row=0, column=1, sticky="w", padx=2)
            
            ttk.Label(countdown_frame, text="Until Sunset:").grid(row=0, column=2, sticky="w", padx=(10,0))
            ttk.Label(
                countdown_frame, 
                textvariable=self.to_sunset,
                style="CountdownTime.TLabel"
            ).grid(row=0, column=3, sticky="w", padx=2)
            
            # Row 2: Until True Day/Night
            ttk.Label(countdown_frame, text="Until True Day:").grid(row=1, column=0, sticky="w")
            ttk.Label(
                countdown_frame, 
                textvariable=self.to_true_day,
                style="CountdownTime.TLabel"
            ).grid(row=1, column=1, sticky="w", padx=2)
            
            ttk.Label(countdown_frame, text="Until True Night:").grid(row=1, column=2, sticky="w", padx=(10,0))
            ttk.Label(
                countdown_frame, 
                textvariable=self.to_true_night,
                style="CountdownTime.TLabel"
            ).grid(row=1, column=3, sticky="w", padx=2)
            
            # Configure grid to distribute space
            for frame in [main_frame, condition_frame, times_frame, countdown_frame]:
                for i in range(4):
                    frame.columnconfigure(i, weight=1)
        except Exception as e:
            self.logger.error(f"Error creating lighting info layout: {e}")
            self.logger.error(traceback.format_exc())
    
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
            self.logger.error(f"Error updating lighting info: {e}")
            self.logger.error(traceback.format_exc())
            
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
                    self.logger.error(f"Error in update thread: {e}")
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

class BaseImagesPanel(ttk.LabelFrame):
    """Panel to display the three base images (day, night, transition)"""
    def __init__(self, parent, camera_configs):
        super().__init__(parent, text="Base Images")
        
        # For logging
        self.logger = get_logger()
        
        self.camera_configs = camera_configs
        self.image_labels = {}
        self.photo_refs = {}  # Keep references to avoid garbage collection
        self.camera_name = list(camera_configs.keys())[0] if camera_configs else "Wyze Internal Camera"
        
        # Create the display frame
        self.create_image_display()
        
        # Load initial images
        self.load_base_images()
        
        # Set up periodic refresh
        self.after(60000, self.refresh_images)  # Refresh every minute
    
    def create_image_display(self):
        """Create the image display layout"""
        try:
            self.images_frame = ttk.Frame(self)
            self.images_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Create three image containers for day, night, transition
            for i, condition in enumerate(["day", "night", "transition"]):
                frame = ttk.Frame(self.images_frame)
                frame.grid(row=0, column=i, padx=5, pady=5)
                
                # Add label for condition
                ttk.Label(
                    frame, 
                    text=condition.capitalize(),
                    font=("Arial", 10, "bold")
                ).pack(pady=(0, 5))
                
                # Add image placeholder
                label = ttk.Label(frame)
                label.pack()
                
                self.image_labels[condition] = label
            
            # Configure grid to distribute space evenly
            for i in range(3):
                self.images_frame.columnconfigure(i, weight=1)
        except Exception as e:
            self.logger.error(f"Error creating image display: {e}")
            self.logger.error(traceback.format_exc())
    
    def load_base_images(self):
        """Load and display base images for the selected camera"""
        try:
            # For each lighting condition, load the corresponding base image
            for condition in ["day", "night", "transition"]:
                image_path = get_base_image_path(self.camera_name, condition)
                
                if os.path.exists(image_path):
                    # Load and resize image
                    img = Image.open(image_path)
                    img = img.resize((200, 150), Image.LANCZOS)  # Resize to fit panel
                    photo = ImageTk.PhotoImage(img)
                    
                    # Store reference to prevent garbage collection
                    self.photo_refs[condition] = photo
                    
                    # Update label
                    self.image_labels[condition].config(image=photo)
                else:
                    # Display placeholder if image doesn't exist
                    self.image_labels[condition].config(text=f"No {condition} image")
                    # Remove any previous image
                    self.image_labels[condition].config(image="")
                    if condition in self.photo_refs:
                        del self.photo_refs[condition]
        except Exception as e:
            self.logger.error(f"Error loading base images: {e}")
            self.logger.error(traceback.format_exc())
    
    def set_camera(self, camera_name):
        """Change the displayed camera"""
        try:
            if camera_name in self.camera_configs:
                self.camera_name = camera_name
                self.load_base_images()
        except Exception as e:
            self.logger.error(f"Error setting camera: {e}")
            self.logger.error(traceback.format_exc())
    
    def refresh_images(self):
        """Refresh images periodically"""
        try:
            self.load_base_images()
            self.after(60000, self.refresh_images)  # Schedule next refresh
        except Exception as e:
            self.logger.error(f"Error refreshing images: {e}")
            self.logger.error(traceback.format_exc())

class AlertImagePanel(ttk.LabelFrame):
    """Panel to display the latest owl detection comparison image"""
    def __init__(self, parent, alert_manager):
        super().__init__(parent, text="Latest Owl Detection")
        
        # For logging
        self.logger = get_logger()
        
        self.alert_manager = alert_manager
        self.last_alert_id = None
        self.photo_ref = None  # Keep reference to prevent garbage collection
        
        # Create display components
        self.create_image_display()
        
        # Load initial image
        self.load_latest_alert_image()
        
        # Set up periodic refresh
        self.after(30000, self.refresh_image)  # Refresh every 30 seconds
    
    def create_image_display(self):
        """Create the image display layout"""
        try:
            self.frame = ttk.Frame(self)
            self.frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Add image placeholder
            self.image_label = ttk.Label(self.frame)
            self.image_label.pack(pady=5)
            
            # Add info label
            self.info_label = ttk.Label(
                self.frame,
                text="No recent alerts",
                font=("Arial", 10)
            )
            self.info_label.pack(pady=5)
        except Exception as e:
            self.logger.error(f"Error creating alert image display: {e}")
            self.logger.error(traceback.format_exc())
    
    def load_latest_alert_image(self):
        """Load and display the latest alert comparison image"""
        try:
            # Get comparison image paths for each alert type
            potential_images = [
                os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_box_comparison.jpg"),
                os.path.join(IMAGE_COMPARISONS_DIR, "owl_on_box_comparison.jpg"),
                os.path.join(IMAGE_COMPARISONS_DIR, "owl_in_area_comparison.jpg"),
                os.path.join(IMAGE_COMPARISONS_DIR, "two_owls_comparison.jpg"),
                os.path.join(IMAGE_COMPARISONS_DIR, "two_owls_in_box_comparison.jpg"),
                os.path.join(IMAGE_COMPARISONS_DIR, "eggs_or_babies_comparison.jpg")
            ]
            
            # Find the most recently modified image file
            latest_image = None
            latest_time = 0
            
            for img_path in potential_images:
                if os.path.exists(img_path):
                    mod_time = os.path.getmtime(img_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_image = img_path
            
            if latest_image and os.path.exists(latest_image):
                # Determine alert type from filename
                alert_type = "Unknown"
                if "owl_in_box" in latest_image:
                    alert_type = "Owl In Box"
                elif "owl_on_box" in latest_image:
                    alert_type = "Owl On Box"
                elif "owl_in_area" in latest_image:
                    alert_type = "Owl In Area"
                elif "two_owls_in_box" in latest_image:
                    alert_type = "Two Owls In Box"
                elif "two_owls" in latest_image:
                    alert_type = "Two Owls"
                elif "eggs_or_babies" in latest_image:
                    alert_type = "Eggs Or Babies"
                
                # Format timestamp
                timestamp = datetime.fromtimestamp(latest_time).strftime('%Y-%m-%d %H:%M:%S')
                
                # Load and resize image - use smaller size for panel display
                img = Image.open(latest_image)
                img = img.resize((300, 150), Image.LANCZOS)  # Resize to fit panel
                photo = ImageTk.PhotoImage(img)
                
                # Store reference to prevent garbage collection
                self.photo_ref = photo
                
                # Update label
                self.image_label.config(image=photo)
                
                # Update info text
                self.info_label.config(
                    text=f"Alert: {alert_type} | Time: {timestamp}"
                )
                
                # Store path to avoid reloading the same image
                self.last_alert_id = latest_image
            else:
                self.image_label.config(image="")
                self.info_label.config(text="No recent alerts")
                self.photo_ref = None
                
        except Exception as e:
            self.logger.error(f"Error loading alert image: {e}")
            self.logger.error(traceback.format_exc())
    
    def on_new_alert(self, alert_data):
        """Called when a new alert is generated to update the display"""
        try:
            self.last_alert_id = None  # Force refresh
            self.load_latest_alert_image()
        except Exception as e:
            self.logger.error(f"Error handling new alert: {e}")
            self.logger.error(traceback.format_exc())
    
    def refresh_image(self):
        """Refresh image periodically"""
        try:
            self.load_latest_alert_image()
            self.after(30000, self.refresh_image)  # Schedule next refresh
        except Exception as e:
            self.logger.error(f"Error refreshing alert image: {e}")
            self.logger.error(traceback.format_exc())