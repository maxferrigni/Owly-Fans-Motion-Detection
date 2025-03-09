# File: _front_end_panels.py
# Purpose: Reusable GUI components for the Owl Monitoring System
#
# March 8, 2025 Update - Version 1.5.2
# - Fixed LightingInfoPanel blank fields issue with robust fallbacks
# - Added Local Image Cleanup button to ControlPanel
# - Enhanced error handling in LightingInfoPanel
# - Improved UI layout to be more condensed and fit better in window
# - Added scrollbars to panels that might overflow

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from datetime import datetime, timedelta
import threading
import time
import traceback
import os
import glob
from utilities.logging_utils import get_logger
from utilities.time_utils import get_lighting_info, format_time_until, get_current_lighting_condition
from utilities.constants import SAVED_IMAGES_DIR

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
        """Create simplified control interface components"""
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

class LightingInfoPanel(ttk.LabelFrame):
    """
    Panel showing lighting information, sunrise/sunset times, and countdown timers.
    Redesigned in v1.5.2 with more compact layout and robust data handling.
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
        self.logger = get_logger()
        
        # Initialize state for update thread
        self.update_thread = None
        self.running = False

        try:
            # Create panel components with more compact layout
            self.create_compact_layout()
            
            # Start update thread
            self.start_update_thread()
            
            self.logger.info("Lighting information panel initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing lighting panel: {e}")
            traceback.print_exc()
            # Create error display instead
            self.create_error_display(str(e))
        
    def create_error_display(self, error_message):
        """Create simplified error display if initialization fails"""
        # Clear any existing widgets
        for widget in self.winfo_children():
            widget.destroy()
            
        # Create simple error message
        error_label = ttk.Label(
            self,
            text=f"Error initializing lighting panel: {error_message}",
            foreground="red",
            wraplength=600
        )
        error_label.pack(padx=10, pady=10)
        
    def create_compact_layout(self):
        """Create more compact layout for lighting information"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=2)
        
        # Top row - Current condition and transition progress combined
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=1)
        
        # Current lighting condition
        condition_frame = ttk.Frame(top_frame)
        condition_frame.pack(side=tk.LEFT, fill="x", padx=2)
        
        ttk.Label(condition_frame, text="Current Condition:").pack(side=tk.LEFT)
        self.condition_label = ttk.Label(
            condition_frame,
            textvariable=self.lighting_condition,
            style="Day.TLabel",
            width=10
        )
        self.condition_label.pack(side=tk.LEFT, padx=2)
        
        self.detailed_label = ttk.Label(
            condition_frame,
            textvariable=self.detailed_condition,
            style="DuskDawn.TLabel"
        )
        self.detailed_label.pack(side=tk.LEFT, padx=2)
        
        # Create progress bar that only shows during transitions
        self.transition_frame = ttk.Frame(top_frame)
        self.transition_frame.pack(side=tk.RIGHT, fill="x", expand=True, padx=2)
        self.progress_bar = ttk.Progressbar(
            self.transition_frame,
            variable=self.transition_percentage,
            style="Transition.Horizontal.TProgressbar",
            length=100,
            mode='determinate'
        )
        self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True)
        self.percentage_label = ttk.Label(self.transition_frame, text="0%", width=5)
        self.percentage_label.pack(side=tk.LEFT)
        
        # Initially hide the transition progress
        self.transition_frame.pack_forget()
        
        # Middle frame - sunrise/sunset times in two rows of two columns each
        times_frame = ttk.Frame(main_frame)
        times_frame.pack(fill="x", pady=1)
        
        # Left column - Sunrise and True Day
        left_times = ttk.Frame(times_frame)
        left_times.pack(side=tk.LEFT, fill="x", expand=True)
        
        # Sunrise row
        sunrise_frame = ttk.Frame(left_times)
        sunrise_frame.pack(fill="x", pady=1)
        ttk.Label(sunrise_frame, text="Sunrise:", width=10).pack(side=tk.LEFT)
        ttk.Label(sunrise_frame, textvariable=self.sunrise_time, width=8).pack(side=tk.LEFT)
        
        # True Day row
        true_day_frame = ttk.Frame(left_times)
        true_day_frame.pack(fill="x", pady=1)
        ttk.Label(true_day_frame, text="True Day:", width=10).pack(side=tk.LEFT)
        ttk.Label(true_day_frame, textvariable=self.true_day_time, width=8).pack(side=tk.LEFT)
        
        # Right column - Sunset and True Night
        right_times = ttk.Frame(times_frame)
        right_times.pack(side=tk.RIGHT, fill="x", expand=True)
        
        # Sunset row
        sunset_frame = ttk.Frame(right_times)
        sunset_frame.pack(fill="x", pady=1)
        ttk.Label(sunset_frame, text="Sunset:", width=10).pack(side=tk.LEFT)
        ttk.Label(sunset_frame, textvariable=self.sunset_time, width=8).pack(side=tk.LEFT)
        
        # True Night row
        true_night_frame = ttk.Frame(right_times)
        true_night_frame.pack(fill="x", pady=1)
        ttk.Label(true_night_frame, text="True Night:", width=10).pack(side=tk.LEFT)
        ttk.Label(true_night_frame, textvariable=self.true_night_time, width=8).pack(side=tk.LEFT)
        
        # Bottom frame - countdowns in two rows of two columns each
        countdown_frame = ttk.Frame(main_frame)
        countdown_frame.pack(fill="x", pady=1)
        
        # Left column - Until Sunrise and Until True Day
        left_countdown = ttk.Frame(countdown_frame)
        left_countdown.pack(side=tk.LEFT, fill="x", expand=True)
        
        # Until Sunrise row
        until_sunrise_frame = ttk.Frame(left_countdown)
        until_sunrise_frame.pack(fill="x", pady=1)
        ttk.Label(until_sunrise_frame, text="Until Sunrise:", width=12).pack(side=tk.LEFT)
        ttk.Label(until_sunrise_frame, textvariable=self.to_sunrise, style="CountdownTime.TLabel").pack(side=tk.LEFT)
        
        # Until True Day row
        until_true_day_frame = ttk.Frame(left_countdown)
        until_true_day_frame.pack(fill="x", pady=1)
        ttk.Label(until_true_day_frame, text="Until True Day:", width=12).pack(side=tk.LEFT)
        ttk.Label(until_true_day_frame, textvariable=self.to_true_day, style="CountdownTime.TLabel").pack(side=tk.LEFT)
        
        # Right column - Until Sunset and Until True Night
        right_countdown = ttk.Frame(countdown_frame)
        right_countdown.pack(side=tk.RIGHT, fill="x", expand=True)
        
        # Until Sunset row
        until_sunset_frame = ttk.Frame(right_countdown)
        until_sunset_frame.pack(fill="x", pady=1)
        ttk.Label(until_sunset_frame, text="Until Sunset:", width=12).pack(side=tk.LEFT)
        ttk.Label(until_sunset_frame, textvariable=self.to_sunset, style="CountdownTime.TLabel").pack(side=tk.LEFT)
        
        # Until True Night row
        until_true_night_frame = ttk.Frame(right_countdown)
        until_true_night_frame.pack(fill="x", pady=1)
        ttk.Label(until_true_night_frame, text="Until True Night:", width=12).pack(side=tk.LEFT)
        ttk.Label(until_true_night_frame, textvariable=self.to_true_night, style="CountdownTime.TLabel").pack(side=tk.LEFT)
            
    def update_lighting_info(self):
        """Update all lighting information with better error handling and debug"""
        try:
            # Get current lighting information
            lighting_info = get_lighting_info()
            
            # Critical debug - print exactly what we get
            self.logger.info(f"LightingPanel received: condition={lighting_info.get('condition', 'MISSING')}, "
                        f"next_sunrise={lighting_info.get('next_sunrise', 'MISSING')}")
            
            # Fix for blank fields - provide fallback values if missing
            condition = lighting_info.get('condition', 'unknown')
            self.lighting_condition.set(condition.upper() if condition else "UNKNOWN")
            
            # Update condition label style
            if condition == 'day':
                self.condition_label.configure(style='Day.TLabel')
            elif condition == 'night':
                self.condition_label.configure(style='Night.TLabel')
            else:
                self.condition_label.configure(style='Transition.TLabel')
            
            # Update detailed condition if in transition
            detailed = lighting_info.get('detailed_condition', '')
            if condition == 'transition' and detailed:
                self.detailed_condition.set(f"({detailed.upper()})")
            else:
                self.detailed_condition.set("")
                
            # Update times with fallbacks for missing values
            self.sunrise_time.set(lighting_info.get('next_sunrise', '--:--'))
            self.sunset_time.set(lighting_info.get('next_sunset', '--:--'))
            self.true_day_time.set(lighting_info.get('next_true_day', '--:--'))
            self.true_night_time.set(lighting_info.get('next_true_night', '--:--'))
                
            # Update countdowns with fallbacks
            countdown = lighting_info.get('countdown', {})
            
            self.to_sunrise.set(format_time_until(countdown.get('to_sunrise', None)) if countdown else '--:--')
            self.to_sunset.set(format_time_until(countdown.get('to_sunset', None)) if countdown else '--:--')
            self.to_true_day.set(format_time_until(countdown.get('to_true_day', None)) if countdown else '--:--')
            self.to_true_night.set(format_time_until(countdown.get('to_true_night', None)) if countdown else '--:--')
                
            # Update transition progress
            is_transition = lighting_info.get('is_transition', False)
            if is_transition:
                progress = lighting_info.get('transition_percentage', 0)
                self.transition_percentage.set(progress)
                self.percentage_label.config(text=f"{progress:.1f}%")
                
                # Show transition progress
                if not self.is_transition:
                    self.transition_frame.pack(side=tk.RIGHT, fill="x", expand=True, padx=2)
                    self.is_transition = True
            else:
                # Hide transition progress
                if self.is_transition:
                    self.transition_frame.pack_forget()
                    self.is_transition = False
                    
        except Exception as e:
            self.logger.error(f"Error updating lighting info: {e}")
            # Ensure UI still has values even on error
            self.lighting_condition.set("ERROR")
            self.sunrise_time.set("--:--")
            self.sunset_time.set("--:--")
            
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
        
        self.running = True
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()
        
    def stop_update_thread(self):
        """Stop the update thread when panel is destroyed"""
        self.running = False
        if self.update_thread:
            try:
                self.update_thread.join(timeout=1)
                self.logger.info("Lighting panel update thread stopped")
            except Exception as e:
                self.logger.error(f"Error stopping lighting panel update thread: {e}")
            
    def destroy(self):
        """Clean up resources when panel is destroyed"""
        try:
            self.stop_update_thread()
        except Exception as e:
            self.logger.error(f"Error during lighting panel cleanup: {e}")
        finally:
            super().destroy()